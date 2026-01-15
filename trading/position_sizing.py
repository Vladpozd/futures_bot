"""
Расчет размера позиции на основе вероятности.
Правило: вероятность → % депозита → размер с учетом плеча.
"""
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from config.settings import settings
from core.portfolio import portfolio_manager
from config.instruments import get_instrument, FutureInstrument
from utils.logger import log


@dataclass
class PositionSizeResult:
    """Результат расчета размера позиции"""
    position_value: float  # Сумма позиции в рублях
    position_percentage: float  # % от депозита (до применения плеча)
    leverage_used: float  # Используемое плечо
    lot_size: int  # Количество лотов
    can_open: bool  # Можно ли открывать позицию
    risk_amount: float  # Сумма риска (для стоп-лосса)
    reason: str  # Причина решения


class PositionSizing:
    """
    Калькулятор размера позиции на основе вероятности.
    
    Логика:
    1. Вероятность < MIN_PROBABILITY (30%) → позиция = 0
    2. Вероятность 30-60% → маленькая позиция (30-60% от макс.)
    3. Вероятность 60-80% → средняя позиция (60-80% от макс.)
    4. Вероятность 80-95% → большая позиция (80-95% от макс.)
    5. Вероятность >95% → максимальная позиция
    
    Размер = вероятность × депозит × плечо
    """
    
    def __init__(self):
        self.min_probability = 0.30  # 30% - минимальный порог
        self.max_position_percentage = 1.0  # Максимум 100% депозита с учетом плеча
        self.risk_per_trade = 0.02  # Риск 2% от депозита на сделку
        
        log.info("Инициализация калькулятора размера позиции")
    
    def calculate_position_size(self, 
                              analysis_result: Dict[str, Any],
                              ticker: str,
                              current_price: float) -> PositionSizeResult:
        """
        Рассчитать размер позиции на основе анализа.
        
        Args:
            analysis_result: Результат комплексного анализа
            ticker: Тикер инструмента
            current_price: Текущая цена
            
        Returns:
            PositionSizeResult с размером позиции
        """
        try:
            # Извлекаем вероятность из анализа
            probability = analysis_result.get('final_probability', 0.0)
            can_open_analysis = analysis_result.get('can_open_position', False)
            position_category = analysis_result.get('position_size_category', 'NONE')
            
            log.info(f"Расчет позиции для {ticker}. Вероятность: {probability:.1%}, "
                    f"Категория: {position_category}")
            
            # 1. Проверяем, можно ли открывать позицию по анализу
            if not can_open_analysis or probability < self.min_probability:
                return self._get_zero_position(
                    ticker, 
                    f"Низкая вероятность ({probability:.1%} < {self.min_probability:.0%})"
                )
            
            # 2. Получаем информацию об инструменте
            instrument = get_instrument(ticker)
            
            # 3. Рассчитываем процент позиции от депозита
            position_percentage = self._calculate_position_percentage(probability)
            
            # 4. Определяем используемое плечо
            leverage = self._determine_leverage(probability, position_category)
            
            # 5. Рассчитываем размер позиции в рублях
            position_value = self._calculate_position_value(
                position_percentage, leverage, current_price, instrument
            )
            
            # 6. Рассчитываем количество лотов
            lot_size = self._calculate_lot_size(position_value, current_price, instrument)
            
            # 7. Проверяем доступность средств
            available_funds = portfolio_manager.available_deposit * leverage
            
            if position_value > available_funds * 0.95:  # Оставляем 5% на комиссии
                adjusted_value = available_funds * 0.95
                lot_size = self._calculate_lot_size(adjusted_value, current_price, instrument)
                position_value = lot_size * current_price * instrument.lot_size
                
                log.warning(f"Скорректировали позицию: недостаточно средств. "
                          f"Было: {position_value:.0f}₽, Стало: {adjusted_value:.0f}₽")
            
            # 8. Рассчитываем сумму риска
            risk_amount = self._calculate_risk_amount(position_value)
            
            # 9. Проверяем минимальную прибыль (с учетом комиссий)
            min_profit_check = self._check_minimum_profit(
                position_value, current_price, instrument
            )
            
            if not min_profit_check['passed']:
                return self._get_zero_position(
                    ticker,
                    f"Минимальная прибыль не достижима: {min_profit_check['reason']}"
                )
            
            result = PositionSizeResult(
                position_value=position_value,
                position_percentage=position_percentage,
                leverage_used=leverage,
                lot_size=lot_size,
                can_open=True,
                risk_amount=risk_amount,
                reason=f"Вероятность {probability:.1%}, категория {position_category}"
            )
            
            log.info(f"✅ Позиция для {ticker}: {lot_size} лотов, "
                    f"{position_value:.0f}₽ ({position_percentage:.1%} депозита), "
                    f"плечо {leverage}x, риск {risk_amount:.0f}₽")
            
            return result
            
        except Exception as e:
            log.error(f"Ошибка расчета позиции для {ticker}: {e}")
            return self._get_zero_position(ticker, f"Ошибка расчета: {str(e)}")
    
    def _calculate_position_percentage(self, probability: float) -> float:
        """
        Рассчитать процент депозита для позиции на основе вероятности.
        
        Линейное преобразование:
        - 30% вероятность → 0% депозита
        - 100% вероятность → 100% депозита
        """
        if probability < self.min_probability:
            return 0.0
        
        # Линейная шкала
        position_percentage = (probability - self.min_probability) / (1.0 - self.min_probability)
        
        # Добавляем нелинейность для высоких вероятностей
        if probability > 0.8:
            # Ускоренный рост при высоких вероятностях
            boost = (probability - 0.8) * 0.5
            position_percentage = min(1.0, position_percentage + boost)
        
        # Ограничиваем максимальный процент
        max_percentage = self.max_position_percentage
        if settings.RISK_LEVEL == 'high':
            max_percentage = 1.0  # 100% для высокого риска
        elif settings.RISK_LEVEL == 'medium':
            max_percentage = 0.7  # 70% для среднего риска
        else:
            max_percentage = 0.5  # 50% для низкого риска
        
        position_percentage = min(max_percentage, position_percentage)
        
        return position_percentage
    
    def _determine_leverage(self, probability: float, category: str) -> float:
        """
        Определить используемое плечо на основе вероятности и категории риска.
        """
        # Базовое плечо из настроек
        base_leverage = settings.MIN_LEVERAGE
        
        # Увеличиваем плечо при высокой вероятности
        if probability > 0.8:
            leverage_multiplier = 1.5
        elif probability > 0.6:
            leverage_multiplier = 1.2
        else:
            leverage_multiplier = 1.0
        
        # Учитываем категорию позиции
        category_multiplier = {
            'SMALL': 0.7,
            'MEDIUM': 1.0,
            'LARGE': 1.2,
            'MAX': 1.5
        }.get(category, 1.0)
        
        # Рассчитываем итоговое плечо
        leverage = base_leverage * leverage_multiplier * category_multiplier
        
        # Ограничиваем максимальным плечом из настроек
        leverage = min(leverage, settings.MAX_LEVERAGE)
        leverage = max(leverage, settings.MIN_LEVERAGE)
        
        return leverage
    
    def _calculate_position_value(self, 
                                position_percentage: float,
                                leverage: float,
                                current_price: float,
                                instrument: FutureInstrument) -> float:
        """
        Рассчитать стоимость позиции в рублях.
        """
        # Доступный депозит
        available_deposit = portfolio_manager.available_deposit
        
        # Размер позиции в рублях (до применения плеча)
        position_before_leverage = available_deposit * position_percentage
        
        # Применяем плечо
        position_value = position_before_leverage * leverage
        
        # Округляем до целого количества лотов
        lot_cost = current_price * instrument.lot_size
        if lot_cost > 0:
            max_lots = int(position_value / lot_cost)
            position_value = max_lots * lot_cost
        
        # Минимальная позиция (хотя бы 1 лот)
        min_position = lot_cost
        if position_value < min_position and position_percentage > 0:
            position_value = min_position
        
        return position_value
    
    def _calculate_lot_size(self, 
                          position_value: float,
                          current_price: float,
                          instrument: FutureInstrument) -> int:
        """
        Рассчитать количество лотов.
        """
        if current_price <= 0:
            return 0
        
        lot_cost = current_price * instrument.lot_size
        if lot_cost <= 0:
            return 0
        
        lot_size = int(position_value / lot_cost)
        
        # Минимум 1 лот, если позиция ненулевая
        if position_value > 0 and lot_size == 0:
            lot_size = 1
        
        return lot_size
    
    def _calculate_risk_amount(self, position_value: float) -> float:
        """
        Рассчитать сумму риска на сделку.
        """
        # Риск = % от депозита
        risk_amount = portfolio_manager.current_deposit * self.risk_per_trade
        
        # Не более 5% от размера позиции
        max_risk = position_value * 0.05
        risk_amount = min(risk_amount, max_risk)
        
        return risk_amount
    
    def _check_minimum_profit(self,
                            position_value: float,
                            current_price: float,
                            instrument: FutureInstrument) -> Dict[str, Any]:
        """
        Проверить, достижима ли минимальная прибыль с учетом комиссий.
        """
        # Минимальный рост для покрытия комиссий
        min_growth = settings.MIN_PROFIT_THRESHOLD  # 0.091%
        
        # Комиссия за круг (покупка + продажа)
        commission_rate = settings.COMMISSION_BUY + settings.COMMISSION_SELL
        
        # Минимальная прибыль в рублях
        min_profit_rub = position_value * min_growth
        
        # Комиссия в рублях
        commission_rub = position_value * commission_rate
        
        # Общая минимальная прибыль
        total_min_profit = min_profit_rub + commission_rub
        
        # Проверяем, не слишком ли мала позиция для прибыли
        min_position_for_profit = total_min_profit / (min_growth * 10)  # Эмпирическая формула
        
        if position_value < min_position_for_profit:
            return {
                'passed': False,
                'reason': f"Позиция слишком мала ({position_value:.0f}₽ < {min_position_for_profit:.0f}₽)"
            }
        
        # Проверяем, не слишком ли высокий спред у инструмента
        min_step_value = instrument.min_step * instrument.lot_size
        
        if min_step_value > total_min_profit * 0.5:
            return {
                'passed': False,
                'reason': f"Слишком высокий минимальный шаг ({min_step_value:.2f}₽)"
            }
        
        return {
            'passed': True,
            'reason': f"Минимальная прибыль достижима: {total_min_profit:.2f}₽"
        }
    
    def _get_zero_position(self, ticker: str, reason: str) -> PositionSizeResult:
        """Вернуть нулевую позицию с причиной"""
        log.info(f"❌ Нулевая позиция для {ticker}: {reason}")
        
        return PositionSizeResult(
            position_value=0.0,
            position_percentage=0.0,
            leverage_used=0.0,
            lot_size=0,
            can_open=False,
            risk_amount=0.0,
            reason=reason
        )
    
    def get_position_summary(self, 
                           analysis_result: Dict[str, Any],
                           ticker: str,
                           current_price: float) -> Dict[str, Any]:
        """
        Получить сводку по позиции для отчета.
        """
        position_result = self.calculate_position_size(analysis_result, ticker, current_price)
        
        instrument = get_instrument(ticker)
        lot_cost = current_price * instrument.lot_size if current_price > 0 else 0
        
        return {
            'ticker': ticker,
            'current_price': current_price,
            'probability': analysis_result.get('final_probability', 0),
            'position_category': analysis_result.get('position_size_category', 'NONE'),
            'can_open': position_result.can_open,
            'position_value': position_result.position_value,
            'position_percentage': position_result.position_percentage * 100,
            'leverage_used': position_result.leverage_used,
            'lot_size': position_result.lot_size,
            'lot_cost': lot_cost,
            'risk_amount': position_result.risk_amount,
            'reason': position_result.reason,
            'instrument_info': {
                'name': instrument.name,
                'lot_size': instrument.lot_size,
                'min_step': instrument.min_step,
                'point_cost': instrument.point_cost
            }
        }


# Глобальный экземпляр
position_sizing = PositionSizing()


def test_position_sizing():
    """Тест калькулятора размера позиции"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ КАЛЬКУЛЯТОРА РАЗМЕРА ПОЗИЦИИ")
    print("="*60)
    
    # Тестовые данные анализа
    test_analysis = {
        'final_probability': 0.75,  # 75%
        'can_open_position': True,
        'position_size_category': 'MEDIUM',
        'current_price': 75000.0,  # Цена Si-3.26 ~ 75,000 руб за контракт
        'integrated_signal': {'direction': 'BUY', 'strength': 80}
    }
    
    test_ticker = "Si-3.26"
    test_price = 75000.0
    
    calculator = PositionSizing()
    
    print(f"\nТест для {test_ticker} по цене {test_price:.0f}₽")
    print(f"Вероятность: {test_analysis['final_probability']:.1%}")
    print(f"Категория: {test_analysis['position_size_category']}")
    
    # Рассчитываем позицию
    result = calculator.calculate_position_size(
        test_analysis, test_ticker, test_price
    )
    
    print(f"\n📊 РЕЗУЛЬТАТ РАСЧЕТА:")
    print(f"Можно открыть: {'ДА' if result.can_open else 'НЕТ'}")
    print(f"Причина: {result.reason}")
    
    if result.can_open:
        print(f"\n📈 ДЕТАЛИ ПОЗИЦИИ:")
        print(f"Размер позиции: {result.position_value:,.0f}₽")
        print(f"Процент депозита: {result.position_percentage:.1%}")
        print(f"Используемое плечо: {result.leverage_used:.1f}x")
        print(f"Количество лотов: {result.lot_size}")
        print(f"Сумма риска: {result.risk_amount:,.0f}₽")
        
        # Сводка
        summary = calculator.get_position_summary(test_analysis, test_ticker, test_price)
        print(f"\n📋 СВОДКА:")
        for key, value in summary.items():
            if key not in ['instrument_info', 'reason']:
                print(f"  {key}: {value}")
    
    # Тест разных вероятностей
    print(f"\n📊 ТЕСТ РАЗНЫХ ВЕРОЯТНОСТЕЙ:")
    test_probabilities = [0.25, 0.40, 0.65, 0.85, 0.95]
    
    for prob in test_probabilities:
        test_analysis['final_probability'] = prob
        test_analysis['can_open_position'] = prob >= 0.30
        
        result = calculator.calculate_position_size(
            test_analysis, test_ticker, test_price
        )
        
        status = "✅ ОТКРЫТЬ" if result.can_open else "❌ НЕ ОТКРЫВАТЬ"
        print(f"  {prob:.0%} → {status} ({result.reason})")
    
    print("\n" + "="*60)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("="*60)
    
    return result


if __name__ == "__main__":
    test_position_sizing()