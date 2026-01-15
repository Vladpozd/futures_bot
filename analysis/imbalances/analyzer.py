"""
Анализатор имбалансов (дисбалансы объема/цены).
Вес: 10% в общей вероятности.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.logger import log


class ImbalanceType(Enum):
    """Типы имбалансов"""
    VOLUME_IMBALANCE = "Имбаланс объема"
    PRICE_IMBALANCE = "Имбаланс цены"
    DELTA_IMBALANCE = "Имбаланс дельты"
    CUMULATIVE_DELTA = "Кумулятивная дельта"


class ImbalanceDirection(Enum):
    """Направление имбаланса"""
    BULLISH = "Бычий"    # Покупатели сильнее
    BEARISH = "Медвежий" # Продавцы сильнее
    NEUTRAL = "Нейтральный"


@dataclass
class Imbalance:
    """Обнаруженный имбаланс"""
    imbalance_type: ImbalanceType
    direction: ImbalanceDirection
    strength: float  # Сила имбаланса 0-100%
    start_idx: int
    end_idx: int
    details: Dict[str, Any]


class ImbalanceAnalyzer:
    """
    Анализатор имбалансов.
    Обнаруживает дисбалансы между спросом и предложением.
    """
    
    def __init__(self):
        self.min_data_points = 10
        self.imbalance_threshold = 0.6  # Порог для определения имбаланса (60%)
        
        log.info("Инициализация анализатора имбалансов")
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Проанализировать имбалансы на данных.
        
        Args:
            df: DataFrame с ценами и объемом (колонки: high, low, close, volume)
            
        Returns:
            Словарь с результатами анализа имбалансов
        """
        if len(df) < self.min_data_points:
            return self._get_empty_result()
        
        try:
            # Получаем данные
            opens = df['open'].values if 'open' in df.columns else df['close'].shift(1).values
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
            
            # 1. Анализируем имбаланс объема
            volume_imbalances = self._analyze_volume_imbalance(closes, volumes)
            
            # 2. Анализируем имбаланс цены
            price_imbalances = self._analyze_price_imbalance(opens, highs, lows, closes)
            
            # 3. Анализируем кумулятивную дельту (упрощенно)
            delta_imbalances = self._analyze_delta_imbalance(opens, closes, volumes)
            
            # 4. Объединяем все имбалансы
            all_imbalances = volume_imbalances + price_imbalances + delta_imbalances
            
            # 5. Определяем общий сигнал
            signal, signal_strength = self._generate_signal(all_imbalances)
            
            # 6. Рассчитываем уверенность и score
            confidence = self._calculate_confidence(all_imbalances)
            score = self._calculate_score(confidence, signal_strength, all_imbalances)
            
            result = {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence / 100)),
                'signal': signal,
                'details': {
                    'total_imbalances': len(all_imbalances),
                    'recent_imbalances': self._get_recent_imbalances(all_imbalances),
                    'signal_strength': signal_strength,
                    'volume_imbalances': len(volume_imbalances),
                    'price_imbalances': len(price_imbalances),
                    'delta_imbalances': len(delta_imbalances),
                    'bullish_count': sum(1 for i in all_imbalances if i.direction == ImbalanceDirection.BULLISH),
                    'bearish_count': sum(1 for i in all_imbalances if i.direction == ImbalanceDirection.BEARISH)
                }
            }
            
            log.debug(f"Анализ имбалансов: найдено {len(all_imbalances)} имбалансов, "
                     f"сигнал: {signal}, сила: {signal_strength:.1f}%")
            
            return result
            
        except Exception as e:
            log.error(f"Ошибка анализа имбалансов: {e}")
            return self._get_empty_result()
    
    def _analyze_volume_imbalance(self, closes: np.ndarray, 
                                volumes: np.ndarray) -> List[Imbalance]:
        """Анализировать имбаланс объема"""
        imbalances = []
        
        if len(closes) < 5:
            return imbalances
        
        # Анализируем объем на повышающихся и понижающихся свечах
        for i in range(1, len(closes)):
            price_change = closes[i] - closes[i-1]
            volume = volumes[i]
            
            # Определяем тип свечи
            if price_change > 0:
                # Бычья свеча
                # Ищем имбаланс: большой объем на бычьей свече
                if volume > np.mean(volumes[max(0, i-5):i]) * 1.5:
                    imbalance = Imbalance(
                        imbalance_type=ImbalanceType.VOLUME_IMBALANCE,
                        direction=ImbalanceDirection.BULLISH,
                        strength=min(100, (volume / np.mean(volumes[max(0, i-5):i]) - 1) * 100),
                        start_idx=i-1,
                        end_idx=i,
                        details={
                            'price_change': price_change,
                            'volume': volume,
                            'avg_volume': np.mean(volumes[max(0, i-5):i]),
                            'volume_ratio': volume / np.mean(volumes[max(0, i-5):i])
                        }
                    )
                    imbalances.append(imbalance)
            
            elif price_change < 0:
                # Медвежья свеча
                # Ищем имбаланс: большой объем на медвежьей свече
                if volume > np.mean(volumes[max(0, i-5):i]) * 1.5:
                    imbalance = Imbalance(
                        imbalance_type=ImbalanceType.VOLUME_IMBALANCE,
                        direction=ImbalanceDirection.BEARISH,
                        strength=min(100, (volume / np.mean(volumes[max(0, i-5):i]) - 1) * 100),
                        start_idx=i-1,
                        end_idx=i,
                        details={
                            'price_change': price_change,
                            'volume': volume,
                            'avg_volume': np.mean(volumes[max(0, i-5):i]),
                            'volume_ratio': volume / np.mean(volumes[max(0, i-5):i])
                        }
                    )
                    imbalances.append(imbalance)
        
        return imbalances
    
    def _analyze_price_imbalance(self, opens: np.ndarray, highs: np.ndarray,
                               lows: np.ndarray, closes: np.ndarray) -> List[Imbalance]:
        """Анализировать имбаланс цены"""
        imbalances = []
        
        if len(closes) < 3:
            return imbalances
        
        # Анализируем соотношение тела свечи к теням
        for i in range(len(closes)):
            open_price = opens[i] if i < len(opens) else closes[i-1]
            high = highs[i]
            low = lows[i]
            close = closes[i]
            
            # Размер тела свечи
            body_size = abs(close - open_price)
            
            # Размер верхней тени
            upper_shadow = high - max(open_price, close)
            
            # Размер нижней тени
            lower_shadow = min(open_price, close) - low
            
            # Общий размер свечи
            total_size = high - low
            
            if total_size > 0:
                # Доля тела в общей свече
                body_ratio = body_size / total_size
                
                # Доли теней
                upper_ratio = upper_shadow / total_size
                lower_ratio = lower_shadow / total_size
                
                # Определяем имбаланс
                if close > open_price:  # Бычья свеча
                    if body_ratio > 0.7 and lower_ratio < 0.1:
                        # Сильная бычья свеча с маленькой нижней тенью
                        imbalance = Imbalance(
                            imbalance_type=ImbalanceType.PRICE_IMBALANCE,
                            direction=ImbalanceDirection.BULLISH,
                            strength=min(100, body_ratio * 100),
                            start_idx=i,
                            end_idx=i,
                            details={
                                'body_ratio': body_ratio,
                                'upper_ratio': upper_ratio,
                                'lower_ratio': lower_ratio,
                                'is_bullish': True
                            }
                        )
                        imbalances.append(imbalance)
                
                elif close < open_price:  # Медвежья свеча
                    if body_ratio > 0.7 and upper_ratio < 0.1:
                        # Сильная медвежья свеча с маленькой верхней тенью
                        imbalance = Imbalance(
                            imbalance_type=ImbalanceType.PRICE_IMBALANCE,
                            direction=ImbalanceDirection.BEARISH,
                            strength=min(100, body_ratio * 100),
                            start_idx=i,
                            end_idx=i,
                            details={
                                'body_ratio': body_ratio,
                                'upper_ratio': upper_ratio,
                                'lower_ratio': lower_ratio,
                                'is_bullish': False
                            }
                        )
                        imbalances.append(imbalance)
        
        return imbalances
    
    def _analyze_delta_imbalance(self, opens: np.ndarray, closes: np.ndarray,
                               volumes: np.ndarray) -> List[Imbalance]:
        """Анализировать имбаланс дельты (упрощенный)"""
        imbalances = []
        
        if len(closes) < 5:
            return imbalances
        
        # Кумулятивная дельта (разница между объемом на покупку и продажу)
        # Упрощенная реализация: считаем, что если цена закрылась выше открытия,
        # то объем был преимущественно покупательский, и наоборот
        
        cumulative_delta = 0
        deltas = []
        
        for i in range(len(closes)):
            open_price = opens[i] if i < len(opens) else closes[i-1]
            close = closes[i]
            volume = volumes[i]
            
            if close > open_price:
                # Предполагаем, что 70% объема - покупка
                delta = volume * 0.7
                cumulative_delta += delta
            elif close < open_price:
                # Предполагаем, что 70% объема - продажа
                delta = -volume * 0.7
                cumulative_delta += delta
            else:
                delta = 0
            
            deltas.append(delta)
        
        # Анализируем кумулятивную дельту
        if len(deltas) >= 3:
            # Ищем значительные изменения в кумулятивной дельте
            for i in range(2, len(deltas)):
                recent_delta = sum(deltas[i-2:i+1])
                
                if abs(recent_delta) > np.mean(volumes[i-2:i+1]) * 0.5:
                    direction = ImbalanceDirection.BULLISH if recent_delta > 0 else ImbalanceDirection.BEARISH
                    
                    imbalance = Imbalance(
                        imbalance_type=ImbalanceType.CUMULATIVE_DELTA,
                        direction=direction,
                        strength=min(100, abs(recent_delta) / np.mean(volumes[i-2:i+1]) * 100),
                        start_idx=i-2,
                        end_idx=i,
                        details={
                            'delta_value': recent_delta,
                            'avg_volume': np.mean(volumes[i-2:i+1]),
                            'delta_ratio': abs(recent_delta) / np.mean(volumes[i-2:i+1])
                        }
                    )
                    imbalances.append(imbalance)
        
        return imbalances
    
    def _generate_signal(self, imbalances: List[Imbalance]) -> Tuple[str, float]:
        """Сгенерировать торговый сигнал на основе имбалансов"""
        if not imbalances:
            return "NEUTRAL", 30.0
        
        # Анализируем последние имбалансы (последние 5)
        recent_imbalances = imbalances[-5:] if len(imbalances) > 5 else imbalances
        
        # Подсчитываем бычьи и медвежьи имбалансы
        bullish_count = sum(1 for i in recent_imbalances if i.direction == ImbalanceDirection.BULLISH)
        bearish_count = sum(1 for i in recent_imbalances if i.direction == ImbalanceDirection.BEARISH)
        
        # Рассчитываем среднюю силу
        bullish_strength = np.mean([i.strength for i in recent_imbalances 
                                   if i.direction == ImbalanceDirection.BULLISH]) if bullish_count > 0 else 0
        bearish_strength = np.mean([i.strength for i in recent_imbalances 
                                   if i.direction == ImbalanceDirection.BEARISH]) if bearish_count > 0 else 0
        
        # Определяем сигнал
        if bullish_count > bearish_count and bullish_strength > 50:
            signal = "BUY"
            strength = min(100, bullish_strength * (bullish_count / len(recent_imbalances)))
        elif bearish_count > bullish_count and bearish_strength > 50:
            signal = "SELL"
            strength = min(100, bearish_strength * (bearish_count / len(recent_imbalances)))
        else:
            signal = "NEUTRAL"
            strength = max(bullish_strength, bearish_strength)
        
        # Учитываем силу последнего имбаланса
        if imbalances:
            last_imbalance = imbalances[-1]
            if signal != "NEUTRAL" and last_imbalance.direction.value == signal:
                # Усиливаем сигнал, если последний имбаланс в том же направлении
                strength = min(100, strength * 1.2)
            elif signal != "NEUTRAL" and last_imbalance.direction.value != signal:
                # Ослабляем сигнал, если последний имбаланс в противоположном направлении
                strength = max(30, strength * 0.8)
        
        return signal, strength
    
    def _calculate_confidence(self, imbalances: List[Imbalance]) -> float:
        """Рассчитать уверенность в анализе"""
        confidence = 30.0  # Базовая уверенность
        
        if not imbalances:
            return confidence
        
        # Увеличиваем уверенность за количество имбалансов
        confidence += min(25, len(imbalances) * 2)
        
        # Увеличиваем за силу имбалансов
        if imbalances:
            avg_strength = np.mean([i.strength for i in imbalances])
            confidence += min(25, avg_strength * 0.25)
        
        # Увеличиваем за согласованность направлений
        if len(imbalances) >= 3:
            recent = imbalances[-3:]
            directions = [i.direction for i in recent]
            
            if all(d == directions[0] for d in directions):
                confidence += 15  # Все последние имбалансы в одном направлении
            elif len(set(directions)) == 1:
                confidence += 10  # Два из трех в одном направлении
        
        return min(100.0, confidence)
    
    def _calculate_score(self, confidence: float, signal_strength: float,
                        imbalances: List[Imbalance]) -> float:
        """Рассчитать итоговый score (0-1)"""
        if not imbalances:
            return 0.5
        
        # Базовый score на основе уверенности и силы сигнала
        base_score = (confidence / 100 * 0.5) + (signal_strength / 100 * 0.5)
        
        # Корректируем на основе типа имбалансов
        if imbalances:
            # Имбалансы объема обычно более значимы
            volume_imbalances = [i for i in imbalances if i.imbalance_type == ImbalanceType.VOLUME_IMBALANCE]
            if volume_imbalances:
                avg_volume_strength = np.mean([i.strength for i in volume_imbalances])
                base_score = min(1.0, base_score * (1 + avg_volume_strength / 200))
        
        return min(1.0, max(0.0, base_score))
    
    def _get_recent_imbalances(self, imbalances: List[Imbalance]) -> List[Dict[str, Any]]:
        """Получить информацию о последних имбалансах"""
        recent = imbalances[-3:] if len(imbalances) > 3 else imbalances
        
        result = []
        for imb in recent:
            result.append({
                'type': imb.imbalance_type.value,
                'direction': imb.direction.value,
                'strength': imb.strength,
                'details': imb.details
            })
        
        return result
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Пустой результат при ошибке"""
        return {
            'score': 0.5,
            'confidence': 0.1,
            'signal': 'NEUTRAL',
            'details': {
                'total_imbalances': 0,
                'recent_imbalances': [],
                'signal_strength': 0,
                'volume_imbalances': 0,
                'price_imbalances': 0,
                'delta_imbalances': 0,
                'bullish_count': 0,
                'bearish_count': 0
            }
        }


# Глобальный экземпляр
imbalance_analyzer = ImbalanceAnalyzer()


def test_imbalance_analyzer():
    """Тест анализатора имбалансов"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ АНАЛИЗАТОРА ИМБАЛАНСОВ")
    print("="*60)
    
    # Создаем тестовые данные с имбалансом объема
    np.random.seed(42)
    
    # Цены с восходящим трендом
    n_points = 20
    trend = np.linspace(100, 110, n_points)
    noise = np.random.normal(0, 0.5, n_points)
    closes = trend + noise
    
    # Объемы с имбалансом
    volumes = np.random.normal(1000, 200, n_points)
    
    # Создаем имбаланс: большие объемы на бычьих свечах
    for i in range(5, 10):
        if closes[i] > closes[i-1]:
            volumes[i] = 3000  # Большой объем
    
    # Создаем DataFrame
    df = pd.DataFrame({
        'open': closes - np.random.random(n_points) * 0.5,
        'high': closes + np.random.random(n_points) * 0.5,
        'low': closes - np.random.random(n_points) * 0.5,
        'close': closes,
        'volume': volumes
    })
    
    analyzer = ImbalanceAnalyzer()
    result = analyzer.analyze(df)
    
    print(f"Score: {result['score']:.2f}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Signal: {result['signal']}")
    
    details = result['details']
    print(f"\nTotal imbalances: {details['total_imbalances']}")
    print(f"Bullish imbalances: {details['bullish_count']}")
    print(f"Bearish imbalances: {details['bearish_count']}")
    print(f"Signal strength: {details['signal_strength']:.1f}%")
    
    if details['recent_imbalances']:
        print(f"\nRecent imbalances:")
        for i, imb in enumerate(details['recent_imbalances'], 1):
            print(f"  {i}. Type: {imb['type']}, "
                  f"Direction: {imb['direction']}, "
                  f"Strength: {imb['strength']:.1f}%")
    
    print("\n" + "="*60)
    
    return result


if __name__ == "__main__":
    test_imbalance_analyzer()