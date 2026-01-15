from .indicators import TechnicalIndicators
from .psychological import PsychologicalLevels

# Глобальные экземпляры
technical_indicators = TechnicalIndicators()
psychological_levels = PsychologicalLevels()

__all__ = [
    'TechnicalIndicators',
    'PsychologicalLevels',
    'technical_indicators',
    'psychological_levels'
]