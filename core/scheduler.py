"""
Планировщик задач для обновления анализа по расписанию.
Обновление по таймфреймам: 15м, 1ч, 4ч, 1д.
"""
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Callable

from core.time_manager import time_manager
# УБРАЛИ импорт analyzer здесь - будет импортироваться внутри методов
from config.settings import settings
from config.instruments import get_all_tickers
from utils.logger import log


class AnalysisScheduler:
    """
    Планировщик обновления анализа по расписанию.
    
    Обновление:
    - 15м: каждый час
    - 1ч: каждые 4 часа  
    - 4ч: каждый день
    - 1д: каждую неделю
    """
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_updates: Dict[str, datetime] = {}
        self.update_intervals = settings.UPDATE_INTERVALS
        
        log.info("Инициализация планировщика анализа")
    
    def _get_analyzer(self):
        """Ленивый импорт анализатора для избежания циклической зависимости"""
        from analysis.analyzer import market_analyzer
        return market_analyzer
    
    def start(self):
        """Запустить планировщик в отдельном потоке"""
        if self.running:
            log.warning("Планировщик уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        log.info("✅ Планировщик анализа запущен")
    
    def stop(self):
        """Остановить планировщик"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        log.info("Планировщик анализа остановлен")
    
    def _run_scheduler(self):
        """Основной цикл планировщика"""
        # Настраиваем расписание
        self._setup_schedule()
        
        # Бесконечный цикл проверки задач
        while self.running:
            try:
                # Запускаем pending задачи
                schedule.run_pending()
                
                # Проверяем время торговли
                if time_manager.is_trading_time():
                    # В торговое время проверяем более часто
                    self._check_additional_updates()
                
                # Ждем 1 минуту перед следующей проверкой
                time.sleep(60)
                
            except Exception as e:
                log.error(f"Ошибка в планировщике: {e}")
                time.sleep(300)  # Ждем 5 минут при ошибке
    
    def _setup_schedule(self):
        """Настроить расписание обновлений"""
        
        # 15-минутный таймфрейм: каждый час
        schedule.every().hour.at(":00").do(
            self._scheduled_update, timeframe="15m", name="15m_hourly"
        )
        
        # Часовой таймфрейм: каждые 4 часа
        for hour in [0, 4, 8, 12, 16, 20]:
            schedule.every().day.at(f"{hour:02d}:00").do(
                self._scheduled_update, timeframe="1h", name="1h_4hourly"
            )
        
        # 4-часовой таймфрейм: каждый день в 00:00
        schedule.every().day.at("00:00").do(
            self._scheduled_update, timeframe="4h", name="4h_daily"
        )
        
        # Дневной таймфрейм: каждый понедельник в 00:00
        schedule.every().monday.at("00:00").do(
            self._scheduled_update, timeframe="1d", name="1d_weekly"
        )
        
        log.info("Расписание обновлений настроено")
    
    def _scheduled_update(self, timeframe: str, name: str):
        """Плановое обновление анализа"""
        if not time_manager.is_trading_time():
            log.debug(f"Пропускаем обновление {name}: не время торговли")
            return
        
        log.info(f"🔄 Плановое обновление анализа: {name}")
        
        try:
            # Ленивый импорт анализатора
            market_analyzer = self._get_analyzer()
            
            # Обновляем все инструменты на указанном таймфрейме
            all_tickers = get_all_tickers()
            
            for ticker in all_tickers:
                try:
                    analysis = market_analyzer.comprehensive_analysis(ticker, timeframe)
                    
                    # Сохраняем время последнего обновления
                    update_key = f"{ticker}_{timeframe}"
                    self.last_updates[update_key] = datetime.now()
                    
                    # Логируем результат
                    signal = analysis.get('integrated_signal', {})
                    prob = analysis.get('final_probability', 0)
                    
                    if signal.get('direction') != 'NEUTRAL' and prob > 0.6:
                        log.info(f"  📊 {ticker} ({timeframe}): {signal.get('direction')} "
                                f"({prob:.1%}), сила: {signal.get('strength', 0):.1f}%")
                    
                except Exception as e:
                    log.error(f"Ошибка обновления {ticker}: {e}")
            
            log.success(f"✅ Обновление {name} завершено")
            
        except Exception as e:
            log.error(f"Ошибка планового обновления {name}: {e}")
    
    def _check_additional_updates(self):
        """
        Проверить необходимость дополнительных обновлений.
        Обновляет анализ при сильных движениях рынка.
        """
        current_time = datetime.now()
        
        # Проверяем, не было ли обновления за последний час
        for update_key, last_update in list(self.last_updates.items()):
            if current_time - last_update > timedelta(hours=1):
                # Обновляем устаревший анализ
                ticker, timeframe = update_key.split('_')
                
                try:
                    # Ленивый импорт анализатора
                    market_analyzer = self._get_analyzer()
                    
                    analysis = market_analyzer.comprehensive_analysis(ticker, timeframe)
                    self.last_updates[update_key] = current_time
                    
                    # Если появился сильный сигнал - логируем
                    signal = analysis.get('integrated_signal', {})
                    if signal.get('strength', 0) > 70:
                        log.info(f"🚨 Сильный сигнал после обновления {ticker}: "
                                f"{signal.get('direction')} ({signal.get('strength'):.1f}%)")
                    
                except Exception as e:
                    log.error(f"Ошибка дополнительного обновления {update_key}: {e}")
    
    def force_update(self, ticker: str, timeframe: str = "1h"):
        """Принудительное обновление анализа"""
        log.info(f"🔧 Принудительное обновление {ticker} ({timeframe})")
        
        try:
            # Ленивый импорт анализатора
            market_analyzer = self._get_analyzer()
            
            analysis = market_analyzer.comprehensive_analysis(ticker, timeframe)
            
            update_key = f"{ticker}_{timeframe}"
            self.last_updates[update_key] = datetime.now()
            
            signal = analysis.get('integrated_signal', {})
            prob = analysis.get('final_probability', 0)
            
            log.info(f"  Результат: {signal.get('direction')} "
                    f"({prob:.1%}), сила: {signal.get('strength', 0):.1f}%")
            
            return analysis
            
        except Exception as e:
            log.error(f"Ошибка принудительного обновления: {e}")
            return None
    
    def get_update_status(self) -> Dict:
        """Получить статус обновлений"""
        status = {
            'running': self.running,
            'last_updates': {},
            'next_updates': []
        }
        
        # Время последних обновлений
        for key, last_time in self.last_updates.items():
            status['last_updates'][key] = last_time.isoformat()
        
        # Следующие запланированные обновления
        for job in schedule.get_jobs():
            status['next_updates'].append({
                'name': str(job),
                'next_run': job.next_run.isoformat() if job.next_run else None
            })
        
        return status


# Глобальный экземпляр
analysis_scheduler = AnalysisScheduler()
