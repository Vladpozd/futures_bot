"""
Расчет всех технических индикаторов.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from utils.logger import log


@dataclass
class IndicatorResult:
    """Результат расчета индикатора"""
    name: str
    value: float
    signal: str  # BUY, SELL, NEUTRAL
    strength: float  # 0-100


class TechnicalIndicators:
    """Калькулятор технических индикаторов"""
    
    def __init__(self):
        log.info("Инициализация технических индикаторов")
    
    def calculate_all(self, df: pd.DataFrame) -> Dict[str, IndicatorResult]:
        """Рассчитать все индикаторы"""
        results = {}
        
        # Скользящие средние
        results.update(self._calculate_moving_averages(df))
        
        # RSI
        results.update(self._calculate_rsi(df))
        
        # Уровни поддержки/сопротивления
        results.update(self._calculate_support_resistance(df))
        
        # Трендовые линии
        results.update(self._calculate_trend_lines(df))
        
        return results
    
    def _calculate_moving_averages(self, df: pd.DataFrame, 
                                  periods: List[int] = None) -> Dict[str, IndicatorResult]:
        """Рассчитать скользящие средние"""
        if periods is None:
            periods = [5, 10, 20, 50, 100, 200]
        
        results = {}
        
        # Сначала рассчитываем MA
        ma_values = {}
        for period in periods:
            if len(df) >= period:
                ma_key = f"MA_{period}"
                ma_values[ma_key] = df['close'].rolling(window=period).mean().iloc[-1]
        
        # Анализируем пересечения
        if len(ma_values) >= 2:
            ma_keys = sorted(ma_values.keys(), 
                           key=lambda x: int(x.split('_')[1]))
            
            # Бычий сигнал: короткие MA выше длинных
            short_ma = ma_values.get('MA_5', 0)
            long_ma = ma_values.get('MA_20', 0)
            
            if short_ma > long_ma:
                signal = "BUY"
                strength = min(100, abs(short_ma - long_ma) / long_ma * 1000)
            elif short_ma < long_ma:
                signal = "SELL"
                strength = min(100, abs(short_ma - long_ma) / long_ma * 1000)
            else:
                signal = "NEUTRAL"
                strength = 0
            
            results['MA_CROSS'] = IndicatorResult(
                name="MA Cross",
                value=short_ma - long_ma,
                signal=signal,
                strength=strength
            )
        
        # Добавляем все MA в результаты
        for key, value in ma_values.items():
            results[key] = IndicatorResult(
                name=key,
                value=value,
                signal="NEUTRAL",
                strength=0
            )
        
        return results
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict[str, IndicatorResult]:
        """Рассчитать RSI"""
        if len(df) < period + 1:
            return {}
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        # Определяем сигнал
        if current_rsi > 70:
            signal = "SELL"
            strength = min(100, (current_rsi - 70) * 5)
        elif current_rsi < 30:
            signal = "BUY"
            strength = min(100, (30 - current_rsi) * 5)
        else:
            signal = "NEUTRAL"
            strength = 0
        
        # Дивергенция
        divergence_signal = self._check_rsi_divergence(df, rsi)
        if divergence_signal:
            signal = divergence_signal
            strength = 70
        
        return {
            'RSI': IndicatorResult(
                name="RSI",
                value=current_rsi,
                signal=signal,
                strength=strength
            )
        }
    
    def _check_rsi_divergence(self, df: pd.DataFrame, rsi: pd.Series) -> Optional[str]:
        """Проверить дивергенцию RSI"""
        if len(df) < 20:
            return None
        
        # Берем последние 20 свечей для анализа
        prices = df['close'].iloc[-20:].values
        rsi_values = rsi.iloc[-20:].values
        
        # Ищем максимумы цен и RSI
        price_highs = []
        rsi_highs = []
        
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                price_highs.append((i, prices[i]))
            if rsi_values[i] > rsi_values[i-1] and rsi_values[i] > rsi_values[i+1]:
                rsi_highs.append((i, rsi_values[i]))
        
        # Ищем медвежью дивергенцию (цена делает новые максимумы, RSI - нет)
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            last_price_high = price_highs[-1][1]
            prev_price_high = price_highs[-2][1]
            last_rsi_high = rsi_highs[-1][1]
            prev_rsi_high = rsi_highs[-2][1]
            
            if last_price_high > prev_price_high and last_rsi_high < prev_rsi_high:
                return "SELL"
        
        # Ищем бычью дивергенцию (цена делает новые минимумы, RSI - нет)
        price_lows = []
        rsi_lows = []
        
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                price_lows.append((i, prices[i]))
            if rsi_values[i] < rsi_values[i-1] and rsi_values[i] < rsi_values[i+1]:
                rsi_lows.append((i, rsi_values[i]))
        
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            last_price_low = price_lows[-1][1]
            prev_price_low = price_lows[-2][1]
            last_rsi_low = rsi_lows[-1][1]
            prev_rsi_low = rsi_lows[-2][1]
            
            if last_price_low < prev_price_low and last_rsi_low > prev_rsi_low:
                return "BUY"
        
        return None
    
    def _calculate_support_resistance(self, df: pd.DataFrame, 
                                     window: int = 20) -> Dict[str, IndicatorResult]:
        """Определить уровни поддержки и сопротивления"""
        if len(df) < window:
            return {}
        
        recent_data = df.iloc[-window:]
        
        # Ищем уровни поддержки (локальные минимумы)
        support_levels = []
        for i in range(1, len(recent_data) - 1):
            low = recent_data['low'].iloc[i]
            if (low < recent_data['low'].iloc[i-1] and 
                low < recent_data['low'].iloc[i+1]):
                support_levels.append(low)
        
        # Ищем уровни сопротивления (локальные максимумы)
        resistance_levels = []
        for i in range(1, len(recent_data) - 1):
            high = recent_data['high'].iloc[i]
            if (high > recent_data['high'].iloc[i-1] and 
                high > recent_data['high'].iloc[i+1]):
                resistance_levels.append(high)
        
        # Убираем дубликаты и сортируем
        support_levels = sorted(list(set(support_levels)))
        resistance_levels = sorted(list(set(resistance_levels)))
        
        # Текущая цена
        current_price = df['close'].iloc[-1]
        
        # Находим ближайшие уровни
        nearest_support = None
        nearest_resistance = None
        
        for level in support_levels:
            if level < current_price:
                nearest_support = level
        
        for level in resistance_levels:
            if level > current_price:
                nearest_resistance = level
                break
        
        # Определяем сигнал на основе расстояния до уровней
        signal = "NEUTRAL"
        strength = 0
        
        if nearest_support and nearest_resistance:
            price_range = nearest_resistance - nearest_support
            distance_to_support = current_price - nearest_support
            distance_to_resistance = nearest_resistance - current_price
            
            # Если ближе к сопротивлению - сигнал на продажу
            if distance_to_resistance < price_range * 0.3:
                signal = "SELL"
                strength = min(100, (1 - distance_to_resistance / price_range) * 100)
            # Если ближе к поддержке - сигнал на покупку
            elif distance_to_support < price_range * 0.3:
                signal = "BUY"
                strength = min(100, (1 - distance_to_support / price_range) * 100)
        
        return {
            'SR_LEVELS': IndicatorResult(
                name="Support/Resistance",
                value=current_price,
                signal=signal,
                strength=strength
            ),
            'NEAREST_SUPPORT': IndicatorResult(
                name="Nearest Support",
                value=nearest_support or 0,
                signal="NEUTRAL",
                strength=0
            ),
            'NEAREST_RESISTANCE': IndicatorResult(
                name="Nearest Resistance",
                value=nearest_resistance or 0,
                signal="NEUTRAL",
                strength=0
            )
        }
    
    def _calculate_trend_lines(self, df: pd.DataFrame) -> Dict[str, IndicatorResult]:
        """Определить трендовые линии"""
        if len(df) < 10:
            return {}
        
        # Упрощенный анализ тренда по скользящим средним
        ma_short = df['close'].rolling(window=10).mean().iloc[-1]
        ma_long = df['close'].rolling(window=30).mean().iloc[-1]
        
        # Анализируем наклон тренда
        recent_prices = df['close'].iloc[-10:].values
        x = np.arange(len(recent_prices))
        
        try:
            slope, intercept = np.polyfit(x, recent_prices, 1)
            
            # Определяем силу тренда
            trend_strength = abs(slope) * 100 / np.mean(recent_prices)
            
            if slope > 0:
                signal = "BUY"
                strength = min(100, trend_strength * 10)
            elif slope < 0:
                signal = "SELL"
                strength = min(100, abs(trend_strength) * 10)
            else:
                signal = "NEUTRAL"
                strength = 0
            
            return {
                'TREND': IndicatorResult(
                    name="Trend Direction",
                    value=slope,
                    signal=signal,
                    strength=strength
                )
            }
            
        except:
            return {}
    
    def identify_zones(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """
        Определить зоны покупок и продаж
        Возвращает ценовые уровни для зон
        """
        zones = {
            'buy_zones': [],
            'sell_zones': []
        }
        
        if len(df) < 50:
            return zones
        
        # Используем скользящие средние как динамические зоны
        ma_20 = df['close'].rolling(window=20).mean().iloc[-1]
        ma_50 = df['close'].rolling(window=50).mean().iloc[-1]
        ma_200 = df['close'].rolling(window=200).mean().iloc[-1]
        
        current_price = df['close'].iloc[-1]
        
        # Зона покупок: ниже MA20 и MA50
        if current_price < ma_20 and current_price < ma_50:
            zones['buy_zones'].extend([ma_20, ma_50])
        
        # Зона продаж: выше MA20 и MA50
        if current_price > ma_20 and current_price > ma_50:
            zones['sell_zones'].extend([ma_20, ma_50])
        
        # Дополнительные зоны на основе поддержки/сопротивления
        sr_result = self._calculate_support_resistance(df)
        support = sr_result.get('NEAREST_SUPPORT')
        resistance = sr_result.get('NEAREST_RESISTANCE')
        
        if support and support.value > 0:
            zones['buy_zones'].append(support.value)
        
        if resistance and resistance.value > 0:
            zones['sell_zones'].append(resistance.value)
        
        return zones


# Глобальный экземпляр
tech_indicators = TechnicalIndicators()