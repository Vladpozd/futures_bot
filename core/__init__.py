# core/__init__.py - МИНИМАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ:
"""
Инициализация core модулей.
БЕЗ циклических импортов.
"""

# Импортируем только то, что точно существует
from .api_client import api_client, TTechInvestAPIClient

# ⚠️ Если этих модулей нет - удаляем их импорт
# from .portfolio import PortfolioManager  # если есть
# from .risk_manager import RiskManager   # ЭТОГО МОДУЛЯ НЕТ!
# from .time_manager import TimeManager   # если есть

__all__ = [
    'api_client',
    'TTechInvestAPIClient'
    # 'PortfolioManager',  # если есть
    # 'RiskManager',       # если есть  
    # 'TimeManager'        # если есть
]