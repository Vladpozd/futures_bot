# data/__init__.py - ИСПРАВЛЕННАЯ ВЕРСИЯ:
"""
Инициализация модулей данных.
"""

# Импортируем только локальные модули данных
from .history import HistoricalData, historical_data

# ⚠️ ВАЖНО: НЕ импортируем api_client здесь
# Он должен импортироваться напрямую в тех модулях, где нужен

__all__ = [
    'HistoricalData',
    'historical_data'
]