"""
Конфигурация всех 11 фьючерсов для торговли.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class FutureInstrument:
    """Описание фьючерса"""
    ticker: str
    name: str
    lot_size: int
    point_cost: float  # Стоимость пункта в рублях
    trading_hours: List[str]  # Часы торговли
    min_step: float
    is_rub: bool = True  # Расчет в рублях
    
    @property
    def display_name(self) -> str:
        return f"{self.ticker} ({self.name})"


# 11 фьючерсов из требований
FUTURES_CONFIG: Dict[str, FutureInstrument] = {
    # Индексные
    "IMOEXF": FutureInstrument(
        ticker="IMOEXF",
        name="Фьючерс на индекс МосБиржи",
        lot_size=1,
        point_cost=1.0,
        trading_hours=["09:50-23:50"],
        min_step=1.0
    ),
    
    "MXI-3.26": FutureInstrument(
        ticker="MXI-3.26",
        name="Мини-фьючерс на индекс МосБиржи",
        lot_size=1,
        point_cost=0.2,
        trading_hours=["09:50-23:50"],
        min_step=0.1
    ),
    
    "MIX-3.26": FutureInstrument(
        ticker="MIX-3.26", 
        name="Мини-фьючерс на индекс МосБиржи в долларах",
        lot_size=1,
        point_cost=0.2,
        trading_hours=["09:50-23:50"],
        min_step=0.1,
        is_rub=False
    ),
    
    # RTS
    "RTS-3.26": FutureInstrument(
        ticker="RTS-3.26",
        name="Фьючерс на индекс RTS",
        lot_size=1,
        point_cost=0.02,  # $0.02 за пункт
        trading_hours=["10:00-23:50"],
        min_step=1.0,
        is_rub=False
    ),
    
    "RTSM-3.26": FutureInstrument(
        ticker="RTSM-3.26",
        name="Мини-фьючерс на индекс RTS",
        lot_size=1,
        point_cost=0.002,  # $0.002 за пункт
        trading_hours=["10:00-23:50"],
        min_step=0.1,
        is_rub=False
    ),
    
    # Валютные
    "CNY-3.26": FutureInstrument(
        ticker="CNY-3.26",
        name="Фьючерс на курс CNY/RUB",
        lot_size=1000,
        point_cost=1.0,  # 1 рубль за 1000 юаней
        trading_hours=["09:30-23:50"],
        min_step=0.001
    ),
    
    "CNYRUBF": FutureInstrument(
        ticker="CNYRUBF",
        name="Фьючерс на курс CNY/RUB (поставочный)",
        lot_size=1000,
        point_cost=1.0,
        trading_hours=["09:30-23:50"],
        min_step=0.001
    ),
    
    "Si-3.26": FutureInstrument(
        ticker="Si-3.26",
        name="Фьючерс на курс USD/RUB",
        lot_size=1000,
        point_cost=1.0,  # 1 рубль за 1000 долларов
        trading_hours=["09:30-23:50"],
        min_step=0.0025
    ),
    
    "USDRUBF": FutureInstrument(
        ticker="USDRUBF",
        name="Фьючерс на курс USD/RUB (поставочный)",
        lot_size=1000,
        point_cost=1.0,
        trading_hours=["09:30-23:50"],
        min_step=0.0025
    ),
    
    "Eu-3.26": FutureInstrument(
        ticker="Eu-3.26",
        name="Фьючерс на курс EUR/RUB",
        lot_size=1000,
        point_cost=1.0,  # 1 рубль за 1000 евро
        trading_hours=["09:30-23:50"],
        min_step=0.0025
    ),
    
    "EURRUBF": FutureInstrument(
        ticker="EURRUBF",
        name="Фьючерс на курс EUR/RUB (поставочный)",
        lot_size=1000,
        point_cost=1.0,
        trading_hours=["09:30-23:50"],
        min_step=0.0025
    )
}


def get_all_tickers() -> List[str]:
    """Получить все тикеры"""
    return list(FUTURES_CONFIG.keys())


def get_instrument(ticker: str) -> FutureInstrument:
    """Получить конфигурацию инструмента"""
    if ticker not in FUTURES_CONFIG:
        raise ValueError(f"Инструмент {ticker} не найден в конфигурации")
    return FUTURES_CONFIG[ticker]


def get_front_month_ticker(base_ticker: str) -> str:
    """
    Получить актуальный тикер с ближайшим месяцем экспирации.
    Например, 'Si-3.26' -> 'Si-6.26' в апреле 2024
    """
    # Здесь будет логика определения фронтального месяца
    # Пока возвращаем как есть
    return base_ticker