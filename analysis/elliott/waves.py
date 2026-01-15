"""
Анализатор волн Эллиота.
Вес: 15% в общей вероятности.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.logger import log


class ElliottWaveType(Enum):
    """Типы волн Эллиота"""
    IMPULSE = "Импульсная волна"      # 1, 3, 5, A, C
    CORRECTIVE = "Коррекционная волна" # 2, 4, B
    UNKNOWN = "Неопределенная"


class ElliottPattern(Enum):
    """Паттерны волн Эллиота"""
    IMPULSE_5 = "Импульс 5-3-5"          # 1-2-3-4-5
    CORRECTION_ABC = "Коррекция A-B-C"   # A-B-C
    DIAGONAL = "Диагональ"
    ZIGZAG = "Зигзаг"
    FLAT = "Плоскость"
    TRIANGLE = "Треугольник"


@dataclass
class ElliottWave:
    """Волна Эллиота"""
    wave_type: ElliottWaveType
    wave_number: str  # "1", "2", "3", "4", "5", "A", "B", "C"
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    retracement: Optional[float] = None  # Откат в %


class ElliottWavesAnalyzer:
    """
    Анализатор волн Эллиота.
    Определяет волновые структуры на графике.
    """
    
    def __init__(self):
        self.min_wave_points = 20  # Минимум точек для анализа волн
        self.fibonacci_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        
        log.info("Инициализация анализатора волн Эллиота")
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Проанализировать волны Эллиота на данных.
        
        Args:
            df: DataFrame с ценами (колонки: high, low, close)
            
        Returns:
            Словарь с результатами анализа
        """
        if len(df) < self.min_wave_points:
            return self._get_empty_result()
        
        try:
            highs = df['high'].tolist()
            lows = df['low'].tolist()
            closes = df['close'].tolist()
            
            # 1. Идентифицируем возможные волны
            waves = self._identify_waves(highs, lows)
            
            # 2. Определяем волновой паттерн
            pattern = self._identify_pattern(waves)
            
            # 3. Определяем текущую позицию в волне
            current_position = self._get_current_wave_position(waves, closes[-1])
            
            # 4. Рассчитываем уверенность
            confidence = self._calculate_confidence(waves, pattern)
            
            # 5. Определяем торговый сигнал
            signal, signal_strength = self._generate_signal(pattern, current_position, waves)
            
            # Рассчитываем итоговый score (0-1)
            score = self._calculate_score(confidence, signal_strength)
            
            result = {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence / 100)),
                'signal': signal,
                'details': {
                    'pattern': pattern.value if pattern else None,
                    'waves_count': len(waves),
                    'current_position': current_position,
                    'confidence_percent': confidence,
                    'waves': [
                        {
                            'wave': w.wave_number,
                            'type': w.wave_type.value,
                            'start_price': w.start_price,
                            'end_price': w.end_price,
                            'retracement': w.retracement
                        }
                        for w in waves
                    ]
                }
            }
            
            log.debug(f"Волновой анализ: {pattern.value if pattern else 'Нет паттерна'}, "
                     f"уверенность: {confidence:.1f}%, сигнал: {signal}")
            
            return result
            
        except Exception as e:
            log.error(f"Ошибка анализа волн Эллиота: {e}")
            return self._get_empty_result()
    
    def _identify_waves(self, highs: List[float], lows: List[float]) -> List[ElliottWave]:
        """
        Идентифицировать волны на графике.
        Упрощенная реализация для MVP.
        """
        waves = []
        
        # Простая логика: находим значительные максимумы и минимумы
        maxima_indices = []
        minima_indices = []
        
        # Ищем локальные максимумы
        for i in range(1, len(highs) - 1):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                maxima_indices.append(i)
        
        # Ищем локальные минимумы
        for i in range(1, len(lows) - 1):
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                minima_indices.append(i)
        
        # Объединяем и сортируем все экстремумы
        extremes = []
        for idx in maxima_indices:
            extremes.append((idx, highs[idx], 'MAX'))
        for idx in minima_indices:
            extremes.append((idx, lows[idx], 'MIN'))
        
        extremes.sort(key=lambda x: x[0])
        
        # Создаем волны из последовательных экстремумов
        for i in range(len(extremes) - 1):
            idx1, price1, type1 = extremes[i]
            idx2, price2, type2 = extremes[i+1]
            
            # Определяем тип волны
            if type1 == 'MAX' and type2 == 'MIN':
                # Нисходящая волна
                wave_type = ElliottWaveType.IMPULSE
                wave_number = self._get_wave_number(len(waves), 'down')
            elif type1 == 'MIN' and type2 == 'MAX':
                # Восходящая волна
                wave_type = ElliottWaveType.IMPULSE
                wave_number = self._get_wave_number(len(waves), 'up')
            else:
                continue
            
            # Рассчитываем откат (если есть предыдущая волна)
            retracement = None
            if waves:
                prev_wave = waves[-1]
                wave_size = abs(prev_wave.end_price - prev_wave.start_price)
                if wave_size > 0:
                    current_move = abs(price2 - price1)
                    retracement = current_move / wave_size
            
            wave = ElliottWave(
                wave_type=wave_type,
                wave_number=wave_number,
                start_idx=idx1,
                end_idx=idx2,
                start_price=price1,
                end_price=price2,
                retracement=retracement
            )
            
            waves.append(wave)
            
            # Ограничиваем количество волн для анализа
            if len(waves) >= 8:  # Достаточно для паттерна 5-3
                break
        
        return waves
    
    def _get_wave_number(self, wave_index: int, direction: str) -> str:
        """Получить номер волны"""
        impulse_waves = ['1', '2', '3', '4', '5']
        corrective_waves = ['A', 'B', 'C']
        
        if wave_index < len(impulse_waves):
            return impulse_waves[wave_index]
        elif wave_index - len(impulse_waves) < len(corrective_waves):
            return corrective_waves[wave_index - len(impulse_waves)]
        else:
            return str(wave_index + 1)
    
    def _identify_pattern(self, waves: List[ElliottWave]) -> Optional[ElliottPattern]:
        """Определить волновой паттерн"""
        if len(waves) < 3:
            return None
        
        # Проверяем паттерн 5-3 (импульс + коррекция)
        if len(waves) >= 5:
            # Простая проверка: первые 5 волн должны чередоваться по направлению
            directions = []
            for i in range(min(5, len(waves))):
                wave = waves[i]
                direction = 'up' if wave.end_price > wave.start_price else 'down'
                directions.append(direction)
            
            # Для импульса 5 волн: 1-вверх, 2-вниз, 3-вверх, 4-вниз, 5-вверх
            # Или наоборот для медвежьего рынка
            if (directions[0] != directions[1] and 
                directions[1] != directions[2] and 
                directions[2] != directions[3] and 
                directions[3] != directions[4]):
                return ElliottPattern.IMPULSE_5
        
        # Проверяем коррекцию A-B-C
        if len(waves) >= 3:
            wave_numbers = [w.wave_number for w in waves[:3]]
            if set(wave_numbers) == {'A', 'B', 'C'}:
                return ElliottPattern.CORRECTION_ABC
        
        return None
    
    def _get_current_wave_position(self, waves: List[ElliottWave], 
                                 current_price: float) -> Dict[str, Any]:
        """Определить текущую позицию в волновой структуре"""
        if not waves:
            return {'wave': None, 'progress': 0, 'is_correction': False}
        
        last_wave = waves[-1]
        
        # Определяем, в какой волне находимся
        current_wave = last_wave.wave_number
        
        # Прогресс в текущей волне (0-100%)
        wave_range = abs(last_wave.end_price - last_wave.start_price)
        if wave_range > 0:
            progress = abs(current_price - last_wave.start_price) / wave_range * 100
            progress = min(100, max(0, progress))
        else:
            progress = 50
        
        # Определяем, является ли текущая волна коррекционной
        is_correction = last_wave.wave_number in ['2', '4', 'B']
        
        return {
            'wave': current_wave,
            'progress': progress,
            'is_correction': is_correction,
            'wave_type': last_wave.wave_type.value
        }
    
    def _calculate_confidence(self, waves: List[ElliottWave], 
                            pattern: Optional[ElliottPattern]) -> float:
        """Рассчитать уверенность в анализе"""
        confidence = 30.0  # Базовая уверенность
        
        # Увеличиваем уверенность за количество волн
        confidence += min(30, len(waves) * 5)
        
        # Увеличиваем за определенный паттерн
        if pattern:
            confidence += 20
        
        # Увеличиваем за соответствие правилам волн Эллиота
        # (упрощенная проверка)
        if len(waves) >= 3:
            # Проверяем, что волна 3 не самая короткая (правило)
            if len(waves) >= 3:
                wave_lengths = [
                    abs(w.end_price - w.start_price) 
                    for w in waves[:3]
                ]
                if len(wave_lengths) == 3:
                    if wave_lengths[1] > wave_lengths[0] and wave_lengths[1] > wave_lengths[2]:
                        confidence += 15
        
        return min(100.0, confidence)
    
    def _generate_signal(self, pattern: Optional[ElliottPattern],
                        current_position: Dict[str, Any],
                        waves: List[ElliottWave]) -> Tuple[str, float]:
        """Сгенерировать торговый сигнал"""
        if not pattern or not waves:
            return "NEUTRAL", 0.0
        
        signal = "NEUTRAL"
        strength = 50.0
        
        current_wave = current_position.get('wave')
        is_correction = current_position.get('is_correction', False)
        progress = current_position.get('progress', 50)
        
        if pattern == ElliottPattern.IMPULSE_5:
            # Для импульсной волны 5-3-5
            if current_wave in ['1', '3', '5']:
                # В импульсной волне - сигнал по направлению
                last_wave = waves[-1]
                if last_wave.end_price > last_wave.start_price:
                    signal = "BUY"
                else:
                    signal = "SELL"
                
                # Сила зависит от прогресса в волне
                if progress < 30:
                    strength = 70.0  # Начало волны - сильный сигнал
                elif progress > 70:
                    strength = 40.0  # Конец волны - слабый сигнал
                else:
                    strength = 60.0
            
            elif current_wave in ['2', '4']:
                # В коррекционной волне - противоположный сигнал
                last_wave = waves[-1]
                if last_wave.end_price > last_wave.start_price:
                    signal = "SELL"  # Коррекция вверх после импульса вниз
                else:
                    signal = "BUY"   # Коррекция вниз после импульса вверх
                strength = 50.0
        
        elif pattern == ElliottPattern.CORRECTION_ABC:
            # Для коррекции A-B-C
            if current_wave == 'C':
                # Волна C обычно завершает коррекцию
                last_wave = waves[-1]
                if len(waves) >= 2:
                    wave_a = waves[-2]
                    # Определяем направление коррекции
                    if wave_a.end_price < wave_a.start_price:
                        signal = "BUY"  # Нисходящая коррекция завершается
                    else:
                        signal = "SELL"  # Восходящая коррекция завершается
                    strength = 60.0
        
        return signal, strength
    
    def _calculate_score(self, confidence: float, signal_strength: float) -> float:
        """Рассчитать итоговый score (0-1)"""
        # Комбинируем уверенность и силу сигнала
        score = (confidence / 100 * 0.7) + (signal_strength / 100 * 0.3)
        return score
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Пустой результат при ошибке"""
        return {
            'score': 0.5,
            'confidence': 0.1,
            'signal': 'NEUTRAL',
            'details': {
                'pattern': None,
                'waves_count': 0,
                'current_position': {'wave': None, 'progress': 0},
                'confidence_percent': 0,
                'waves': []
            }
        }


# Глобальный экземпляр
elliott_waves_analyzer = ElliottWavesAnalyzer()


def test_elliott_analyzer():
    """Тест анализатора волн Эллиота"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ АНАЛИЗАТОРА ВОЛН ЭЛЛИОТА")
    print("="*60)
    
    # Создаем тестовые данные
    np.random.seed(42)
    
    # Симулируем импульсную волну 1-2-3-4-5
    closes = []
    
    # Волна 1: рост
    for i in range(5):
        closes.append(100 + i * 2 + np.random.random())
    
    # Волна 2: коррекция
    for i in range(3):
        closes.append(closes[-1] - 1 - np.random.random() * 0.5)
    
    # Волна 3: сильный рост (самая длинная)
    for i in range(8):
        closes.append(closes[-1] + 3 + np.random.random())
    
    # Волна 4: коррекция
    for i in range(4):
        closes.append(closes[-1] - 2 - np.random.random())
    
    # Волна 5: завершающий рост
    for i in range(5):
        closes.append(closes[-1] + 1.5 + np.random.random())
    
    # Создаем DataFrame
    df = pd.DataFrame({
        'open': closes,
        'high': [c + np.random.random() for c in closes],
        'low': [c - np.random.random() for c in closes],
        'close': closes,
        'volume': [1000 + np.random.randint(500) for _ in closes]
    })
    
    analyzer = ElliottWavesAnalyzer()
    result = analyzer.analyze(df)
    
    print(f"Score: {result['score']:.2f}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Signal: {result['signal']}")
    
    details = result['details']
    print(f"\nPattern: {details['pattern']}")
    print(f"Waves count: {details['waves_count']}")
    print(f"Current wave: {details['current_position']['wave']}")
    print(f"Progress: {details['current_position']['progress']:.1f}%")
    
    print(f"\nDetected waves:")
    for wave in details['waves'][:5]:  # Показываем первые 5 волн
        print(f"  Wave {wave['wave']}: {wave['type']}, "
              f"{wave['start_price']:.2f} → {wave['end_price']:.2f}")
    
    print("\n" + "="*60)
    
    return result


if __name__ == "__main__":
    test_elliott_analyzer()