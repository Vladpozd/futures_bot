"""
Конфигурация торговых часов.
"""
from typing import Dict, List, Tuple
from datetime import time


# Общие торговые часы для фьючерсов Мосбиржи
DEFAULT_TRADING_HOURS = [
    (time(9, 0), time(14, 0)),    # Утренняя сессия: 09:00-14:00
    (time(14, 5), time(19, 45)),  # Дневная сессия: 14:05-19:45
    (time(21, 5), time(23, 45))   # Вечерняя сессия: 21:05-23:45
]

# Специфичные часы для инструментов (если отличаются)
INSTRUMENT_TRADING_HOURS: Dict[str, List[Tuple[time, time]]] = {
    "RTS-3.26": [
        (time(10, 0), time(23, 50))
    ],
    "RTSM-3.26": [
        (time(10, 0), time(23, 50))
    ],
    "IMOEXF": [
        (time(9, 50), time(23, 50))
    ],
    "MXI-3.26": [
        (time(9, 50), time(23, 50))
    ],
    "MIX-3.26": [
        (time(9, 50), time(23, 50))
    ]
}


def get_trading_hours(ticker: str) -> List[Tuple[time, time]]:
    """Получить торговые часы для инструмента"""
    return INSTRUMENT_TRADING_HOURS.get(ticker, DEFAULT_TRADING_HOURS)