"""
Анализатор психологических уровней.
Определяет круглые числа и важные ценовые уровни.
"""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from dataclasses import dataclass

from utils.logger import log


@dataclass
class PsychologicalLevel:
    """Психологический уровень"""
    price: float
    strength: float  # Сила уровня 0-1
    type: str  # ROUND, HALF, QUARTER, SUPPORT, RESISTANCE
    description: str


class PsychologicalLevels:
    """Анализатор психологических уровней."""
    
    def __init__(self):
        self.round_numbers_cache: Dict[float, Dict] = {}
        log.info("Инициализация анализатора психологических уровней")
    
    def find_psychological_levels(self, 
                                 current_price: float, 
                                 recent_prices: List[float],
                                 volatility: float = 0.01) -> List[PsychologicalLevel]:
        """
        Найти психологические уровни вокруг текущей цены.
        
        Args:
            current_price: Текущая цена
            recent_prices: Список последних цен
            volatility: Волатильность для определения зоны
        
        Returns:
            Список психологических уровней
        """
        levels = []
        
        # Основные круглые числа
        round_numbers = self._find_round_numbers(current_price)
        levels.extend(round_numbers)
        
        # Половинные уровни (50, 150, 250 и т.д.)
        half_levels = self._find_half_levels(current_price)
        levels.extend(half_levels)
        
        # Четвертные уровни (25, 75, 125 и т.д.)
        quarter_levels = self._find_quarter_levels(current_price)
        levels.extend(quarter_levels)
        
        # Уровни на основе истории
        historical_levels = self._find_historical_levels(recent_prices)
        levels.extend(historical_levels)
        
        # Фильтруем по близости к текущей цене
        relevant_levels = [
            level for level in levels 
            if abs(level.price - current_price) <= current_price * volatility * 3
        ]
        
        # Сортируем по силе
        relevant_levels.sort(key=lambda x: x.strength, reverse=True)
        
        return relevant_levels[:10]  # Возвращаем топ-10 уровней
    
    def get_psychological_levels(self, current_price: float, ticker: str) -> Dict[str, List[float]]:
        """
        Старый метод для совместимости с analyzer.py.
        Возвращает психологические уровни для заданной цены и тикера.
        
        Args:
            current_price: Текущая цена
            ticker: Тикер инструмента
            
        Returns:
            Словарь с уровнями ниже и выше текущей цены
        """
        try:
            # Генерируем искусственные исторические данные для анализа
            price_variation = current_price * 0.05  # 5% вариация
            recent_prices = [
                current_price - price_variation * 0.8,
                current_price - price_variation * 0.4,
                current_price + price_variation * 0.4,
                current_price + price_variation * 0.8,
                current_price
            ]
            
            # Получаем психологические уровни
            levels = self.find_psychological_levels(current_price, recent_prices)
            
            # Разделяем на уровни ниже и выше текущей цены
            below = [level.price for level in levels if level.price < current_price]
            above = [level.price for level in levels if level.price > current_price]
            
            # Сортируем и ограничиваем количество
            below.sort(reverse=True)  # Ближайшие снизу сначала
            above.sort()  # Ближайшие сверху сначала
            
            return {
                'below': below[:3],  # Топ-3 уровня снизу
                'above': above[:3],  # Топ-3 уровня сверху
                'all_levels': [{'price': level.price, 'type': level.type, 'strength': level.strength} 
                              for level in levels[:5]]
            }
            
        except Exception as e:
            log.error(f"Ошибка в get_psychological_levels: {e}")
            return {'below': [], 'above': [], 'all_levels': []}
    
    def is_psychological_level(self, price: float) -> bool:
        """
        Проверяет, является ли цена психологическим уровнем.
        Для совместимости с analyzer.py.
        """
        try:
            # Проверяем, является ли цена круглым числом
            tolerance = price * 0.001  # 0.1% допуск
            
            # Проверяем круглые числа (100, 1000 и т.д.)
            round_check = round(price, -2)  # Округляем до сотен
            if abs(price - round_check) <= tolerance:
                return True
            
            # Проверяем половинные уровни (50, 150 и т.д.)
            half_check = round(price - 50, -2) + 50
            if abs(price - half_check) <= tolerance:
                return True
            
            return False
            
        except Exception as e:
            log.error(f"Ошибка в is_psychological_level: {e}")
            return False
    
    def _find_round_numbers(self, current_price: float) -> List[PsychologicalLevel]:
        """Найти круглые числа."""
        levels = []
        
        # Определяем порядок величины
        if current_price == 0:
            return levels
        
        order = 10 ** (int(np.log10(current_price)) - 1)
        
        # Ближайшие круглые числа
        base = round(current_price / (order * 10)) * (order * 10)
        
        for i in range(-3, 4):
            round_price = base + i * (order * 10)
            distance = abs(round_price - current_price) / current_price
            
            # Сила зависит от расстояния и "круглости"
            if distance < 0.1:  # Не дальше 10%
                strength = max(0, 1 - distance * 10)
                
                # Особо сильные уровни (100, 1000 и т.д.)
                if round_price % (order * 100) == 0:
                    strength = min(1.0, strength * 1.5)
                
                level = PsychologicalLevel(
                    price=round_price,
                    strength=strength,
                    type="ROUND",
                    description=f"Круглое число {round_price:.0f}"
                )
                levels.append(level)
        
        return levels
    
    def _find_half_levels(self, current_price: float) -> List[PsychologicalLevel]:
        """Найти половинные уровни (50, 150, 250 и т.д.)."""
        levels = []
        
        if current_price == 0:
            return levels
        
        order = 10 ** (int(np.log10(current_price)) - 1)
        base = round(current_price / (order * 10)) * (order * 10)
        
        for i in range(-3, 4):
            half_price = base + (i * (order * 10)) + (order * 5)
            distance = abs(half_price - current_price) / current_price
            
            if distance < 0.1:
                strength = max(0, 0.8 - distance * 8)  # Чуть слабее круглых
                
                level = PsychologicalLevel(
                    price=half_price,
                    strength=strength,
                    type="HALF",
                    description=f"Половинный уровень {half_price:.0f}"
                )
                levels.append(level)
        
        return levels
    
    def _find_quarter_levels(self, current_price: float) -> List[PsychologicalLevel]:
        """Найти четвертные уровни (25, 75, 125 и т.д.)."""
        levels = []
        
        if current_price == 0:
            return levels
        
        order = 10 ** (int(np.log10(current_price)) - 1)
        base = round(current_price / (order * 10)) * (order * 10)
        
        quarter_points = [2.5, 7.5]  # 25% и 75% от порядка
        
        for i in range(-3, 4):
            for quarter in quarter_points:
                quarter_price = base + (i * (order * 10)) + (order * quarter)
                distance = abs(quarter_price - current_price) / current_price
                
                if distance < 0.1:
                    strength = max(0, 0.6 - distance * 6)  # Еще слабее
                    
                    level = PsychologicalLevel(
                        price=quarter_price,
                        strength=strength,
                        type="QUARTER",
                        description=f"Четвертной уровень {quarter_price:.0f}"
                    )
                    levels.append(level)
        
        return levels
    
    def _find_historical_levels(self, recent_prices: List[float]) -> List[PsychologicalLevel]:
        """Найти уровни поддержки/сопротивления на основе истории."""
        if not recent_prices or len(recent_prices) < 20:
            return []
        
        levels = []
        prices = np.array(recent_prices)
        
        # Находим локальные минимумы и максимумы
        window = max(5, len(prices) // 10)
        
        for i in range(window, len(prices) - window):
            # Проверяем локальный минимум
            if (prices[i] == min(prices[i-window:i+window+1]) and 
                prices[i] < prices[i-1] and prices[i] < prices[i+1]):
                
                # Проверяем, сколько раз цена отскакивала от этого уровня
                bounce_count = self._count_bounces(prices, prices[i], window=window)
                
                if bounce_count >= 2:
                    strength = min(1.0, bounce_count / 5)
                    
                    level = PsychologicalLevel(
                        price=float(prices[i]),
                        strength=strength,
                        type="SUPPORT",
                        description=f"Уровень поддержки (отскоков: {bounce_count})"
                    )
                    levels.append(level)
            
            # Проверяем локальный максимум
            if (prices[i] == max(prices[i-window:i+window+1]) and 
                prices[i] > prices[i-1] and prices[i] > prices[i+1]):
                
                bounce_count = self._count_bounces(prices, prices[i], window=window)
                
                if bounce_count >= 2:
                    strength = min(1.0, bounce_count / 5)
                    
                    level = PsychologicalLevel(
                        price=float(prices[i]),
                        strength=strength,
                        type="RESISTANCE",
                        description=f"Уровень сопротивления (отскоков: {bounce_count})"
                    )
                    levels.append(level)
        
        return levels
    
    def _count_bounces(self, prices: np.ndarray, level: float, window: int = 5) -> int:
        """Посчитать количество отскоков от уровня."""
        bounce_count = 0
        tolerance = level * 0.005  # 0.5% допуск
        
        for i in range(window, len(prices) - window):
            # Проверяем подход к уровню
            if abs(prices[i] - level) <= tolerance:
                # Проверяем отскок
                prev_trend = np.mean(prices[i-window:i]) - level
                next_trend = np.mean(prices[i+1:i+window+1]) - level
                
                # Отскок вверх от поддержки
                if level < np.mean(prices[i-window:i]) and next_trend > 0:
                    bounce_count += 1
                # Отскок вниз от сопротивления
                elif level > np.mean(prices[i-window:i]) and next_trend < 0:
                    bounce_count += 1
        
        return bounce_count
    
    def analyze_price_action(self,
                           current_price: float,
                           recent_prices: List[float]) -> Dict[str, Any]:
        """
        Проанализировать поведение цены относительно психологических уровней.
        
        Returns:
            Словарь с анализом
        """
        levels = self.find_psychological_levels(current_price, recent_prices)
        
        if not levels:
            return {
                'has_strong_levels': False,
                'nearest_level': None,
                'action': 'NEUTRAL',
                'levels': []
            }
        
        # Находим ближайший уровень
        nearest_level = min(levels, key=lambda x: abs(x.price - current_price))
        distance_percent = abs(nearest_level.price - current_price) / current_price * 100
        
        # Определяем действие
        action = 'NEUTRAL'
        if distance_percent < 0.5:  # Очень близко к уровню
            if current_price > nearest_level.price:
                action = 'RESISTANCE_TEST'
            else:
                action = 'SUPPORT_TEST'
        elif distance_percent < 2.0:  # Близко к уровню
            action = 'APPROACHING_LEVEL'
        
        # Сильные уровни (сила > 0.7)
        strong_levels = [l for l in levels if l.strength > 0.7]
        
        return {
            'has_strong_levels': len(strong_levels) > 0,
            'strong_levels_count': len(strong_levels),
            'nearest_level': {
                'price': nearest_level.price,
                'type': nearest_level.type,
                'strength': nearest_level.strength,
                'distance_percent': distance_percent
            },
            'action': action,
            'levels': [
                {
                    'price': level.price,
                    'type': level.type,
                    'strength': level.strength,
                    'description': level.description
                }
                for level in levels[:5]  # Только топ-5
            ]
        }
    
    def is_breakout_likely(self,
                          current_price: float,
                          recent_prices: List[float],
                          volume_trend: str = 'NEUTRAL') -> Dict[str, Any]:
        """
        Оценить вероятность пробоя психологического уровня.
        
        Args:
            current_price: Текущая цена
            recent_prices: Последние цены
            volume_trend: Тренд объема (INCREASING, DECREASING, NEUTRAL)
        
        Returns:
            Словарь с оценкой пробоя
        """
        levels = self.find_psychological_levels(current_price, recent_prices)
        
        if not levels:
            return {
                'breakout_likely': False,
                'probability': 0.0,
                'direction': 'NONE',
                'reason': 'Нет значимых уровней'
            }
        
        nearest_level = min(levels, key=lambda x: abs(x.price - current_price))
        distance_percent = abs(nearest_level.price - current_price) / current_price * 100
        
        # Базовая вероятность пробоя
        base_probability = 0.0
        
        # Факторы, увеличивающие вероятность пробоя
        if distance_percent < 0.3:  # Очень близко
            base_probability += 0.4
        elif distance_percent < 1.0:  # Близко
            base_probability += 0.2
        
        # Сила уровня (чем слабее, тем вероятнее пробой)
        if nearest_level.strength < 0.3:
            base_probability += 0.3
        elif nearest_level.strength < 0.6:
            base_probability += 0.15
        
        # Объем
        if volume_trend == 'INCREASING':
            base_probability += 0.2
        elif volume_trend == 'DECREASING':
            base_probability -= 0.1
        
        # Определяем направление
        direction = 'UP' if current_price > nearest_level.price else 'DOWN'
        
        # Корректируем направление для типов уровней
        if nearest_level.type == 'SUPPORT' and direction == 'DOWN':
            base_probability *= 0.7  # Меньше вероятность пробоя поддержки вниз
        elif nearest_level.type == 'RESISTANCE' and direction == 'UP':
            base_probability *= 0.7  # Меньше вероятность пробоя сопротивления вверх
        
        # Ограничиваем вероятность
        probability = max(0.0, min(1.0, base_probability))
        
        return {
            'breakout_likely': probability > 0.5,
            'probability': probability,
            'direction': direction,
            'nearest_level': {
                'price': nearest_level.price,
                'type': nearest_level.type,
                'strength': nearest_level.strength
            },
            'distance_percent': distance_percent
        }


# Глобальный экземпляр
psychological_levels = PsychologicalLevels()