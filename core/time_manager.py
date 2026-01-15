"""
Управление временем торговли по московскому времени.
Обрабатывает перерывы и сессии.
"""
from datetime import datetime, time, timedelta
from typing import List, Tuple
import pytz
from loguru import logger

from config.settings import settings


class TradingTimeManager:
    """Менеджер торгового времени"""
    
    def __init__(self):
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        self.trading_sessions = settings.TRADING_SESSIONS
        self.vm_times = settings.VM_ACCURAL_TIMES
        
        logger.info(f"Настроено {len(self.trading_sessions)} торговых сессий")
    
    def get_moscow_time(self) -> datetime:
        """Получить текущее московское время"""
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        return utc_now.astimezone(self.moscow_tz)
    
    def is_trading_time(self) -> bool:
        """
        Проверка, идет ли сейчас торговая сессия.
        Возвращает True, если можно торговать.
        """
        moscow_time = self.get_moscow_time()
        current_time = moscow_time.time()
        weekday = moscow_time.weekday()  # 0=пн, 4=пт, 5=сб, 6=вс
        
        # Не торгуем в выходные
        if weekday >= 5:
            logger.debug(f"Выходной день: {weekday}")
            return False
        
        # Проверяем все торговые сессии
        for session_start, session_end in self.trading_sessions:
            if session_start <= current_time <= session_end:
                logger.debug(f"Идет торговая сессия: {session_start}-{session_end}")
                return True
        
        logger.debug(f"Вне торговой сессии: {current_time}")
        return False
    
    def get_time_to_next_session(self) -> timedelta:
        """
        Получить время до следующей торговой сессии.
        Возвращает timedelta.
        """
        moscow_time = self.get_moscow_time()
        current_time = moscow_time.time()
        
        # Если сейчас торговая сессия - возвращаем 0
        if self.is_trading_time():
            return timedelta(seconds=0)
        
        # Ищем ближайшую будущую сессию
        for session_start, session_end in self.trading_sessions:
            if current_time < session_start:
                # Сессия сегодня
                next_start = datetime.combine(moscow_time.date(), session_start)
                next_start = self.moscow_tz.localize(next_start)
                return next_start - moscow_time
        
        # Если все сессии сегодня прошли - ждем первую сессию завтра
        tomorrow = moscow_time.date() + timedelta(days=1)
        first_session_start, _ = self.trading_sessions[0]
        next_start = datetime.combine(tomorrow, first_session_start)
        next_start = self.moscow_tz.localize(next_start)
        
        return next_start - moscow_time
    
    def is_vm_accural_time(self) -> bool:
        """
        Проверка, наступило ли время начисления вариационной маржи.
        """
        moscow_time = self.get_moscow_time()
        current_time = moscow_time.time()
        
        for vm_time in self.vm_times:
            # Проверяем +/- 1 минуту от времени начисления
            time_window_start = (datetime.combine(moscow_time.date(), vm_time) - 
                               timedelta(minutes=1)).time()
            time_window_end = (datetime.combine(moscow_time.date(), vm_time) + 
                              timedelta(minutes=1)).time()
            
            if time_window_start <= current_time <= time_window_end:
                logger.info(f"Время начисления ВМ: {vm_time}")
                return True
        
        return False
    
    def get_current_session_info(self) -> dict:
        """Получить информацию о текущей/ближайшей сессии"""
        moscow_time = self.get_moscow_time()
        
        return {
            'moscow_time': moscow_time.strftime('%Y-%m-%d %H:%M:%S'),
            'is_trading_time': self.is_trading_time(),
            'time_to_next_session': str(self.get_time_to_next_session()),
            'is_vm_accural_time': self.is_vm_accural_time(),
            'weekday': moscow_time.strftime('%A')
        }


# Глобальный экземпляр
time_manager = TradingTimeManager()