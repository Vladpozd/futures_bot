"""
Анализатор гэпов (разрывов цены).
Вес: 10% в общей вероятности.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.logger import log


class GapType(Enum):
    """Типы гэпов"""
    COMMON_GAP = "Обычный гэп"
    BREAKAWAY_GAP = "Гэп пробоя"
    RUNAWAY_GAP = "Беглый гэп"
    EXHAUSTION_GAP = "Исчерпывающий гэп"
    ISLAND_REVERSAL = "Островной разворот"


class GapDirection(Enum):
    """Направление гэпа"""
    UP = "Вверх"
    DOWN = "Вниз"


@dataclass
class Gap:
    """Обнаруженный гэп"""
    gap_type: GapType
    direction: GapDirection
    start_idx: int
    gap_size: float  # Размер гэпа в %
    price_before: float
    price_after: float
    filled: bool = False  # Заполнен ли гэп
    fill_percentage: float = 0.0  # Процент заполнения


class GapAnalyzer:
    """
    Анализатор гэпов (разрывов цены).
    Обнаруживает и классифицирует гэпы на графике.
    """
    
    def __init__(self):
        self.min_gap_size = 0.001  # Минимальный размер гэпа (0.1%)
        self.gap_fill_threshold = 0.9  # Гэп считается заполненным при 90% заполнения
        
        log.info("Инициализация анализатора гэпов")
    
    def analyze(self, df: pd.DataFrame, ticker: str = "") -> Dict[str, Any]:
        """
        Проанализировать гэпы на данных.
        
        Args:
            df: DataFrame с ценами (колонки: high, low, close, open)
            ticker: Тикер инструмента (для логирования)
            
        Returns:
            Словарь с результатами анализа гэпов
        """
        if len(df) < 3:
            return self._get_empty_result()
        
        try:
            # Получаем цены
            if 'open' not in df.columns:
                # Если нет открытия, используем закрытие предыдущей свечи
                df['open'] = df['close'].shift(1)
                df['open'].iloc[0] = df['close'].iloc[0]
            
            opens = df['open'].tolist()
            highs = df['high'].tolist()
            lows = df['low'].tolist()
            closes = df['close'].tolist()
            
            # 1. Обнаруживаем все гэпы
            gaps = self._detect_gaps(opens, highs, lows, closes)
            
            # 2. Классифицируем гэпы
            classified_gaps = self._classify_gaps(gaps, highs, lows, closes)
            
            # 3. Анализируем последний гэп (если есть)
            last_gap_analysis = self._analyze_last_gap(classified_gaps, closes[-1])
            
            # 4. Определяем торговый сигнал
            signal, signal_strength = self._generate_signal(classified_gaps, last_gap_analysis)
            
            # 5. Рассчитываем уверенность и score
            confidence = self._calculate_confidence(classified_gaps, last_gap_analysis)
            score = self._calculate_score(confidence, signal_strength, classified_gaps)
            
            result = {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence / 100)),
                'signal': signal,
                'details': {
                    'gaps_count': len(classified_gaps),
                    'last_gap': last_gap_analysis,
                    'gap_types': [g.gap_type.value for g in classified_gaps],
                    'gap_directions': [g.direction.value for g in classified_gaps],
                    'gap_sizes': [g.gap_size for g in classified_gaps],
                    'gaps': [
                        {
                            'type': g.gap_type.value,
                            'direction': g.direction.value,
                            'size_percent': g.gap_size,
                            'filled': g.filled,
                            'fill_percentage': g.fill_percentage
                        }
                        for g in classified_gaps[-3:]  # Последние 3 гэпа
                    ]
                }
            }
            
            log.debug(f"Анализ гэпов: найдено {len(classified_gaps)} гэпов, "
                     f"сигнал: {signal}, уверенность: {confidence:.1f}%")
            
            return result
            
        except Exception as e:
            log.error(f"Ошибка анализа гэпов: {e}")
            return self._get_empty_result()
    
    def _detect_gaps(self, opens: List[float], highs: List[float], 
                    lows: List[float], closes: List[float]) -> List[Gap]:
        """Обнаружить все гэпы в данных"""
        gaps = []
        
        for i in range(1, len(opens)):
            prev_high = highs[i-1]
            prev_low = lows[i-1]
            prev_close = closes[i-1]
            current_open = opens[i]
            current_low = lows[i]
            current_high = highs[i]
            
            # Проверяем гэп вверх
            if current_low > prev_high:
                gap_size = (current_low - prev_high) / prev_high
                if gap_size >= self.min_gap_size:
                    gap = Gap(
                        gap_type=GapType.COMMON_GAP,  # Временно
                        direction=GapDirection.UP,
                        start_idx=i,
                        gap_size=gap_size * 100,  # В процентах
                        price_before=prev_high,
                        price_after=current_low
                    )
                    gaps.append(gap)
            
            # Проверяем гэп вниз
            elif current_high < prev_low:
                gap_size = (prev_low - current_high) / prev_low
                if gap_size >= self.min_gap_size:
                    gap = Gap(
                        gap_type=GapType.COMMON_GAP,  # Временно
                        direction=GapDirection.DOWN,
                        start_idx=i,
                        gap_size=gap_size * 100,  # В процентах
                        price_before=prev_low,
                        price_after=current_high
                    )
                    gaps.append(gap)
        
        return gaps
    
    def _classify_gaps(self, gaps: List[Gap], highs: List[float], 
                      lows: List[float], closes: List[float]) -> List[Gap]:
        """Классифицировать гэпы по типам"""
        if not gaps:
            return []
        
        classified_gaps = []
        
        for i, gap in enumerate(gaps):
            gap_idx = gap.start_idx
            
            # Проверяем, заполнен ли гэп
            gap_filled = self._check_gap_filled(gap, highs, lows, closes)
            gap.fill_percentage = gap_filled['fill_percentage']
            gap.filled = gap_filled['filled']
            
            # Определяем тип гэпа на основе контекста
            gap_type = self._determine_gap_type(gap, i, gaps, closes)
            gap.gap_type = gap_type
            
            classified_gaps.append(gap)
        
        return classified_gaps
    
    def _check_gap_filled(self, gap: Gap, highs: List[float], 
                         lows: List[float], closes: List[float]) -> Dict[str, Any]:
        """Проверить, заполнен ли гэп"""
        gap_idx = gap.start_idx
        
        # Целевая цена для заполнения гэпа
        if gap.direction == GapDirection.UP:
            target_price = gap.price_before  # Нужно вернуться к prev_high
        else:  # DOWN
            target_price = gap.price_before  # Нужно вернуться к prev_low
        
        # Проверяем свечи после гэпа
        fill_data = []
        
        for j in range(gap_idx, min(gap_idx + 20, len(closes))):  # Проверяем 20 свечей
            current_low = lows[j]
            current_high = highs[j]
            
            if gap.direction == GapDirection.UP:
                # Для гэпа вверх: цена опускается до уровня до гэпа
                if current_low <= target_price:
                    fill_percentage = 100.0
                    filled = True
                    break
                else:
                    # Сколько осталось до заполнения
                    remaining = current_low - target_price
                    gap_range = gap.price_after - target_price
                    fill_percentage = max(0, 100 - (remaining / gap_range * 100))
                    filled = fill_percentage >= self.gap_fill_threshold * 100
            else:  # DOWN
                # Для гэпа вниз: цена поднимается до уровня до гэпа
                if current_high >= target_price:
                    fill_percentage = 100.0
                    filled = True
                    break
                else:
                    # Сколько осталось до заполнения
                    remaining = target_price - current_high
                    gap_range = target_price - gap.price_after
                    fill_percentage = max(0, 100 - (remaining / gap_range * 100))
                    filled = fill_percentage >= self.gap_fill_threshold * 100
        
        # Если не нашли заполнения в пределах 20 свечей
        else:
            if 'fill_percentage' not in locals():
                fill_percentage = 0.0
                filled = False
        
        return {
            'fill_percentage': fill_percentage,
            'filled': filled,
            'target_price': target_price
        }
    
    def _determine_gap_type(self, gap: Gap, gap_index: int, 
                           all_gaps: List[Gap], closes: List[float]) -> GapType:
        """Определить тип гэпа"""
        gap_idx = gap.start_idx
        
        # Анализируем контекст вокруг гэпа
        if gap_idx < 5 or gap_idx >= len(closes) - 5:
            return GapType.COMMON_GAP
        
        # Анализируем тренд до гэпа
        prev_prices = closes[max(0, gap_idx-10):gap_idx]
        if len(prev_prices) >= 5:
            prev_trend = self._calculate_trend(prev_prices)
        else:
            prev_trend = 0
        
        # Анализируем движение после гэпа
        if gap_idx + 5 < len(closes):
            post_prices = closes[gap_idx:min(gap_idx+5, len(closes))]
            post_trend = self._calculate_trend(post_prices)
        else:
            post_trend = 0
        
        # Объем гэпа (относительный размер)
        is_large_gap = gap.gap_size > 1.0  # Более 1%
        
        # 1. Гэп пробоя (Breakaway Gap)
        # Появляется после консолидации, с большим объемом
        if (is_large_gap and 
            abs(prev_trend) < 0.001 and  # Боковое движение до гэпа
            abs(post_trend) > 0.002):    # Явный тренд после гэпа
            return GapType.BREAKAWAY_GAP
        
        # 2. Беглый гэп (Runaway Gap)
        # Появляется в середине тренда, в направлении тренда
        elif (is_large_gap and
              prev_trend * post_trend > 0 and  # Тренд продолжается
              abs(prev_trend) > 0.001):       # Был явный тренд
            return GapType.RUNAWAY_GAP
        
        # 3. Исчерпывающий гэп (Exhaustion Gap)
        # Появляется в конце тренда, затем разворот
        elif (is_large_gap and
              prev_trend * post_trend < 0 and  # Тренд меняется
              abs(prev_trend) > 0.002):       # Был сильный тренд
            return GapType.EXHAUSTION_GAP
        
        # 4. Обычный гэп
        else:
            return GapType.COMMON_GAP
    
    def _calculate_trend(self, prices: List[float]) -> float:
        """Рассчитать тренд (наклон) цен"""
        if len(prices) < 2:
            return 0.0
        
        x = np.arange(len(prices))
        y = np.array(prices)
        
        # Линейная регрессия
        A = np.vstack([x, np.ones(len(x))]).T
        slope, _ = np.linalg.lstsq(A, y, rcond=None)[0]
        
        # Нормализуем относительно средней цены
        if np.mean(y) != 0:
            slope = slope / np.mean(y)
        
        return slope
    
    def _analyze_last_gap(self, gaps: List[Gap], current_price: float) -> Dict[str, Any]:
        """Проанализировать последний гэп"""
        if not gaps:
            return {'has_gap': False, 'action': 'NO_GAP'}
        
        last_gap = gaps[-1]
        
        analysis = {
            'has_gap': True,
            'gap_type': last_gap.gap_type.value,
            'direction': last_gap.direction.value,
            'size_percent': last_gap.gap_size,
            'filled': last_gap.filled,
            'fill_percentage': last_gap.fill_percentage,
            'days_since': len(gaps)  # Упрощенно
        }
        
        # Определяем действие на основе последнего гэпа
        if last_gap.filled:
            # Гэп заполнен - возможен отскок
            if last_gap.direction == GapDirection.UP:
                analysis['action'] = 'SELL_AFTER_FILL'  # Заполнен гэп вверх → продавать
            else:
                analysis['action'] = 'BUY_AFTER_FILL'   # Заполнен гэп вниз → покупать
        else:
            # Гэп не заполнен
            if last_gap.gap_type == GapType.BREAKAWAY_GAP:
                # Гэп пробоя - следовать за направлением
                if last_gap.direction == GapDirection.UP:
                    analysis['action'] = 'BUY_BREAKAWAY'
                else:
                    analysis['action'] = 'SELL_BREAKAWAY'
            elif last_gap.gap_type == GapType.EXHAUSTION_GAP:
                # Исчерпывающий гэп - готовиться к развороту
                if last_gap.direction == GapDirection.UP:
                    analysis['action'] = 'PREPARE_SELL'
                else:
                    analysis['action'] = 'PREPARE_BUY'
            else:
                analysis['action'] = 'WAIT'
        
        return analysis
    
    def _generate_signal(self, gaps: List[Gap], 
                        last_gap_analysis: Dict[str, Any]) -> Tuple[str, float]:
        """Сгенерировать торговый сигнал на основе гэпов"""
        if not gaps:
            return "NEUTRAL", 30.0
        
        last_gap_action = last_gap_analysis.get('action', 'NO_GAP')
        
        # Маппинг действий на сигналы
        action_to_signal = {
            'BUY_AFTER_FILL': 'BUY',
            'SELL_AFTER_FILL': 'SELL',
            'BUY_BREAKAWAY': 'BUY',
            'SELL_BREAKAWAY': 'SELL',
            'PREPARE_BUY': 'BUY',
            'PREPARE_SELL': 'SELL',
            'NO_GAP': 'NEUTRAL',
            'WAIT': 'NEUTRAL'
        }
        
        signal = action_to_signal.get(last_gap_action, 'NEUTRAL')
        
        # Определяем силу сигнала
        if signal != 'NEUTRAL':
            # Сила зависит от типа гэпа и заполнения
            last_gap = gaps[-1]
            
            if last_gap.gap_type == GapType.BREAKAWAY_GAP:
                strength = 70.0
            elif last_gap.gap_type == GapType.EXHAUSTION_GAP:
                strength = 60.0
            elif last_gap.filled:
                strength = 65.0
            else:
                strength = 50.0
            
            # Уменьшаем силу со временем
            days_since = last_gap_analysis.get('days_since', 1)
            time_decay = max(0.5, 1.0 - (days_since * 0.1))
            strength *= time_decay
        else:
            strength = 30.0
        
        return signal, min(100.0, max(0.0, strength))
    
    def _calculate_confidence(self, gaps: List[Gap], 
                            last_gap_analysis: Dict[str, Any]) -> float:
        """Рассчитать уверенность в анализе"""
        confidence = 30.0  # Базовая уверенность
        
        if not gaps:
            return confidence
        
        # Увеличиваем уверенность за количество гэпов
        confidence += min(20, len(gaps) * 3)
        
        # Увеличиваем за последний значительный гэп
        if last_gap_analysis.get('has_gap', False):
            gap_size = last_gap_analysis.get('size_percent', 0)
            if gap_size > 0.5:  # Гэп более 0.5%
                confidence += 15
            
            # Тип гэпа влияет на уверенность
            gap_type = last_gap_analysis.get('gap_type', '')
            if 'BREAKAWAY' in gap_type:
                confidence += 20
            elif 'EXHAUSTION' in gap_type:
                confidence += 15
        
        return min(100.0, confidence)
    
    def _calculate_score(self, confidence: float, signal_strength: float,
                        gaps: List[Gap]) -> float:
        """Рассчитать итоговый score (0-1)"""
        if not gaps:
            return 0.5
        
        # Комбинируем уверенность и силу сигнала
        base_score = (confidence / 100 * 0.6) + (signal_strength / 100 * 0.4)
        
        # Корректируем на основе заполнения гэпов
        if gaps:
            last_gap = gaps[-1]
            if last_gap.filled:
                # Заполненный гэп дает более надежные сигналы
                base_score = min(1.0, base_score * 1.1)
            elif last_gap.fill_percentage > 70:
                # Гэп почти заполнен
                base_score = min(1.0, base_score * 1.05)
        
        return min(1.0, max(0.0, base_score))
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Пустой результат при ошибке"""
        return {
            'score': 0.5,
            'confidence': 0.1,
            'signal': 'NEUTRAL',
            'details': {
                'gaps_count': 0,
                'last_gap': {'has_gap': False, 'action': 'NO_GAP'},
                'gap_types': [],
                'gap_directions': [],
                'gap_sizes': [],
                'gaps': []
            }
        }


# Глобальный экземпляр
gap_analyzer = GapAnalyzer()


def test_gap_analyzer():
    """Тест анализатора гэпов"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ АНАЛИЗАТОРА ГЭПОВ")
    print("="*60)
    
    # Создаем тестовые данные с гэпом
    np.random.seed(42)
    
    # Цены до гэпа
    prices_before = []
    for i in range(10):
        prices_before.append(100 + np.random.random() * 2)
    
    # Гэп вверх
    gap_size = 2.0  # 2%
    price_after_gap = prices_before[-1] * (1 + gap_size/100)
    
    # Цены после гэпа
    prices_after = []
    for i in range(10):
        # Постепенно заполняем гэп
        fill_progress = i / 10
        price = price_after_gap * (1 - fill_progress * gap_size/100)
        prices_after.append(price + np.random.random() * 0.5)
    
    # Объединяем
    all_prices = prices_before + prices_after
    
    # Создаем DataFrame
    df = pd.DataFrame({
        'open': all_prices,
        'high': [p + np.random.random() * 0.5 for p in all_prices],
        'low': [p - np.random.random() * 0.5 for p in all_prices],
        'close': all_prices,
        'volume': [1000 + np.random.randint(500) for _ in all_prices]
    })
    
    # Создаем искусственный гэп
    df['open'].iloc[10] = df['close'].iloc[9] * 1.02  # Гэп 2% вверх
    
    analyzer = GapAnalyzer()
    result = analyzer.analyze(df, "TEST")
    
    print(f"Score: {result['score']:.2f}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Signal: {result['signal']}")
    
    details = result['details']
    print(f"\nGaps found: {details['gaps_count']}")
    
    if details['gaps_count'] > 0:
        last_gap = details['last_gap']
        print(f"Last gap: {last_gap['gap_type']}")
        print(f"Direction: {last_gap['direction']}")
        print(f"Size: {last_gap['size_percent']:.2f}%")
        print(f"Filled: {last_gap['filled']}")
        print(f"Fill %: {last_gap['fill_percentage']:.1f}%")
        print(f"Action: {last_gap['action']}")
        
        print(f"\nRecent gaps:")
        for gap in details['gaps']:
            print(f"  Type: {gap['type']}, "
                  f"Dir: {gap['direction']}, "
                  f"Size: {gap['size_percent']:.2f}%, "
                  f"Filled: {gap['filled']}")
    
    print("\n" + "="*60)
    
    return result


if __name__ == "__main__":
    test_gap_analyzer()