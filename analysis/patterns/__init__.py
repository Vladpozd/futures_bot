"""
Анализ графических паттернов.
"""
from .basic_patterns import PatternDetector  # ИЗМЕНЕНО: PatternDetector вместо PatternAnalyzer

# Глобальный экземпляр
pattern_analyzer = PatternDetector()  # Создаем экземпляр PatternDetector

__all__ = ['PatternDetector', 'pattern_analyzer']  # ИЗМЕНЕНО