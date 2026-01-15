
"""
Анализ гэпов (разрывов) на рынке.
"""
from .analyzer import GapAnalyzer

# Глобальный экземпляр
gap_analyzer = GapAnalyzer()

__all__ = ['GapAnalyzer', 'gap_analyzer']
