"""
Анализ имбалансов.
"""
from .analyzer import ImbalanceAnalyzer  # ИЗМЕНЕНО: правильное имя класса

# Глобальный экземпляр
imbalance_analyzer = ImbalanceAnalyzer()

__all__ = ['ImbalanceAnalyzer', 'imbalance_analyzer']