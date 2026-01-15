"""
Управление рисками, стоп-лоссами и тейк-профитами.
Реализует трейлинг-стоп и перенос стопа в безубыток.
"""
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime
import numpy as np

from config.settings import settings
from core.portfolio import portfolio_manager
from utils.logger import log


@dataclass
class RiskParameters:
    """Параметры управления риском для позиции"""
    stop_loss_price: float  # Цена стоп-лосса
    take_profit_price: float  # Цена тейк-профита
    initial_stop_loss: float  # Начальный стоп-лосс
    trailing_stop_activated: bool = False  # Активирован ли трейлинг-стоп
    breakeven_stop_activated: bool = False  # Активирован ли стоп в безубыток
    risk_reward_ratio: float = 2.0  # Соотношение риск/прибыль
    risk_amount: float = 0.0  # Сумма риска в рублях
    max_position_risk: float = 0.02  # Максимальный риск 2% от депозита


@dataclass
class PositionRisk:
    """Информация о рисках позиции"""
    position_id: str
    ticker: str
    entry_price: float
    current_price: float
    position_size: float  # Сумма позиции в рублях
    position_type: str  # LONG или SHORT
    risk_params: RiskParameters
    pnl_percentage: float  # Текущий PnL в %
    pnl_rub: float  # Текущий PnL в рублях
    created_at: datetime
    updated_at: datetime


class RiskManager:
    """
    Менеджер рисков для управления стоп-лоссами и тейк-профитами.
    """
    
    def __init__(self):
        self.positions: Dict[str, PositionRisk] = {}
        self.default_risk_reward = 2.0  # По умолчанию риск/прибыль = 1:2
        self.trailing_stop_activation = 0.10  # Активация трейлинга при 10% прибыли
        self.breakeven_activation = 0.10  # Перенос в безубыток при 10% прибыли
        self.min_stop_distance = 0.005  # Минимальное расстояние стоп-лосса (0.5%)
        
        log.info("Инициализация менеджера рисков")
    
    def calculate_risk_parameters(self,
                                ticker: str,
                                entry_price: float,
                                position_type: str,
                                position_value: float,
                                analysis_result: Dict[str, Any],
                                atr: Optional[float] = None) -> RiskParameters:
        """
        Рассчитать параметры риска для новой позиции.
        
        Args:
            ticker: Тикер инструмента
            entry_price: Цена входа
            position_type: LONG или SHORT
            position_value: Сумма позиции в рублях
            analysis_result: Результат анализа
            atr: Average True Range (если доступен)
            
        Returns:
            RiskParameters с ценами стоп-лосса и тейк-профита
        """
        try:
            # Определяем волатильность
            if atr is None or atr <= 0:
                # Эмпирическая оценка волатильности
                volatility = entry_price * 0.01  # 1% по умолчанию
            else:
                volatility = atr
            
            # Базовое расстояние для стоп-лосса
            if position_type == "LONG":
                # Для лонга: стоп ниже цены входа
                stop_distance = volatility * 2  # 2 ATR
                take_distance = volatility * 4  # 4 ATR (риск/прибыль 1:2)
                
                stop_loss = entry_price - stop_distance
                take_profit = entry_price + take_distance
                
            else:  # SHORT
                # Для шорта: стоп выше цены входа
                stop_distance = volatility * 2
                take_distance = volatility * 4
                
                stop_loss = entry_price + stop_distance
                take_profit = entry_price - take_distance
            
            # Корректируем на основе анализа
            confidence = analysis_result.get('final_probability', 0.5)
            
            if confidence > 0.7:
                # При высокой уверенности можно увеличить риск/прибыль
                take_profit = self._adjust_for_confidence(
                    entry_price, take_profit, confidence, position_type
                )
            
            # Рассчитываем сумму риска
            if position_type == "LONG":
                risk_per_unit = entry_price - stop_loss
            else:
                risk_per_unit = stop_loss - entry_price
            
            risk_amount = risk_per_unit * (position_value / entry_price) if entry_price > 0 else 0
            
            # Ограничиваем максимальный риск
            max_risk = portfolio_manager.current_deposit * 0.02  # Макс 2% от депозита
            if risk_amount > max_risk:
                # Корректируем стоп-лосс
                scaling_factor = max_risk / risk_amount
                if position_type == "LONG":
                    stop_loss = entry_price - (stop_distance * scaling_factor)
                else:
                    stop_loss = entry_price + (stop_distance * scaling_factor)
                
                risk_amount = max_risk
                log.warning(f"Скорректирован стоп-лосс для ограничения риска: "
                           f"{risk_amount:.0f}₽ вместо {risk_per_unit * (position_value / entry_price):.0f}₽")
            
            # Рассчитываем соотношение риск/прибыль
            if risk_per_unit > 0:
                if position_type == "LONG":
                    profit_per_unit = take_profit - entry_price
                else:
                    profit_per_unit = entry_price - take_profit
                
                risk_reward_ratio = profit_per_unit / risk_per_unit if risk_per_unit > 0 else 0
            else:
                risk_reward_ratio = self.default_risk_reward
            
            params = RiskParameters(
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                initial_stop_loss=stop_loss,
                risk_amount=risk_amount,
                risk_reward_ratio=risk_reward_ratio,
                max_position_risk=0.02
            )
            
            log.info(f"Рассчитаны параметры риска для {ticker}: "
                    f"стоп {stop_loss:.0f}, тейк {take_profit:.0f}, "
                    f"риск/прибыль {risk_reward_ratio:.2f}, сумма риска {risk_amount:.0f}₽")
            
            return params
            
        except Exception as e:
            log.error(f"Ошибка расчета параметров риска: {e}")
            # Возвращаем параметры по умолчанию
            return self._get_default_parameters(entry_price, position_type)
    
    def _adjust_for_confidence(self, 
                              entry_price: float,
                              take_profit: float,
                              confidence: float,
                              position_type: str) -> float:
        """Скорректировать тейк-профит на основе уверенности"""
        # Чем выше уверенность, тем дальше тейк-профит
        confidence_boost = (confidence - 0.7) * 2  # Усиление для уверенности > 70%
        
        if position_type == "LONG":
            distance = take_profit - entry_price
            adjusted_distance = distance * (1 + confidence_boost)
            return entry_price + adjusted_distance
        else:
            distance = entry_price - take_profit
            adjusted_distance = distance * (1 + confidence_boost)
            return entry_price - adjusted_distance
    
    def _get_default_parameters(self, 
                               entry_price: float,
                               position_type: str) -> RiskParameters:
        """Получить параметры риска по умолчанию"""
        default_distance = entry_price * 0.02  # 2%
        
        if position_type == "LONG":
            stop_loss = entry_price * 0.98  # -2%
            take_profit = entry_price * 1.04  # +4% (риск/прибыль 1:2)
        else:
            stop_loss = entry_price * 1.02  # +2%
            take_profit = entry_price * 0.96  # -4% (риск/прибыль 1:2)
        
        return RiskParameters(
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            initial_stop_loss=stop_loss,
            risk_amount=entry_price * 0.02,
            risk_reward_ratio=2.0,
            max_position_risk=0.02
        )
    
    def add_position(self,
                    position_id: str,
                    ticker: str,
                    entry_price: float,
                    position_type: str,
                    position_size: float,
                    risk_params: RiskParameters):
        """
        Добавить новую позицию для отслеживания рисков.
        """
        position_risk = PositionRisk(
            position_id=position_id,
            ticker=ticker,
            entry_price=entry_price,
            current_price=entry_price,
            position_size=position_size,
            position_type=position_type,
            risk_params=risk_params,
            pnl_percentage=0.0,
            pnl_rub=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.positions[position_id] = position_risk
        
        log.info(f"Добавлена позиция {position_id} ({ticker}) для отслеживания рисков")
    
    def update_position_price(self, 
                            position_id: str, 
                            current_price: float) -> Dict[str, Any]:
        """
        Обновить цену позиции и проверить условия стоп-лоссов.
        
        Returns:
            Словарь с действиями: {'stop_hit': bool, 'take_hit': bool, 'adjustments': []}
        """
        if position_id not in self.positions:
            return {'stop_hit': False, 'take_hit': False, 'adjustments': []}
        
        position = self.positions[position_id]
        position.current_price = current_price
        position.updated_at = datetime.now()
        
        # Рассчитываем текущий PnL
        if position.position_type == "LONG":
            pnl_rub = (current_price - position.entry_price) * (position.position_size / position.entry_price)
        else:
            pnl_rub = (position.entry_price - current_price) * (position.position_size / position.entry_price)
        
        position.pnl_rub = pnl_rub
        position.pnl_percentage = (pnl_rub / position.position_size) * 100
        
        actions = {
            'stop_hit': False,
            'take_hit': False,
            'adjustments': [],
            'current_pnl_percent': position.pnl_percentage,
            'current_pnl_rub': position.pnl_rub
        }
        
        # Проверяем стоп-лосс и тейк-профит
        if self._check_stop_loss(position, current_price):
            actions['stop_hit'] = True
            log.info(f"Стоп-лосс сработал для позиции {position_id}")
        
        if self._check_take_profit(position, current_price):
            actions['take_hit'] = True
            log.info(f"Тейк-профит сработал для позиции {position_id}")
        
        # Проверяем условия для трейлинг-стопа и безубытка
        adjustments = self._check_adjustment_conditions(position)
        if adjustments:
            actions['adjustments'].extend(adjustments)
        
        return actions
    
    def _check_stop_loss(self, position: PositionRisk, current_price: float) -> bool:
        """Проверить, сработал ли стоп-лосс"""
        if position.position_type == "LONG":
            return current_price <= position.risk_params.stop_loss_price
        else:
            return current_price >= position.risk_params.stop_loss_price
    
    def _check_take_profit(self, position: PositionRisk, current_price: float) -> bool:
        """Проверить, сработал ли тейк-профит"""
        if position.position_type == "LONG":
            return current_price >= position.risk_params.take_profit_price
        else:
            return current_price <= position.risk_params.take_profit_price
    
    def _check_adjustment_conditions(self, position: PositionRisk) -> List[Dict[str, Any]]:
        """
        Проверить условия для корректировки стоп-лосса.
        """
        adjustments = []
        
        # 1. Проверяем условие для безубытка
        if (not position.risk_params.breakeven_stop_activated and 
            position.pnl_percentage >= self.breakeven_activation * 100):
            
            # Переносим стоп в точку безубытка
            if position.position_type == "LONG":
                new_stop = position.entry_price * 1.001  # Чуть выше цены входа
            else:
                new_stop = position.entry_price * 0.999  # Чуть ниже цены входа
            
            position.risk_params.stop_loss_price = new_stop
            position.risk_params.breakeven_stop_activated = True
            
            adjustments.append({
                'type': 'BREAKEVEN',
                'new_stop': new_stop,
                'reason': f'Прибыль достигла {self.breakeven_activation * 100:.0f}%'
            })
            
            log.info(f"Перенесен стоп в безубыток для позиции {position.position_id}")
        
        # 2. Проверяем условие для трейлинг-стопа
        elif (not position.risk_params.trailing_stop_activated and 
              position.pnl_percentage >= self.trailing_stop_activation * 100):
            
            # Активируем трейлинг-стоп
            position.risk_params.trailing_stop_activated = True
            
            adjustments.append({
                'type': 'TRAILING_START',
                'reason': f'Активация трейлинг-стопа при {self.trailing_stop_activation * 100:.0f}% прибыли'
            })
            
            log.info(f"Активирован трейлинг-стоп для позиции {position.position_id}")
        
        # 3. Обновляем трейлинг-стоп
        elif position.risk_params.trailing_stop_activated:
            adjustment = self._update_trailing_stop(position)
            if adjustment:
                adjustments.append(adjustment)
        
        return adjustments
    
    def _update_trailing_stop(self, position: PositionRisk) -> Optional[Dict[str, Any]]:
        """Обновить трейлинг-стоп"""
        if position.position_type == "LONG":
            # Для лонга: стоп ниже максимальной цены
            trailing_distance = position.entry_price * 0.01  # 1% трейлинг
            
            new_stop = position.current_price - trailing_distance
            current_stop = position.risk_params.stop_loss_price
            
            # Поднимаем стоп только вверх
            if new_stop > current_stop:
                position.risk_params.stop_loss_price = new_stop
                
                return {
                    'type': 'TRAILING_UPDATE',
                    'new_stop': new_stop,
                    'reason': f'Трейлинг-стоп обновлен до {new_stop:.0f}'
                }
        
        else:  # SHORT
            # Для шорта: стоп выше минимальной цены
            trailing_distance = position.entry_price * 0.01
            
            new_stop = position.current_price + trailing_distance
            current_stop = position.risk_params.stop_loss_price
            
            # Опускаем стоп только вниз
            if new_stop < current_stop:
                position.risk_params.stop_loss_price = new_stop
                
                return {
                    'type': 'TRAILING_UPDATE',
                    'new_stop': new_stop,
                    'reason': f'Трейлинг-стоп обновлен до {new_stop:.0f}'
                }
        
        return None
    
    def remove_position(self, position_id: str):
        """Удалить позицию из отслеживания"""
        if position_id in self.positions:
            del self.positions[position_id]
            log.info(f"Удалена позиция {position_id} из отслеживания рисков")
    
    def get_position_risk(self, position_id: str) -> Optional[PositionRisk]:
        """Получить информацию о рисках позиции"""
        return self.positions.get(position_id)
    
    def get_all_positions_risk(self) -> List[Dict[str, Any]]:
        """Получить информацию о рисках всех позиций"""
        result = []
        
        for position_id, position in self.positions.items():
            result.append({
                'position_id': position_id,
                'ticker': position.ticker,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'pnl_percent': position.pnl_percentage,
                'pnl_rub': position.pnl_rub,
                'stop_loss': position.risk_params.stop_loss_price,
                'take_profit': position.risk_params.take_profit_price,
                'breakeven_activated': position.risk_params.breakeven_stop_activated,
                'trailing_activated': position.risk_params.trailing_stop_activated
            })
        
        return result
    
    def calculate_portfolio_risk(self) -> Dict[str, Any]:
        """Рассчитать общий риск портфеля"""
        total_position_value = 0.0
        total_risk_amount = 0.0
        total_pnl_rub = 0.0
        
        for position in self.positions.values():
            total_position_value += position.position_size
            total_risk_amount += position.risk_params.risk_amount
            total_pnl_rub += position.pnl_rub
        
        portfolio_value = portfolio_manager.current_deposit + total_pnl_rub
        
        return {
            'total_positions': len(self.positions),
            'total_position_value': total_position_value,
            'total_risk_amount': total_risk_amount,
            'total_pnl_rub': total_pnl_rub,
            'portfolio_value': portfolio_value,
            'risk_percentage': (total_risk_amount / portfolio_value * 100) if portfolio_value > 0 else 0,
            'positions': self.get_all_positions_risk()
        }


# Глобальный экземпляр
risk_manager = RiskManager()


def test_risk_manager():
    """Тест менеджера рисков"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ МЕНЕДЖЕРА РИСКОВ")
    print("="*60)
    
    manager = RiskManager()
    
    # Тест 1: Расчет параметров риска
    print("\n📊 Тест 1: Расчет параметров риска")
    
    test_analysis = {
        'final_probability': 0.8,
        'current_price': 75000.0
    }
    
    params = manager.calculate_risk_parameters(
        ticker="Si-3.26",
        entry_price=75000.0,
        position_type="LONG",
        position_value=100000.0,
        analysis_result=test_analysis,
        atr=750.0  # 1% волатильность
    )
    
    print(f"Стоп-лосс: {params.stop_loss_price:.0f} (-{((75000 - params.stop_loss_price) / 75000 * 100):.1f}%)")
    print(f"Тейк-профит: {params.take_profit_price:.0f} (+{(params.take_profit_price - 75000) / 75000 * 100:.1f}%)")
    print(f"Риск/прибыль: {params.risk_reward_ratio:.2f}")
    print(f"Сумма риска: {params.risk_amount:.0f}₽")
    
    # Тест 2: Отслеживание позиции
    print("\n📊 Тест 2: Отслеживание позиции")
    
    position_id = "TEST_001"
    manager.add_position(
        position_id=position_id,
        ticker="Si-3.26",
        entry_price=75000.0,
        position_type="LONG",
        position_size=100000.0,
        risk_params=params
    )
    
    # Симулируем рост цены
    print("\nСимуляция роста цены:")
    test_prices = [75500, 76000, 76500, 77000, 77500]
    
    for price in test_prices:
        actions = manager.update_position_price(position_id, price)
        
        pnl_percent = actions['current_pnl_percent']
        print(f"Цена: {price:.0f} | PnL: {pnl_percent:.1f}% | "
              f"Стоп: {manager.positions[position_id].risk_params.stop_loss_price:.0f}")
        
        if actions['adjustments']:
            for adj in actions['adjustments']:
                print(f"  Корректировка: {adj['type']} - {adj.get('reason', '')}")
    
    # Тест 3: Риск портфеля
    print("\n📊 Тест 3: Риск портфеля")
    portfolio_risk = manager.calculate_portfolio_risk()
    
    print(f"Всего позиций: {portfolio_risk['total_positions']}")
    print(f"Общая стоимость позиций: {portfolio_risk['total_position_value']:,.0f}₽")
    print(f"Общий риск: {portfolio_risk['total_risk_amount']:,.0f}₽")
    print(f"Общий PnL: {portfolio_risk['total_pnl_rub']:,.0f}₽")
    print(f"Риск портфеля: {portfolio_risk['risk_percentage']:.2f}%")
    
    # Тест 4: Симуляция стоп-лосса
    print("\n📊 Тест 4: Симуляция стоп-лосса")
    
    # Падаем ниже стоп-лосса
    stop_price = manager.positions[position_id].risk_params.stop_loss_price
    actions = manager.update_position_price(position_id, stop_price - 100)
    
    if actions['stop_hit']:
        print(f"✅ Стоп-лосс сработал при цене {stop_price - 100:.0f}")
    
    print("\n" + "="*60)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("="*60)
    
    return manager


if __name__ == "__main__":
    test_risk_manager()