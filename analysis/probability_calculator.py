"""
Калькулятор вероятности для определения размера позиции.
Объединяет все 8 модулей анализа с весами.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

from utils.logger import log


@dataclass
class ModuleWeights:
    """Веса модулей анализа"""
    TECHNICAL: float = 0.20      # 20% - технический анализ
    PATTERNS: float = 0.25       # 25% - графические паттерны
    ELLIOTT: float = 0.15        # 15% - волны Эллиота
    GAPS: float = 0.10           # 10% - гэпы
    IMBALANCES: float = 0.10     # 10% - имбалансы
    PSYCHOLOGICAL: float = 0.10  # 10% - психологические уровни
    ORDERBOOK: float = 0.10      # 10% - стакан (Level 2)
    
    # Проверка, что сумма весов = 1.0
    def __post_init__(self):
        total = sum([
            self.TECHNICAL, self.PATTERNS, self.ELLIOTT,
            self.GAPS, self.IMBALANCES, self.PSYCHOLOGICAL,
            self.ORDERBOOK
        ])
        if abs(total - 1.0) > 0.001:
            log.warning(f"Сумма весов модулей ≠ 1.0: {total}")


@dataclass
class ProbabilityThresholds:
    """Пороговые значения вероятности"""
    MIN_TO_OPEN: float = 0.30      # Минимум 30% для открытия позиции
    SMALL_POSITION: float = 0.60   # 30-60% - маленькая позиция
    MEDIUM_POSITION: float = 0.80  # 60-80% - средняя позиция
    LARGE_POSITION: float = 0.90   # 80-90% - большая позиция
    MAX_POSITION: float = 0.95     # 90%+ - максимальная позиция


class ProbabilityCalculator:
    """
    Калькулятор вероятности успеха сделки.
    Объединяет все модули анализа с учетом их весов.
    """
    
    def __init__(self):
        self.weights = ModuleWeights()
        self.thresholds = ProbabilityThresholds()
        
        log.info("Инициализация калькулятора вероятности")
        log.info(f"Веса модулей: Тех.анализ {self.weights.TECHNICAL:.0%}, "
                f"Паттерны {self.weights.PATTERNS:.0%}, "
                f"Эллиот {self.weights.ELLIOTT:.0%}")
    
    def calculate_probability(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитать итоговую вероятность на основе всех модулей анализа.
        
        Args:
            analysis_results: Словарь с результатами всех модулей анализа.
                             Пример структуры:
                             {
                                 'technical': {'score': 0.7, 'confidence': 0.8, 'signal': 'BUY'},
                                 'patterns': {'score': 0.8, 'confidence': 0.9, 'signal': 'BUY'},
                                 'elliott': {'score': 0.6, 'confidence': 0.7, 'signal': 'BUY'},
                                 'gaps': {'score': 0.5, 'confidence': 0.6, 'signal': 'NEUTRAL'},
                                 'imbalances': {'score': 0.4, 'confidence': 0.5, 'signal': 'SELL'},
                                 'psychological': {'score': 0.9, 'confidence': 0.8, 'signal': 'BUY'},
                                 'orderbook': {'score': 0.3, 'confidence': 0.4, 'signal': 'NEUTRAL'}
                             }
        
        Returns:
            Словарь с вероятностью и деталями расчета:
            {
                'final_probability': 0.75,
                'weighted_components': {...},
                'signal_consistency': 0.85,
                'can_open_position': True,
                'position_size_category': 'MEDIUM',
                'thresholds': {
                    'MIN_TO_OPEN': 0.30,
                    'SMALL': 0.60,
                    'MEDIUM': 0.80,
                    'LARGE': 0.90
                }
            }
        """
        log.debug("Начало расчета вероятности")
        
        # Проверяем наличие данных
        if not analysis_results:
            log.warning("Нет данных анализа для расчета вероятности")
            return self._get_empty_result()
        
        # Шаг 1: Рассчитываем взвешенные компоненты
        weighted_components = self._calculate_weighted_components(analysis_results)
        
        # Шаг 2: Рассчитываем итоговую вероятность
        final_probability = self._calculate_final_probability(weighted_components)
        
        # Шаг 3: Анализируем согласованность сигналов
        signal_consistency = self._calculate_signal_consistency(analysis_results)
        
        # Шаг 4: Корректируем вероятность на согласованность
        if signal_consistency < 0.5:
            # Если сигналы противоречат друг другу - снижаем вероятность
            final_probability *= signal_consistency
            log.debug(f"Корректировка вероятности из-за низкой согласованности: {signal_consistency:.2%}")
        
        # Шаг 5: Определяем категорию размера позиции
        position_category = self._get_position_size_category(final_probability)
        
        # Шаг 6: Проверяем, можно ли открывать позицию
        can_open_position = final_probability >= self.thresholds.MIN_TO_OPEN
        
        # Формируем результат
        result = {
            'final_probability': round(final_probability, 4),
            'weighted_components': weighted_components,
            'signal_consistency': round(signal_consistency, 4),
            'can_open_position': can_open_position,
            'position_size_category': position_category,
            'thresholds': {
                'MIN_TO_OPEN': self.thresholds.MIN_TO_OPEN,
                'SMALL': self.thresholds.SMALL_POSITION,
                'MEDIUM': self.thresholds.MEDIUM_POSITION,
                'LARGE': self.thresholds.LARGE_POSITION,
                'MAX': self.thresholds.MAX_POSITION
            },
            'confidence_level': self._get_confidence_level(final_probability)
        }
        
        log.info(f"Рассчитана вероятность: {final_probability:.1%} "
                f"(Категория: {position_category}, "
                f"Согласованность: {signal_consistency:.0%})")
        
        return result
    
    def _calculate_weighted_components(self, analysis_results: Dict[str, Any]) -> Dict[str, float]:
        """Рассчитать взвешенные компоненты для каждого модуля"""
        weighted_components = {}
        
        # Технический анализ
        if 'technical' in analysis_results:
            tech = analysis_results['technical']
            score = tech.get('score', 0.5)
            confidence = tech.get('confidence', 0.5)
            weighted = score * confidence * self.weights.TECHNICAL
            weighted_components['technical'] = weighted
        
        # Графические паттерны
        if 'patterns' in analysis_results:
            patterns = analysis_results['patterns']
            score = patterns.get('score', 0.5)
            confidence = patterns.get('confidence', 0.5)
            weighted = score * confidence * self.weights.PATTERNS
            weighted_components['patterns'] = weighted
        
        # Волны Эллиота
        if 'elliott' in analysis_results:
            elliott = analysis_results['elliott']
            score = elliott.get('score', 0.5)
            confidence = elliott.get('confidence', 0.5)
            weighted = score * confidence * self.weights.ELLIOTT
            weighted_components['elliott'] = weighted
        
        # Гэпы
        if 'gaps' in analysis_results:
            gaps = analysis_results['gaps']
            score = gaps.get('score', 0.5)
            confidence = gaps.get('confidence', 0.5)
            weighted = score * confidence * self.weights.GAPS
            weighted_components['gaps'] = weighted
        
        # Имбалансы
        if 'imbalances' in analysis_results:
            imbalances = analysis_results['imbalances']
            score = imbalances.get('score', 0.5)
            confidence = imbalances.get('confidence', 0.5)
            weighted = score * confidence * self.weights.IMBALANCES
            weighted_components['imbalances'] = weighted
        
        # Психологические уровни
        if 'psychological' in analysis_results:
            psych = analysis_results['psychological']
            score = psych.get('score', 0.5)
            confidence = psych.get('confidence', 0.5)
            weighted = score * confidence * self.weights.PSYCHOLOGICAL
            weighted_components['psychological'] = weighted
        
        # Стакан (Level 2)
        if 'orderbook' in analysis_results:
            orderbook = analysis_results['orderbook']
            score = orderbook.get('score', 0.5)
            confidence = orderbook.get('confidence', 0.5)
            weighted = score * confidence * self.weights.ORDERBOOK
            weighted_components['orderbook'] = weighted
        
        # Если каких-то модулей нет - добавляем базовые значения
        expected_modules = ['technical', 'patterns', 'elliott', 'gaps', 
                          'imbalances', 'psychological', 'orderbook']
        
        for module in expected_modules:
            if module not in weighted_components:
                # Базовый вес: 0.5 * 0.5 * вес_модуля
                weight = getattr(self.weights, module.upper())
                weighted_components[module] = 0.25 * weight
        
        return weighted_components
    
    def _calculate_final_probability(self, weighted_components: Dict[str, float]) -> float:
        """Рассчитать итоговую вероятность из взвешенных компонентов"""
        total_weighted = sum(weighted_components.values())
        
        # Сумма всех весов (должна быть 1.0, но на всякий случай)
        total_weights = sum([
            self.weights.TECHNICAL, self.weights.PATTERNS, self.weights.ELLIOTT,
            self.weights.GAPS, self.weights.IMBALANCES, self.weights.PSYCHOLOGICAL,
            self.weights.ORDERBOOK
        ])
        
        # Итоговая вероятность
        if total_weights > 0:
            final_probability = total_weighted / total_weights
        else:
            final_probability = total_weighted
        
        # Ограничиваем от 0 до 1
        final_probability = max(0.0, min(1.0, final_probability))
        
        return final_probability
    
    def _calculate_signal_consistency(self, analysis_results: Dict[str, Any]) -> float:
        """
        Рассчитать согласованность сигналов между модулями.
        Возвращает значение от 0.0 (полное противоречие) до 1.0 (полное согласие)
        """
        if not analysis_results:
            return 0.5  # Нейтральное значение при отсутствии данных
        
        # Собираем все сигналы
        signals = []
        signals_strength = []
        
        for module_name, module_data in analysis_results.items():
            signal = module_data.get('signal', 'NEUTRAL')
            confidence = module_data.get('confidence', 0.5)
            
            # Конвертируем сигнал в числовое значение
            if signal == 'BUY':
                signal_value = 1.0
            elif signal == 'SELL':
                signal_value = -1.0
            else:  # NEUTRAL
                signal_value = 0.0
            
            signals.append(signal_value)
            signals_strength.append(confidence)
        
        if not signals:
            return 0.5
        
        # Рассчитываем дисперсию сигналов
        signals_array = np.array(signals)
        weights_array = np.array(signals_strength)
        
        if len(signals_array) == 1:
            return 1.0  # Если только один модуль - полная согласованность
        
        # Взвешенное среднее сигналов
        if weights_array.sum() > 0:
            weighted_mean = np.average(signals_array, weights=weights_array)
        else:
            weighted_mean = np.mean(signals_array)
        
        # Рассчитываем согласованность
        # Чем ближе все сигналы к среднему - тем выше согласованность
        deviations = np.abs(signals_array - weighted_mean)
        max_deviation = max(np.abs(signals_array).max(), 1.0)
        
        consistency = 1.0 - (deviations.mean() / max_deviation)
        
        return float(max(0.0, min(1.0, consistency)))
    
    def _get_position_size_category(self, probability: float) -> str:
        """Определить категорию размера позиции на основе вероятности"""
        if probability < self.thresholds.MIN_TO_OPEN:
            return 'NONE'
        elif probability < self.thresholds.SMALL_POSITION:
            return 'SMALL'
        elif probability < self.thresholds.MEDIUM_POSITION:
            return 'MEDIUM'
        elif probability < self.thresholds.LARGE_POSITION:
            return 'LARGE'
        elif probability < self.thresholds.MAX_POSITION:
            return 'MAX'
        else:
            return 'MAX'  # Максимальная позиция
    
    def _get_confidence_level(self, probability: float) -> str:
        """Определить уровень уверенности на основе вероятности"""
        if probability < 0.3:
            return 'VERY_LOW'
        elif probability < 0.5:
            return 'LOW'
        elif probability < 0.7:
            return 'MEDIUM'
        elif probability < 0.85:
            return 'HIGH'
        else:
            return 'VERY_HIGH'
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Возвращает пустой результат при отсутствии данных"""
        return {
            'final_probability': 0.0,
            'weighted_components': {},
            'signal_consistency': 0.0,
            'can_open_position': False,
            'position_size_category': 'NONE',
            'thresholds': {
                'MIN_TO_OPEN': self.thresholds.MIN_TO_OPEN,
                'SMALL': self.thresholds.SMALL_POSITION,
                'MEDIUM': self.thresholds.MEDIUM_POSITION,
                'LARGE': self.thresholds.LARGE_POSITION,
                'MAX': self.thresholds.MAX_POSITION
            },
            'confidence_level': 'VERY_LOW'
        }
    
    def calculate_position_size_percentage(self, probability: float) -> float:
        """
        Рассчитать процент депозита для позиции на основе вероятности.
        
        Args:
            probability: Вероятность от 0.0 до 1.0
            
        Returns:
            Процент депозита от 0% до 100%
        """
        if probability < self.thresholds.MIN_TO_OPEN:
            return 0.0
        
        # Линейное преобразование: вероятность → процент
        # 0.3 (30%) → 0%, 1.0 (100%) → 100%
        min_prob = self.thresholds.MIN_TO_OPEN
        percentage = ((probability - min_prob) / (1.0 - min_prob)) * 100
        
        # Ограничиваем от 0 до 100
        percentage = max(0.0, min(100.0, percentage))
        
        log.debug(f"Процент позиции: вероятность {probability:.1%} → {percentage:.1f}% депозита")
        
        return percentage


# Глобальный экземпляр
probability_calculator = ProbabilityCalculator()


# Тестовые функции
def test_probability_calculator():
    """Тест калькулятора вероятности"""
    print("🧪 Тест калькулятора вероятности")
    
    # Тестовые данные анализа
    test_analysis = {
        'technical': {'score': 0.8, 'confidence': 0.9, 'signal': 'BUY'},
        'patterns': {'score': 0.7, 'confidence': 0.8, 'signal': 'BUY'},
        'elliott': {'score': 0.6, 'confidence': 0.7, 'signal': 'BUY'},
        'gaps': {'score': 0.5, 'confidence': 0.6, 'signal': 'NEUTRAL'},
        'imbalances': {'score': 0.4, 'confidence': 0.5, 'signal': 'NEUTRAL'},
        'psychological': {'score': 0.9, 'confidence': 0.8, 'signal': 'BUY'},
        'orderbook': {'score': 0.3, 'confidence': 0.4, 'signal': 'NEUTRAL'}
    }
    
    calculator = ProbabilityCalculator()
    result = calculator.calculate_probability(test_analysis)
    
    print(f"Итоговая вероятность: {result['final_probability']:.1%}")
    print(f"Можно открыть позицию: {'Да' if result['can_open_position'] else 'Нет'}")
    print(f"Категория позиции: {result['position_size_category']}")
    print(f"Процент депозита: {calculator.calculate_position_size_percentage(result['final_probability']):.1f}%")
    
    print("\nВзвешенные компоненты:")
    for module, weight in result['weighted_components'].items():
        print(f"  {module}: {weight:.3f}")
    
    return result


if __name__ == "__main__":
    # Запуск теста при прямом выполнении файла
    test_result = test_probability_calculator()