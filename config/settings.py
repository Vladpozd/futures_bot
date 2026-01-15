
"""
Основные настройки бота из .env файла.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import time
from typing import List, Tuple

# Загружаем .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Settings:
    """Все настройки бота"""
    
    # === API ===
    TINKOFF_TOKEN: str = os.getenv('TINKOFF_TOKEN', '')
    SANDBOX_MODE: bool = os.getenv('SANDBOX_MODE', 'true').lower() == 'true'
    
    # === Депозит и плечо ===
    INITIAL_DEPOSIT: float = float(os.getenv('INITIAL_DEPOSIT', '10000'))
    MAX_LEVERAGE: int = int(os.getenv('MAX_LEVERAGE', '10'))
    MIN_LEVERAGE: int = int(os.getenv('MIN_LEVERAGE', '5'))
    RISK_LEVEL: str = os.getenv('RISK_LEVEL', 'high')
    
    # === Комиссии ===
    COMMISSION_BUY: float = float(os.getenv('COMMISSION_BUY', '0.00045'))
    COMMISSION_SELL: float = float(os.getenv('COMMISSION_SELL', '0.00045'))
    MIN_PROFIT_THRESHOLD: float = float(os.getenv('MIN_PROFIT_THRESHOLD', '0.00091'))
    
    # === Время торговли ===
    TRADING_SESSIONS: List[Tuple[time, time]] = [
        (time.fromisoformat(os.getenv('TRADING_SESSION_1_START', '09:00')),
         time.fromisoformat(os.getenv('TRADING_SESSION_1_END', '14:00'))),
        (time.fromisoformat(os.getenv('TRADING_SESSION_2_START', '14:05')),
         time.fromisoformat(os.getenv('TRADING_SESSION_2_END', '19:45'))),
        (time.fromisoformat(os.getenv('TRADING_SESSION_3_START', '21:05')),
         time.fromisoformat(os.getenv('TRADING_SESSION_3_END', '23:45')))
    ]
    
    # === Вариационная маржа ===
    VM_ACCURAL_TIMES: List[time] = [
        time.fromisoformat(os.getenv('VM_ACCURAL_1', '14:05')),
        time.fromisoformat(os.getenv('VM_ACCURAL_2', '21:05'))
    ]
    
    # === Таймфреймы ===
    TIMEFRAMES: List[str] = os.getenv('TIMEFRAMES', '15m,1h,4h,1d').split(',')
    
    # === Частота обновления ===
    UPDATE_INTERVALS = {
        '15m': os.getenv('UPDATE_15M_EVERY', '1h'),
        '1h': os.getenv('UPDATE_1H_EVERY', '4h'),
        '4h': os.getenv('UPDATE_4H_EVERY', '1d'),
        '1d': os.getenv('UPDATE_1D_EVERY', '1w')
    }
    
    # === Логирование ===
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', 'logs/bot.log')
    
    # === Инструменты ===
    DEFAULT_TICKER: str = os.getenv('DEFAULT_TICKER', 'Si-3.26')
    
    # === Пороги вероятности ===
    MIN_PROBABILITY: float = float(os.getenv('MIN_PROBABILITY', '0.30'))
    PROBABILITY_SMALL: float = float(os.getenv('PROBABILITY_SMALL', '0.60'))
    PROBABILITY_MEDIUM: float = float(os.getenv('PROBABILITY_MEDIUM', '0.80'))
    PROBABILITY_LARGE: float = float(os.getenv('PROBABILITY_LARGE', '0.90'))
    PROBABILITY_MAX: float = float(os.getenv('PROBABILITY_MAX', '0.95'))
    
    # === Управление рисками ===
    RISK_PER_TRADE: float = float(os.getenv('RISK_PER_TRADE', '0.02'))
    TRAILING_STOP_ACTIVATION: float = float(os.getenv('TRAILING_STOP_ACTIVATION', '0.10'))
    BREAKEVEN_ACTIVATION: float = float(os.getenv('BREAKEVEN_ACTIVATION', '0.10'))
    
    # === Пути ===
    BASE_DIR: Path = Path(__file__).parent.parent
    LOGS_DIR: Path = BASE_DIR / 'logs'
    DATA_DIR: Path = BASE_DIR / 'data'
    
    # === API Targets (T-Tech/Т-Банк) ===
    INVEST_GRPC_API = "invest-public-api.tinkoff.ru:443"  # Боевой контур
    INVEST_GRPC_API_SANDBOX = "sandbox-invest-public-api.tinkoff.ru:443"  # Песочница
    
    def __init__(self):
        """Инициализация и проверка настроек"""
        self.validate()
        self.create_dirs()
    
    def validate(self):
        """Проверка корректности настроек"""
        if not self.TINKOFF_TOKEN:
            raise ValueError("❌ TINKOFF_TOKEN не указан в .env файле")
        
        if self.INITIAL_DEPOSIT <= 0:
            raise ValueError("❌ INITIAL_DEPOSIT должен быть положительным")
        
        if self.MAX_LEVERAGE < self.MIN_LEVERAGE:
            raise ValueError("❌ MAX_LEVERAGE должен быть >= MIN_LEVERAGE")
        
        print("✅ Настройки загружены успешно")
        print(f"   Режим: {'ПЕСОЧНИЦА' if self.SANDBOX_MODE else 'РЕАЛЬНЫЙ СЧЕТ'}")
        print(f"   Депозит: {self.INITIAL_DEPOSIT:.2f} руб")
        print(f"   Плечо: {self.MIN_LEVERAGE}x - {self.MAX_LEVERAGE}x")
        print(f"   Минимальная вероятность: {self.MIN_PROBABILITY:.0%}")
    
    def create_dirs(self):
        """Создание необходимых директорий"""
        self.LOGS_DIR.mkdir(exist_ok=True)
        self.DATA_DIR.mkdir(exist_ok=True)
    
    @property
    def api_target(self) -> str:
        """Получить целевой адрес API в зависимости от режима"""
        if self.SANDBOX_MODE:
            return self.INVEST_GRPC_API_SANDBOX
        return self.INVEST_GRPC_API


# Глобальный экземпляр настроек
settings = Settings()
