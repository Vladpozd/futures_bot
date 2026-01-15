"""
Анализ волн Эллиота.
"""
from .waves import ElliottWavesAnalyzer  # ИЗМЕНЕНО: добавили 's'

# Глобальный экземпляр
elliott_waves_analyzer = ElliottWavesAnalyzer()

__all__ = ['ElliottWavesAnalyzer', 'elliott_waves_analyzer']