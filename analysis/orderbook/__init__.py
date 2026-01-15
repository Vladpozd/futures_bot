
"""
Анализ стакана заявок (биржевого стакана).
"""
from .analyzer import OrderBookAnalyzer

# Глобальный экземпляр
orderbook_analyzer = OrderBookAnalyzer()

__all__ = ['OrderBookAnalyzer', 'orderbook_analyzer']
