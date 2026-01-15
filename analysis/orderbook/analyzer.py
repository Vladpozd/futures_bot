"""
Анализатор стакана (Level 2 данных).
Вес: 10% в общей вероятности.
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.logger import log
from core.api_client import api_client


class OrderBookImbalance(Enum):
    """Типы имбалансов в стакане"""
    BID_DOMINANCE = "Доминирование покупателей"
    ASK_DOMINANCE = "Доминирование продавцов"
    BALANCED = "Сбалансированный"
    WALL_DETECTED = "Обнаружена стена"
    SPREAD_WIDE = "Широкий спред"


class MarketMakerAction(Enum):
    """Действия маркет-мейкеров"""
    ACCUMULATING = "Накопление позиции"
    DISTRIBUTING = "Распределение позиции"
    SUPPORTING = "Поддержка уровня"
    RESISTING = "Сопротивление уровню"
    FLUSHING = "Вымывание стоп-лоссов"
    UNKNOWN = "Неизвестно"


@dataclass
class OrderBookAnalysis:
    """Анализ стакана"""
    spread_percent: float  # Спред в %
    bid_volume: float      # Общий объем на покупку
    ask_volume: float      # Общий объем на продажу
    volume_imbalance: float  # Имбаланс объема (%)
    support_levels: List[float]  # Уровни поддержки
    resistance_levels: List[float]  # Уровни сопротивления
    market_maker_actions: List[MarketMakerAction]
    order_book_imbalance: OrderBookImbalance


class OrderBookAnalyzer:
    """
    Анализатор стакана (Level 2 данных).
    Анализирует глубину рынка и действия маркет-мейкеров.
    """
    
    def __init__(self):
        self.levels_to_analyze = 10  # Сколько уровней анализировать
        self.imbalance_threshold = 0.3  # Порог имбаланса (30%)
        self.wall_threshold = 5.0  # Порог для определения "стены" (в 5 раз больше среднего)
        
        log.info("Инициализация анализатора стакана")
    
    def analyze(self, ticker: str) -> Dict[str, Any]:
        """
        Проанализировать стакан для инструмента.
        
        Args:
            ticker: Тикер инструмента
            
        Returns:
            Словарь с результатами анализа стакана
        """
        try:
            # 1. Получаем данные стакана через API
            order_book_data = self._get_order_book_data(ticker)
            
            if not order_book_data:
                log.warning(f"Не удалось получить данные стакана для {ticker}")
                return self._get_empty_result()
            
            # 2. Анализируем стакан
            analysis = self._analyze_order_book(order_book_data)
            
            # 3. Определяем действия маркет-мейкеров
            market_maker_actions = self._detect_market_maker_actions(order_book_data, analysis)
            
            # 4. Генерируем торговый сигнал
            signal, signal_strength = self._generate_signal(analysis, market_maker_actions)
            
            # 5. Рассчитываем уверенность и score
            confidence = self._calculate_confidence(analysis, market_maker_actions)
            score = self._calculate_score(confidence, signal_strength, analysis)
            
            result = {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence / 100)),
                'signal': signal,
                'details': {
                    'spread_percent': analysis.spread_percent,
                    'volume_imbalance': analysis.volume_imbalance,
                    'order_book_imbalance': analysis.order_book_imbalance.value,
                    'market_maker_actions': [a.value for a in market_maker_actions],
                    'support_levels': analysis.support_levels[:3],  # Топ-3 уровня поддержки
                    'resistance_levels': analysis.resistance_levels[:3],  # Топ-3 уровня сопротивления
                    'bid_volume': analysis.bid_volume,
                    'ask_volume': analysis.ask_volume,
                    'signal_strength': signal_strength
                }
            }
            
            log.debug(f"Анализ стакана {ticker}: спред {analysis.spread_percent:.2f}%, "
                     f"имбаланс {analysis.volume_imbalance:+.1f}%, сигнал: {signal}")
            
            return result
            
        except Exception as e:
            log.error(f"Ошибка анализа стакана {ticker}: {e}")
            return self._get_empty_result()
    
    def _get_order_book_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Получить данные стакана через API"""
        try:
            # В реальной реализации здесь будет запрос к API Тинькофф
            # Для MVP возвращаем заглушку
            
            # Заглушка: симулируем данные стакана
            return self._simulate_order_book_data()
            
        except Exception as e:
            log.error(f"Ошибка получения данных стакана: {e}")
            return None
    
    def _simulate_order_book_data(self) -> Dict[str, Any]:
        """Сгенерировать тестовые данные стакана"""
        np.random.seed(42)
        
        # Генерируем уровни покупки (bid)
        bid_prices = []
        bid_volumes = []
        
        current_price = 100.0
        for i in range(self.levels_to_analyze):
            price = current_price * (1 - (i + 1) * 0.001)  # Каждый уровень на 0.1% ниже
            volume = np.random.uniform(10, 100)
            
            # Создаем "стену" на определенном уровне
            if i == 2:
                volume = 500  # Большой объем - стена
            
            bid_prices.append(price)
            bid_volumes.append(volume)
        
        # Генерируем уровни продажи (ask)
        ask_prices = []
        ask_volumes = []
        
        for i in range(self.levels_to_analyze):
            price = current_price * (1 + (i + 1) * 0.001)  # Каждый уровень на 0.1% выше
            volume = np.random.uniform(10, 100)
            
            # Создаем "стену" на определенном уровне
            if i == 3:
                volume = 400  # Большой объем - стена
            
            ask_prices.append(price)
            ask_volumes.append(volume)
        
        return {
            'bids': list(zip(bid_prices, bid_volumes)),
            'asks': list(zip(ask_prices, ask_volumes)),
            'current_price': current_price,
            'timestamp': '2024-01-15T12:00:00'
        }
    
    def _analyze_order_book(self, order_book_data: Dict[str, Any]) -> OrderBookAnalysis:
        """Проанализировать данные стакана"""
        bids = order_book_data.get('bids', [])
        asks = order_book_data.get('asks', [])
        current_price = order_book_data.get('current_price', 0)
        
        # Рассчитываем спред
        if bids and asks:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = best_ask - best_bid
            spread_percent = (spread / current_price * 100) if current_price > 0 else 0
        else:
            spread_percent = 0
        
        # Суммируем объемы
        bid_volume = sum(volume for _, volume in bids)
        ask_volume = sum(volume for _, volume in asks)
        
        # Рассчитываем имбаланс объема
        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            volume_imbalance = ((bid_volume - ask_volume) / total_volume) * 100
        else:
            volume_imbalance = 0
        
        # Определяем уровни поддержки (большие объемы на покупку)
        support_levels = []
        for price, volume in bids:
            avg_volume = np.mean([v for _, v in bids])
            if volume > avg_volume * 2:  # Объем в 2 раза больше среднего
                support_levels.append((price, volume))
        
        support_levels.sort(key=lambda x: x[1], reverse=True)
        support_prices = [price for price, _ in support_levels[:3]]
        
        # Определяем уровни сопротивления (большие объемы на продажу)
        resistance_levels = []
        for price, volume in asks:
            avg_volume = np.mean([v for _, v in asks])
            if volume > avg_volume * 2:  # Объем в 2 раза больше среднего
                resistance_levels.append((price, volume))
        
        resistance_levels.sort(key=lambda x: x[1], reverse=True)
        resistance_prices = [price for price, _ in resistance_levels[:3]]
        
        # Определяем общий имбаланс стакана
        if volume_imbalance > self.imbalance_threshold * 100:
            order_book_imbalance = OrderBookImbalance.BID_DOMINANCE
        elif volume_imbalance < -self.imbalance_threshold * 100:
            order_book_imbalance = OrderBookImbalance.ASK_DOMINANCE
        elif spread_percent > 0.1:  # Спред более 0.1%
            order_book_imbalance = OrderBookImbalance.SPREAD_WIDE
        elif support_levels or resistance_levels:
            order_book_imbalance = OrderBookImbalance.WALL_DETECTED
        else:
            order_book_imbalance = OrderBookImbalance.BALANCED
        
        return OrderBookAnalysis(
            spread_percent=spread_percent,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            volume_imbalance=volume_imbalance,
            support_levels=support_prices,
            resistance_levels=resistance_prices,
            market_maker_actions=[],  # Заполнится позже
            order_book_imbalance=order_book_imbalance
        )
    
    def _detect_market_maker_actions(self, order_book_data: Dict[str, Any],
                                   analysis: OrderBookAnalysis) -> List[MarketMakerAction]:
        """Обнаружить действия маркет-мейкеров"""
        actions = []
        
        bids = order_book_data.get('bids', [])
        asks = order_book_data.get('asks', [])
        
        # 1. Проверяем накопление (большие объемы на покупку глубоко в стакане)
        if bids:
            deep_bids = bids[3:]  # Уровни глубже 3-го
            deep_bid_volumes = [volume for _, volume in deep_bids]
            
            if deep_bid_volumes:
                avg_deep_bid = np.mean(deep_bid_volumes)
                if avg_deep_bid > np.mean([v for _, v in bids[:3]]) * 1.5:
                    actions.append(MarketMakerAction.ACCUMULATING)
        
        # 2. Проверяем распределение (большие объемы на продажу глубоко в стакане)
        if asks:
            deep_asks = asks[3:]  # Уровни глубже 3-го
            deep_ask_volumes = [volume for _, volume in deep_asks]
            
            if deep_ask_volumes:
                avg_deep_ask = np.mean(deep_ask_volumes)
                if avg_deep_ask > np.mean([v for _, v in asks[:3]]) * 1.5:
                    actions.append(MarketMakerAction.DISTRIBUTING)
        
        # 3. Проверяем поддержку/сопротивление (стены)
        if analysis.support_levels:
            actions.append(MarketMakerAction.SUPPORTING)
        
        if analysis.resistance_levels:
            actions.append(MarketMakerAction.RESISTING)
        
        # 4. Проверяем вымывание стоп-лоссов
        # (большие объемы на экстремальных уровнях)
        if bids and asks:
            extreme_bid = bids[-1][1] if bids else 0
            extreme_ask = asks[-1][1] if asks else 0
            
            avg_bid = np.mean([v for _, v in bids])
            avg_ask = np.mean([v for _, v in asks])
            
            if extreme_bid > avg_bid * 3 or extreme_ask > avg_ask * 3:
                actions.append(MarketMakerAction.FLUSHING)
        
        if not actions:
            actions.append(MarketMakerAction.UNKNOWN)
        
        return actions
    
    def _generate_signal(self, analysis: OrderBookAnalysis,
                        market_maker_actions: List[MarketMakerAction]) -> Tuple[str, float]:
        """Сгенерировать торговый сигнал на основе стакана"""
        # Базовый сигнал на основе имбаланса объема
        if analysis.volume_imbalance > self.imbalance_threshold * 100:
            base_signal = "BUY"
            base_strength = min(100, analysis.volume_imbalance)
        elif analysis.volume_imbalance < -self.imbalance_threshold * 100:
            base_signal = "SELL"
            base_strength = min(100, abs(analysis.volume_imbalance))
        else:
            base_signal = "NEUTRAL"
            base_strength = 30.0
        
        # Корректируем на основе действий маркет-мейкеров
        signal = base_signal
        strength = base_strength
        
        for action in market_maker_actions:
            if action == MarketMakerAction.ACCUMULATING:
                # Накопление - бычий признак
                if signal == "BUY":
                    strength = min(100, strength * 1.2)
                elif signal == "SELL":
                    strength = max(30, strength * 0.8)
            
            elif action == MarketMakerAction.DISTRIBUTING:
                # Распределение - медвежий признак
                if signal == "SELL":
                    strength = min(100, strength * 1.2)
                elif signal == "BUY":
                    strength = max(30, strength * 0.8)
            
            elif action == MarketMakerAction.SUPPORTING:
                # Поддержка - бычий признак
                if signal == "BUY":
                    strength = min(100, strength * 1.1)
            
            elif action == MarketMakerAction.RESISTING:
                # Сопротивление - медвежий признак
                if signal == "SELL":
                    strength = min(100, strength * 1.1)
            
            elif action == MarketMakerAction.FLUSHING:
                # Вымывание стоп-лоссов - обычно перед разворотом
                if signal != "NEUTRAL":
                    strength = max(40, strength * 0.7)
                    signal = "NEUTRAL"  # Лучше подождать
        
        # Корректируем на основе спреда
        if analysis.spread_percent > 0.15:  # Широкий спред
            strength = max(30, strength * 0.6)
            if signal != "NEUTRAL":
                signal = "NEUTRAL"  # При широком спреде лучше не торговать
        
        return signal, strength
    
    def _calculate_confidence(self, analysis: OrderBookAnalysis,
                            market_maker_actions: List[MarketMakerAction]) -> float:
        """Рассчитать уверенность в анализе"""
        confidence = 40.0  # Базовая уверенность для стакана
        
        # Увеличиваем уверенность за явный имбаланс
        if abs(analysis.volume_imbalance) > 20:
            confidence += 20
        
        # Увеличиваем за обнаруженные стены
        if analysis.support_levels or analysis.resistance_levels:
            confidence += 15
        
        # Увеличиваем за определенные действия маркет-мейкеров
        if market_maker_actions and market_maker_actions[0] != MarketMakerAction.UNKNOWN:
            confidence += 15
        
        # Уменьшаем за широкий спред
        if analysis.spread_percent > 0.1:
            confidence = max(30, confidence - 10)
        
        return min(100.0, confidence)
    
    def _calculate_score(self, confidence: float, signal_strength: float,
                        analysis: OrderBookAnalysis) -> float:
        """Рассчитать итоговый score (0-1)"""
        # Базовый score
        base_score = (confidence / 100 * 0.6) + (signal_strength / 100 * 0.4)
        
        # Корректируем на основе конкретных условий стакана
        if analysis.order_book_imbalance == OrderBookImbalance.WALL_DETECTED:
            # Стены обычно дают более надежные сигналы
            base_score = min(1.0, base_score * 1.1)
        
        if analysis.spread_percent < 0.05:  # Очень узкий спред
            base_score = min(1.0, base_score * 1.05)
        
        return min(1.0, max(0.0, base_score))
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """Пустой результат при ошибке"""
        return {
            'score': 0.5,
            'confidence': 0.1,
            'signal': 'NEUTRAL',
            'details': {
                'spread_percent': 0,
                'volume_imbalance': 0,
                'order_book_imbalance': OrderBookImbalance.BALANCED.value,
                'market_maker_actions': [MarketMakerAction.UNKNOWN.value],
                'support_levels': [],
                'resistance_levels': [],
                'bid_volume': 0,
                'ask_volume': 0,
                'signal_strength': 0
            }
        }


# Глобальный экземпляр
orderbook_analyzer = OrderBookAnalyzer()


def test_orderbook_analyzer():
    """Тест анализатора стакана"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ АНАЛИЗАТОРА СТАКАНА")
    print("="*60)
    
    analyzer = OrderBookAnalyzer()
    
    # Тестируем на тестовом тикере
    test_ticker = "Si-3.26"
    result = analyzer.analyze(test_ticker)
    
    print(f"Score: {result['score']:.2f}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Signal: {result['signal']}")
    
    details = result['details']
    print(f"\nSpread: {details['spread_percent']:.3f}%")
    print(f"Volume imbalance: {details['volume_imbalance']:+.1f}%")
    print(f"Order book imbalance: {details['order_book_imbalance']}")
    print(f"Signal strength: {details['signal_strength']:.1f}%")
    
    print(f"\nMarket maker actions:")
    for action in details['market_maker_actions']:
        print(f"  - {action}")
    
    if details['support_levels']:
        print(f"\nTop support levels:")
        for price in details['support_levels']:
            print(f"  - {price:.2f}")
    
    if details['resistance_levels']:
        print(f"\nTop resistance levels:")
        for price in details['resistance_levels']:
            print(f"  - {price:.2f}")
    
    print(f"\nBid volume: {details['bid_volume']:.0f}")
    print(f"Ask volume: {details['ask_volume']:.0f}")
    
    print("\n" + "="*60)
    
    return result


if __name__ == "__main__":
    test_orderbook_analyzer()