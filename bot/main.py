"""
Главный цикл торгового бота.
Связывает все модули: анализ → вероятность → позиция → риски → ордера.
"""
import time
import signal
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

from config.settings import settings
from config.instruments import get_all_tickers
from core.api_client import api_client
from core.portfolio import portfolio_manager
from core.time_manager import time_manager
from core.scheduler import analysis_scheduler
from data.history import historical_data

from analysis.analyzer import market_analyzer
from analysis.probability_calculator import probability_calculator
from trading.position_sizing import position_sizing
from trading.risk_manager import risk_manager
from trading.order_executor import order_executor

from utils.logger import log


class TradingBot:
    """Главный класс торгового бота"""
    
    def __init__(self):
        self.running = False
        self.positions = {}
        self.analysis_cache = {}
        
        log.info("=" * 60)
        log.info("🚀 ИНИЦИАЛИЗАЦИЯ ТОРГОВОГО БОТА")
        log.info("=" * 60)
    
    def initialize(self) -> bool:
        """Инициализация бота"""
        try:
            # 1. Проверка подключения к API
            log.info("1. Проверка подключения к Tinkoff API...")
            if not api_client.test_connection():
                log.error("❌ Не удалось подключиться к API")
                return False
            
            # 2. Проверка инструментов
            log.info("2. Проверка доступности инструментов...")
            available = api_client.verify_all_instruments()
            available_count = sum(available.values())
            
            if available_count == 0:
                log.error("❌ Нет доступных инструментов для торговли")
                return False
            
            log.success(f"✅ Доступно инструментов: {available_count}/{len(available)}")
            
            # 3. Загрузка исторических данных
            log.info("3. Загрузка исторических данных...")
            self._load_historical_data()
            
            # 4. Запуск планировщика
            log.info("4. Запуск планировщика анализа...")
            analysis_scheduler.start()
            
            # 5. Начальный отчет
            self._print_startup_report()
            
            log.success("✅ Бот успешно инициализирован")
            return True
            
        except Exception as e:
            log.error(f"❌ Ошибка инициализации: {e}")
            return False
    
    def _load_historical_data(self):
        """Загрузить исторические данные для всех инструментов"""
        tickers = get_all_tickers()
        
        for ticker in tickers[:5]:  # Первые 5 для скорости
            try:
                for timeframe in ['1h', '4h']:
                    historical_data.load_data(ticker, timeframe)
                log.debug(f"Загружены данные для {ticker}")
            except Exception as e:
                log.warning(f"Не удалось загрузить данные для {ticker}: {e}")
    
    def _print_startup_report(self):
        """Напечатать стартовый отчет"""
        print("\n" + "=" * 60)
        print("📊 СТАРТОВЫЙ ОТЧЕТ БОТА")
        print("=" * 60)
        print(f"Депозит: {portfolio_manager.current_deposit:.2f}₽")
        print(f"Плечо: {settings.MIN_LEVERAGE}x - {settings.MAX_LEVERAGE}x")
        print(f"Режим риска: {settings.RISK_LEVEL}")
        print(f"Время торговли: {len(settings.TRADING_SESSIONS)} сессий")
        print(f"Инструменты: {len(get_all_tickers())} фьючерсов")
        print(f"Минимальная вероятность: {settings.MIN_PROBABILITY:.0%}")
        print("=" * 60)
    
    def run(self):
        """Главный цикл бота"""
        if not self.initialize():
            log.error("Не удалось инициализировать бота")
            return
        
        self.running = True
        log.info("🔄 Запуск главного цикла бота")
        
        # Обработка сигналов для graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            while self.running:
                # 1. Проверяем время торговли
                if not time_manager.is_trading_time():
                    time.sleep(60)
                    continue
                
                # 2. Обновляем цены открытых позиций
                self._update_open_positions()
                
                # 3. Анализируем инструменты и торгуем
                self._trading_cycle()
                
                # 4. Пауза между циклами
                time.sleep(10)  # 10 секунд
                
        except Exception as e:
            log.error(f"Ошибка в главном цикле: {e}")
        finally:
            self.shutdown()
    
    def _trading_cycle(self):
        """Один цикл торговли"""
        try:
            # Получаем список всех инструментов
            tickers = get_all_tickers()
            
            for ticker in tickers:
                # Пропускаем если уже есть открытая позиция
                if self._has_open_position(ticker):
                    continue
                
                # Анализируем инструмент
                analysis = self._analyze_instrument(ticker)
                
                if not analysis or not analysis.get('can_open_position', False):
                    continue
                
                # Рассчитываем размер позиции
                current_price = api_client.get_current_price(ticker)
                if not current_price:
                    continue
                
                position_result = position_sizing.calculate_position_size(
                    analysis, ticker, current_price
                )
                
                if not position_result.can_open:
                    continue
                
                # Открываем позицию
                self._open_position(ticker, analysis, position_result, current_price)
                
        except Exception as e:
            log.error(f"Ошибка в цикле торговли: {e}")
    
    def _analyze_instrument(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Проанализировать инструмент"""
        cache_key = f"{ticker}_1h"
        
        # Проверяем кэш (анализ действителен 5 минут)
        if cache_key in self.analysis_cache:
            cache_time, cached_analysis = self.analysis_cache[cache_key]
            if (datetime.now() - cache_time).total_seconds() < 300:
                return cached_analysis
        
        try:
            # Выполняем комплексный анализ
            analysis = market_analyzer.comprehensive_analysis(ticker, "1h")
            
            # Сохраняем в кэш
            self.analysis_cache[cache_key] = (datetime.now(), analysis)
            
            return analysis
            
        except Exception as e:
            log.error(f"Ошибка анализа {ticker}: {e}")
            return None
    
    def _open_position(self, ticker: str, analysis: Dict[str, Any],
                      position_result: Any, current_price: float):
        """Открыть позицию"""
        try:
            signal = analysis.get('integrated_signal', {}).get('direction', 'NEUTRAL')
            
            if signal not in ['BUY', 'SELL']:
                return
            
            # Определяем тип позиции
            position_type = "LONG" if signal == "BUY" else "SHORT"
            
            # Выставляем ордер
            order_result = order_executor.execute_order(
                ticker=ticker,
                direction=signal,
                quantity=position_result.lot_size,
                order_type="MARKET"
            )
            
            if order_result.status != "FILLED":
                log.warning(f"Не удалось открыть позицию {ticker}: {order_result.message}")
                return
            
            # Рассчитываем параметры риска
            risk_params = risk_manager.calculate_risk_parameters(
                ticker=ticker,
                entry_price=order_result.average_price,
                position_type=position_type,
                position_value=position_result.position_value,
                analysis_result=analysis
            )
            
            # Регистрируем позицию в риск-менеджере
            risk_manager.add_position(
                position_id=order_result.order_id,
                ticker=ticker,
                entry_price=order_result.average_price,
                position_type=position_type,
                position_size=position_result.position_value,
                risk_params=risk_params
            )
            
            # Устанавливаем стоп-лосс и тейк-профит
            order_executor.set_position_stop_loss(
                order_result.order_id, risk_params.stop_loss_price
            )
            order_executor.set_position_take_profit(
                order_result.order_id, risk_params.take_profit_price
            )
            
            # Сохраняем информацию о позиции
            self.positions[order_result.order_id] = {
                'ticker': ticker,
                'type': position_type,
                'entry_price': order_result.average_price,
                'quantity': position_result.lot_size,
                'size': position_result.position_value,
                'opened_at': datetime.now()
            }
            
            log.success(f"✅ Открыта позиция {ticker} {position_type}: "
                       f"{position_result.lot_size} лотов по {order_result.average_price:.2f}")
            
        except Exception as e:
            log.error(f"Ошибка открытия позиции {ticker}: {e}")
    
    def _update_open_positions(self):
        """Обновить информацию об открытых позициях"""
        try:
            # Обновляем цены позиций
            order_executor.update_position_prices()
            
            # Проверяем стоп-лоссы и тейк-профиты через риск-менеджер
            for position_id in list(self.positions.keys()):
                current_price = api_client.get_current_price(self.positions[position_id]['ticker'])
                if current_price:
                    actions = risk_manager.update_position_price(position_id, current_price)
                    
                    # Закрываем позицию если сработал стоп или тейк
                    if actions.get('stop_hit') or actions.get('take_hit'):
                        self._close_position(position_id, 
                                           "STOP" if actions.get('stop_hit') else "TAKE")
        
        except Exception as e:
            log.error(f"Ошибка обновления позиций: {e}")
    
    def _close_position(self, position_id: str, reason: str):
        """Закрыть позицию"""
        try:
            order_result = order_executor.close_position(position_id, "MARKET")
            
            if order_result.status == "FILLED":
                # Удаляем из риск-менеджера
                risk_manager.remove_position(position_id)
                
                # Удаляем из нашего списка
                if position_id in self.positions:
                    position_info = self.positions.pop(position_id)
                    pnl = order_executor.get_portfolio_summary().get('total_pnl_rub', 0)
                    
                    log.info(f"Закрыта позиция {position_id} ({reason}): "
                            f"{position_info['ticker']}, PnL: {pnl:+.0f}₽")
        
        except Exception as e:
            log.error(f"Ошибка закрытия позиции {position_id}: {e}")
    
    def _has_open_position(self, ticker: str) -> bool:
        """Проверить есть ли открытая позиция по инструменту"""
        for pos in self.positions.values():
            if pos['ticker'] == ticker:
                return True
        return False
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        log.info(f"Получен сигнал {signum}, завершаем работу...")
        self.running = False
    
    def shutdown(self):
        """Корректное завершение работы бота"""
        log.info("Завершение работы бота...")
        
        # 1. Останавливаем планировщик
        analysis_scheduler.stop()
        
        # 2. Закрываем все открытые позиции
        for position_id in list(self.positions.keys()):
            try:
                self._close_position(position_id, "SHUTDOWN")
            except:
                pass
        
        # 3. Печатаем финальный отчет
        self._print_final_report()
        
        log.info("Бот завершил работу")
    
    def _print_final_report(self):
        """Напечатать финальный отчет"""
        portfolio = order_executor.get_portfolio_summary()
        
        print("\n" + "=" * 60)
        print("📊 ФИНАЛЬНЫЙ ОТЧЕТ")
        print("=" * 60)
        print(f"Депозит: {portfolio_manager.current_deposit:.2f}₽")
        print(f"Итого PnL: {portfolio.get('total_pnl_rub', 0):+.2f}₽")
        print(f"Открыто позиций: {portfolio.get('total_positions', 0)}")
        print(f"Общая стоимость позиций: {portfolio.get('total_position_value', 0):.2f}₽")
        print("=" * 60)


def main():
    """Точка входа"""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()