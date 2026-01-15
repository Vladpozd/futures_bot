"""Исполнитель ордеров для работы с T-Tech Investments API."""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid

from t_tech.invest import (
    Client,
    OrderDirection,
    OrderType,
    Quotation,
    StopOrderDirection,
    StopOrderExpirationType,
    StopOrderType
)
from t_tech.invest.utils import decimal_to_quotation, quotation_to_decimal

from config.settings import settings
from core.api_client import api_client
from config.instruments import get_instrument, FutureInstrument
from utils.logger import log


@dataclass
class OrderResult:
    """Результат выставления ордера"""
    order_id: str
    ticker: str
    direction: str
    order_type: str
    price: float
    quantity: int
    status: str
    filled_quantity: int
    average_price: float
    commission: float
    message: str
    timestamp: datetime


@dataclass 
class PositionInfo:
    """Информация об открытой позиции"""
    position_id: str
    ticker: str
    direction: str
    entry_price: float
    current_price: float
    quantity: int
    position_value: float
    pnl_rub: float
    pnl_percentage: float
    stop_loss: float
    take_profit: float
    opened_at: datetime


class OrderExecutor:
    """Исполнитель ордеров для торговли фьючерсами через T-Tech API."""
    
    def __init__(self):
        self.open_orders: Dict[str, OrderResult] = {}
        self.open_positions: Dict[str, PositionInfo] = {}
        self.position_counter = 0
        
        log.info("Инициализация исполнителя ордеров")
    
    def execute_order(self,
                     ticker: str,
                     direction: str,
                     quantity: int,
                     order_type: str = "LIMIT",
                     price: Optional[float] = None,
                     stop_price: Optional[float] = None) -> OrderResult:
        """Выставить ордер на покупку/продажу."""
        order_id = str(uuid.uuid4())
        
        try:
            instrument_info = api_client.find_real_instrument(ticker)
            if not instrument_info:
                return self._create_rejected_order(
                    order_id, ticker, direction, quantity,
                    f"Инструмент {ticker} не найден"
                )
            
            figi = instrument_info['figi']
            
            if order_type == "MARKET" and price is None:
                current_price = api_client.get_current_price(ticker)
                if current_price is None:
                    return self._create_rejected_order(
                        order_id, ticker, direction, quantity,
                        "Не удалось получить текущую цену"
                    )
                price = current_price
            
            instrument = get_instrument(ticker)
            if price and instrument.min_step > 0:
                price = round(price / instrument.min_step) * instrument.min_step
            
            with api_client.connect() as client:
                if order_type == "MARKET":
                    result = self._execute_market_order(
                        client, figi, direction, quantity
                    )
                elif order_type == "LIMIT" and price:
                    result = self._execute_limit_order(
                        client, figi, direction, quantity, price
                    )
                elif order_type == "STOP_LIMIT" and price and stop_price:
                    result = self._execute_stop_limit_order(
                        client, figi, direction, quantity, price, stop_price
                    )
                else:
                    return self._create_rejected_order(
                        order_id, ticker, direction, quantity,
                        f"Неподдерживаемый тип ордера: {order_type}"
                    )
            
            order_result = OrderResult(
                order_id=order_id,
                ticker=ticker,
                direction=direction,
                order_type=order_type,
                price=price or 0,
                quantity=quantity,
                status="FILLED" if result['success'] else "REJECTED",
                filled_quantity=quantity if result['success'] else 0,
                average_price=result.get('average_price', price or 0),
                commission=result.get('commission', 0),
                message=result['message'],
                timestamp=datetime.now()
            )
            
            if result['success']:
                log.info(f"✅ Ордер исполнен: {ticker} {direction} {quantity} лотов "
                        f"по {order_result.average_price:.2f}, комиссия: {order_result.commission:.2f}₽")
                
                if not hasattr(result, 'is_close_order') or not result.get('is_close_order'):
                    self._create_position(
                        ticker, direction, quantity, 
                        order_result.average_price, instrument
                    )
            else:
                log.error(f"❌ Ордер отклонен: {ticker} - {result['message']}")
            
            self.open_orders[order_id] = order_result
            return order_result
            
        except Exception as e:
            log.error(f"Ошибка исполнения ордера {ticker}: {e}")
            return self._create_rejected_order(
                order_id, ticker, direction, quantity,
                f"Ошибка API: {str(e)}"
            )
    
    def _execute_market_order(self, client: Client, figi: str, 
                            direction: str, quantity: int) -> Dict[str, Any]:
        """Исполнить рыночный ордер"""
        try:
            if settings.SANDBOX_MODE:
                order_book = client.market_data.get_order_book(figi=figi, depth=1)
                current_price = float(quotation_to_decimal(order_book.last_price))
                
                order_direction = OrderDirection.ORDER_DIRECTION_BUY if direction == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
                
                response = client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    price=decimal_to_quotation(current_price),
                    direction=order_direction,
                    account_id=self._get_account_id(client),
                    order_type=OrderType.ORDER_TYPE_LIMIT
                )
                
                commission_rate = settings.COMMISSION_BUY if direction == "BUY" else settings.COMMISSION_SELL
                commission = quantity * current_price * commission_rate
                
                return {
                    'success': True,
                    'average_price': current_price,
                    'commission': commission,
                    'message': 'Рыночный ордер исполнен в песочнице'
                }
            else:
                order_direction = OrderDirection.ORDER_DIRECTION_BUY if direction == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
                
                response = client.orders.post_order(
                    figi=figi,
                    quantity=quantity,
                    direction=order_direction,
                    account_id=self._get_account_id(client),
                    order_type=OrderType.ORDER_TYPE_MARKET
                )
                
                executed_price = float(quotation_to_decimal(response.executed_order_price))
                total_amount = float(quotation_to_decimal(response.total_order_amount))
                
                commission_rate = settings.COMMISSION_BUY if direction == "BUY" else settings.COMMISSION_SELL
                commission = total_amount * commission_rate
                
                return {
                    'success': True,
                    'average_price': executed_price,
                    'commission': commission,
                    'message': 'Рыночный ордер исполнен'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Ошибка рыночного ордера: {str(e)}"
            }
    
    def _execute_limit_order(self, client: Client, figi: str,
                           direction: str, quantity: int, price: float) -> Dict[str, Any]:
        """Исполнить лимитный ордер"""
        try:
            order_direction = OrderDirection.ORDER_DIRECTION_BUY if direction == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
            
            response = client.orders.post_order(
                figi=figi,
                quantity=quantity,
                price=decimal_to_quotation(price),
                direction=order_direction,
                account_id=self._get_account_id(client),
                order_type=OrderType.ORDER_TYPE_LIMIT
            )
            
            commission_rate = settings.COMMISSION_BUY if direction == "BUY" else settings.COMMISSION_SELL
            total_amount = price * quantity
            
            if hasattr(response, 'total_order_amount'):
                total_amount = float(quotation_to_decimal(response.total_order_amount))
            
            commission = total_amount * commission_rate
            
            if settings.SANDBOX_MODE:
                return {
                    'success': True,
                    'average_price': price,
                    'commission': commission,
                    'message': 'Лимитный ордер выставлен в песочнице'
                }
            else:
                order_id = response.order_id
                
                return {
                    'success': True,
                    'average_price': price,
                    'commission': commission,
                    'order_id': order_id,
                    'message': 'Лимитный ордер выставлен'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Ошибка лимитного ордера: {str(e)}"
            }
    
    def _execute_stop_limit_order(self, client: Client, figi: str,
                                direction: str, quantity: int, 
                                price: float, stop_price: float) -> Dict[str, Any]:
        """Исполнить стоп-лимитный ордер"""
        try:
            if direction == "BUY":
                stop_direction = StopOrderDirection.STOP_ORDER_DIRECTION_BUY
            else:
                stop_direction = StopOrderDirection.STOP_ORDER_DIRECTION_SELL
            
            response = client.stop_orders.post_stop_order(
                figi=figi,
                quantity=quantity,
                price=decimal_to_quotation(price),
                stop_price=decimal_to_quotation(stop_price),
                direction=stop_direction,
                account_id=self._get_account_id(client),
                expiration_type=StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL,
                stop_order_type=StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT
            )
            
            stop_order_id = response.stop_order_id
            
            return {
                'success': True,
                'stop_order_id': stop_order_id,
                'message': f'Стоп-лимитный ордер выставлен: {direction} {quantity} @ {price} (стоп {stop_price})'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Ошибка стоп-лимитного ордера: {str(e)}"
            }
    
    def _get_account_id(self, client: Client) -> str:
        """Получить ID счета"""
        accounts = client.users.get_accounts()
        if accounts.accounts:
            return accounts.accounts[0].id
        else:
            raise ValueError("Не найден ни один счет")
    
    def _create_position(self, ticker: str, direction: str, 
                        quantity: int, entry_price: float,
                        instrument: FutureInstrument) -> str:
        """Создать запись об открытой позиции"""
        self.position_counter += 1
        position_id = f"POS_{self.position_counter:06d}"
        
        position_value = entry_price * quantity * instrument.lot_size
        
        position = PositionInfo(
            position_id=position_id,
            ticker=ticker,
            direction="LONG" if direction == "BUY" else "SHORT",
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            position_value=position_value,
            pnl_rub=0.0,
            pnl_percentage=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            opened_at=datetime.now()
        )
        
        self.open_positions[position_id] = position
        
        log.info(f"Создана позиция {position_id}: {ticker} {direction} "
                f"{quantity} лотов по {entry_price:.2f}, стоимость: {position_value:.0f}₽")
        
        return position_id
    
    def close_position(self, position_id: str, 
                      order_type: str = "MARKET") -> OrderResult:
        """Закрыть позицию."""
        if position_id not in self.open_positions:
            return self._create_rejected_order(
                f"CLOSE_{position_id}", "", "", 0,
                f"Позиция {position_id} не найдена"
            )
        
        position = self.open_positions[position_id]
        
        if position.direction == "LONG":
            close_direction = "SELL"
        else:
            close_direction = "BUY"
        
        try:
            with api_client.connect() as client:
                if order_type == "MARKET":
                    result = self._execute_market_order(
                        client, 
                        api_client.find_real_instrument(position.ticker)['figi'],
                        close_direction, 
                        position.quantity
                    )
                else:
                    current_price = api_client.get_current_price(position.ticker)
                    if not current_price:
                        return self._create_rejected_order(
                            f"CLOSE_{position_id}", position.ticker, close_direction, position.quantity,
                            "Не удалось получить текущую цену"
                        )
                    
                    result = self._execute_limit_order(
                        client,
                        api_client.find_real_instrument(position.ticker)['figi'],
                        close_direction,
                        position.quantity,
                        current_price
                    )
            
            result['is_close_order'] = True
            
            order_id = f"CLOSE_{position_id}"
            order_result = OrderResult(
                order_id=order_id,
                ticker=position.ticker,
                direction=close_direction,
                order_type=order_type,
                price=position.current_price,
                quantity=position.quantity,
                status="FILLED" if result['success'] else "REJECTED",
                filled_quantity=position.quantity if result['success'] else 0,
                average_price=result.get('average_price', position.current_price),
                commission=result.get('commission', 0),
                message=result['message'],
                timestamp=datetime.now()
            )
            
            if result['success']:
                exit_price = order_result.average_price
                
                if position.direction == "LONG":
                    pnl_rub = (exit_price - position.entry_price) * position.quantity * get_instrument(position.ticker).lot_size
                else:
                    pnl_rub = (position.entry_price - exit_price) * position.quantity * get_instrument(position.ticker).lot_size
                
                position.pnl_rub = pnl_rub
                position.pnl_percentage = (pnl_rub / position.position_value) * 100
                position.current_price = exit_price
                
                log.info(f"Позиция {position_id} закрыта. PnL: {pnl_rub:+.0f}₽ ({position.pnl_percentage:+.1f}%)")
                
                del self.open_positions[position_id]
            
            return order_result
            
        except Exception as e:
            log.error(f"Ошибка закрытия позиции {position_id}: {e}")
            return self._create_rejected_order(
                f"CLOSE_{position_id}", position.ticker, close_direction, position.quantity,
                f"Ошибка закрытия: {str(e)}"
            )
    
    def update_position_prices(self):
        """Обновить цены всех открытых позиций"""
        for position_id, position in list(self.open_positions.items()):
            try:
                current_price = api_client.get_current_price(position.ticker)
                if current_price:
                    position.current_price = current_price
                    
                    if position.direction == "LONG":
                        pnl_rub = (current_price - position.entry_price) * position.quantity * get_instrument(position.ticker).lot_size
                    else:
                        pnl_rub = (position.entry_price - current_price) * position.quantity * get_instrument(position.ticker).lot_size
                    
                    position.pnl_rub = pnl_rub
                    position.pnl_percentage = (pnl_rub / position.position_value) * 100 if position.position_value > 0 else 0
            except Exception as e:
                log.error(f"Ошибка обновления цены позиции {position_id}: {e}")
    
    def set_position_stop_loss(self, position_id: str, stop_price: float) -> bool:
        """Установить стоп-лосс для позиции"""
        if position_id not in self.open_positions:
            return False
        
        position = self.open_positions[position_id]
        
        if position.direction == "LONG":
            direction = "SELL"
        else:
            direction = "BUY"
        
        try:
            order_result = self.execute_order(
                ticker=position.ticker,
                direction=direction,
                quantity=position.quantity,
                order_type="STOP_LIMIT",
                price=stop_price * 0.995,
                stop_price=stop_price
            )
            
            if order_result.status == "FILLED" or "стоп-лимитный ордер выставлен" in order_result.message:
                position.stop_loss = stop_price
                log.info(f"Установлен стоп-лосс для позиции {position_id}: {stop_price:.2f}")
                return True
            else:
                log.error(f"Не удалось установить стоп-лосс: {order_result.message}")
                return False
                
        except Exception as e:
            log.error(f"Ошибка установки стоп-лосса: {e}")
            return False
    
    def set_position_take_profit(self, position_id: str, take_price: float) -> bool:
        """Установить тейк-профит для позиции"""
        if position_id not in self.open_positions:
            return False
        
        position = self.open_positions[position_id]
        
        if position.direction == "LONG":
            direction = "SELL"
        else:
            direction = "BUY"
        
        try:
            order_result = self.execute_order(
                ticker=position.ticker,
                direction=direction,
                quantity=position.quantity,
                order_type="LIMIT",
                price=take_price
            )
            
            if order_result.status == "FILLED" or "лимитный ордер выставлен" in order_result.message:
                position.take_profit = take_price
                log.info(f"Установлен тейк-профит для позиции {position_id}: {take_price:.2f}")
                return True
            else:
                log.error(f"Не удалось установить тейк-профит: {order_result.message}")
                return False
                
        except Exception as e:
            log.error(f"Ошибка установки тейк-профита: {e}")
            return False
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Получить список открытых позиций"""
        positions = []
        
        for position_id, position in self.open_positions.items():
            positions.append({
                'position_id': position_id,
                'ticker': position.ticker,
                'direction': position.direction,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'quantity': position.quantity,
                'position_value': position.position_value,
                'pnl_rub': position.pnl_rub,
                'pnl_percentage': position.pnl_percentage,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'opened_at': position.opened_at
            })
        
        return positions
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Получить сводку по портфелю"""
        total_value = 0.0
        total_pnl = 0.0
        position_count = len(self.open_positions)
        
        for position in self.open_positions.values():
            total_value += position.position_value
            total_pnl += position.pnl_rub
        
        return {
            'total_positions': position_count,
            'total_position_value': total_value,
            'total_pnl_rub': total_pnl,
            'total_pnl_percent': (total_pnl / total_value * 100) if total_value > 0 else 0,
            'positions': self.get_open_positions()
        }
    
    def _create_rejected_order(self, order_id: str, ticker: str, 
                             direction: str, quantity: int,
                             message: str) -> OrderResult:
        """Создать отклоненный ордер"""
        return OrderResult(
            order_id=order_id,
            ticker=ticker,
            direction=direction,
            order_type="REJECTED",
            price=0,
            quantity=quantity,
            status="REJECTED",
            filled_quantity=0,
            average_price=0,
            commission=0,
            message=message,
            timestamp=datetime.now()
        )


# Глобальный экземпляр
order_executor = OrderExecutor()