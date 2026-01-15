"""API клиент для T-Tech Investments API с поддержкой торговли."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from contextlib import contextmanager

from t_tech.invest import Client, CandleInterval
from t_tech.invest.schemas import (
    OrderDirection, OrderType, Quotation, 
    InstrumentIdType, OrderExecutionReportStatus
)
from t_tech.invest.utils import quotation_to_decimal, decimal_to_quotation

from config.settings import settings
from utils.logger import log


class TTechInvestAPIClient:
    """Клиент для работы с T-Tech API с поддержкой торговли."""
    
    def __init__(self):
        self.token = settings.TINKOFF_TOKEN
        self.sandbox = settings.SANDBOX_MODE
        
        self._instruments_cache: Dict[str, dict] = {}
        self._figi_to_ticker: Dict[str, str] = {}
        self._account_id: Optional[str] = None
        
        log.info(f"Инициализация T-Tech API клиента")
        log.info(f"  Режим: {'ПЕСОЧНИЦА' if self.sandbox else 'БОЕВОЙ'}")
        log.info(f"  Токен: {self.token[:20]}...")
    
    def _execute_with_client(self, func):
        """Выполнить функцию с клиентом в контексте."""
        try:
            with Client(token=self.token) as client:
                return func(client)
        except Exception as e:
            log.error(f"Ошибка выполнения операции: {e}")
            raise
    
    def _get_account_id(self, client) -> str:
        """Получить ID основного счета."""
        if self._account_id:
            return self._account_id
        
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            raise ValueError("Нет доступных счетов")
        
        # Выбираем первый счет типа "Брокерский"
        for account in accounts.accounts:
            if account.type == 1:  # Брокерский счет
                self._account_id = account.id
                log.info(f"Выбран счет: {account.name} ({account.id})")
                return self._account_id
        
        # Если не нашли брокерский, берем первый
        self._account_id = accounts.accounts[0].id
        log.info(f"Выбран счет (первый доступный): {accounts.accounts[0].name} ({self._account_id})")
        return self._account_id
    
    def find_real_instrument(self, ticker: str) -> Optional[dict]:
        """Найти инструмент через API."""
        if ticker in self._instruments_cache:
            return self._instruments_cache[ticker]
        
        def find_instrument(client):
            # 1. Ищем среди фьючерсов
            futures_response = client.instruments.futures()
            for instrument in futures_response.instruments:
                if instrument.ticker == ticker:
                    return self._cache_instrument(ticker, instrument)
            
            # 2. Ищем через общий поиск
            response = client.instruments.find_instrument(query=ticker)
            if response.instruments:
                return self._cache_instrument(ticker, response.instruments[0])
            
            log.warning(f"Инструмент {ticker} не найден")
            return None
        
        try:
            return self._execute_with_client(find_instrument)
        except Exception as e:
            log.error(f"Ошибка поиска {ticker}: {e}")
            return None
    
    def _cache_instrument(self, ticker: str, instrument) -> dict:
        """Кэшировать информацию об инструменте."""
        info = {
            'figi': instrument.figi,
            'ticker': instrument.ticker,
            'name': instrument.name,
            'lot': instrument.lot if hasattr(instrument, 'lot') else 1,
            'currency': instrument.currency if hasattr(instrument, 'currency') else 'rub',
            'api_trade_available_flag': instrument.api_trade_available_flag if hasattr(instrument, 'api_trade_available_flag') else False,
            'buy_available_flag': instrument.buy_available_flag if hasattr(instrument, 'buy_available_flag') else False,
            'sell_available_flag': instrument.sell_available_flag if hasattr(instrument, 'sell_available_flag') else False,
        }
        
        # Для min_price_increment (может быть в разных форматах)
        if hasattr(instrument, 'min_price_increment'):
            if hasattr(instrument.min_price_increment, 'units'):
                info['min_price_increment'] = float(quotation_to_decimal(instrument.min_price_increment))
            else:
                info['min_price_increment'] = float(instrument.min_price_increment)
        else:
            info['min_price_increment'] = 0.01
        
        # Дополнительные поля
        if hasattr(instrument, 'min_price_increment_amount'):
            if hasattr(instrument.min_price_increment_amount, 'units'):
                info['min_price_increment_amount'] = float(quotation_to_decimal(instrument.min_price_increment_amount))
            else:
                info['min_price_increment_amount'] = float(instrument.min_price_increment_amount)
        
        if hasattr(instrument, 'expiration_date'):
            info['expiration_date'] = instrument.expiration_date
        
        self._instruments_cache[ticker] = info
        self._figi_to_ticker[instrument.figi] = ticker
        log.debug(f"Кэширован: {ticker} -> {info['figi']}")
        return info
    
    # -----------------------------------------------------------------
    # МЕТОДЫ ДЛЯ РЫНОЧНЫХ ДАННЫХ
    # -----------------------------------------------------------------
    
    def get_candles(self, ticker: str, interval: str = '15min', 
                   hours: int = 24) -> List[Dict]:
        """Получить свечи для инструмента."""
        instrument = self.find_real_instrument(ticker)
        if not instrument:
            return []
        
        # Маппинг интервалов
        interval_map = {
            '1min': CandleInterval.CANDLE_INTERVAL_1_MIN,
            '5min': CandleInterval.CANDLE_INTERVAL_5_MIN,
            '15min': CandleInterval.CANDLE_INTERVAL_15_MIN,
            '1hour': CandleInterval.CANDLE_INTERVAL_HOUR,
            '1day': CandleInterval.CANDLE_INTERVAL_DAY
        }
        
        candle_interval = interval_map.get(interval, CandleInterval.CANDLE_INTERVAL_15_MIN)
        
        def get_candles_func(client):
            to_time = datetime.now()
            from_time = to_time - timedelta(hours=hours)
            
            response = client.market_data.get_candles(
                figi=instrument['figi'],
                from_=from_time,
                to=to_time,
                interval=candle_interval
            )
            
            candles = []
            for candle in response.candles:
                candles.append({
                    'time': candle.time,
                    'open': float(quotation_to_decimal(candle.open)),
                    'high': float(quotation_to_decimal(candle.high)),
                    'low': float(quotation_to_decimal(candle.low)),
                    'close': float(quotation_to_decimal(candle.close)),
                    'volume': candle.volume,
                    'interval': interval,
                    'is_complete': candle.is_complete
                })
            
            log.debug(f"Получено свечей {ticker}: {len(candles)} шт.")
            return candles
        
        try:
            return self._execute_with_client(get_candles_func)
        except Exception as e:
            log.error(f"Ошибка получения свечей {ticker}: {e}")
            return []
    
    def get_order_book(self, ticker: str, depth: int = 10) -> Dict:
        """Получить стакан."""
        instrument = self.find_real_instrument(ticker)
        if not instrument:
            return {'bids': [], 'asks': []}
        
        def get_order_book_func(client):
            response = client.market_data.get_order_book(
                figi=instrument['figi'],
                depth=depth
            )
            
            order_book = {
                'figi': instrument['figi'],
                'time': datetime.now(),  # Используем текущее время, если нет в ответе
                'bids': [],
                'asks': []
            }
            
            # Пытаемся получить время из ответа
            if hasattr(response, 'time'):
                order_book['time'] = response.time
            
            for bid in response.bids:
                order_book['bids'].append({
                    'price': float(quotation_to_decimal(bid.price)),
                    'quantity': bid.quantity
                })
            
            for ask in response.asks:
                order_book['asks'].append({
                    'price': float(quotation_to_decimal(ask.price)),
                    'quantity': ask.quantity
                })
            
            log.debug(f"Получен стакан {ticker}, глубина: {depth}")
            return order_book
        
        try:
            return self._execute_with_client(get_order_book_func)
        except Exception as e:
            log.error(f"Ошибка получения стакана {ticker}: {e}")
            return {'bids': [], 'asks': []}
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Получить текущую цену."""
        instrument = self.find_real_instrument(ticker)
        if not instrument:
            return None
        
        def get_price_func(client):
            response = client.market_data.get_last_prices(figi=[instrument['figi']])
            
            if response.last_prices:
                price = quotation_to_decimal(response.last_prices[0].price)
                return float(price)
            
            return None
        
        try:
            return self._execute_with_client(get_price_func)
        except Exception as e:
            log.error(f"Ошибка получения цены {ticker}: {e}")
            return None
    
    # -----------------------------------------------------------------
    # МЕТОДЫ ДЛЯ ПОРТФЕЛЯ
    # -----------------------------------------------------------------
    
    def get_portfolio(self) -> Dict:
        """Получить портфель."""
        def get_portfolio_func(client):
            account_id = self._get_account_id(client)
            
            portfolio = client.operations.get_portfolio(account_id=account_id)
            
            result = {
                'account_id': account_id,
                'total_amount': float(quotation_to_decimal(portfolio.total_amount_portfolio)),
                'expected_yield': float(quotation_to_decimal(portfolio.expected_yield)),
                'positions': []
            }
            
            for pos in portfolio.positions:
                position = {
                    'figi': pos.figi,
                    'ticker': self._figi_to_ticker.get(pos.figi, pos.figi),
                    'quantity': float(quotation_to_decimal(pos.quantity)),
                    'instrument_type': pos.instrument_type
                }
                
                if pos.average_position_price:
                    position['average_price'] = float(quotation_to_decimal(pos.average_position_price))
                
                if pos.expected_yield:
                    position['expected_yield'] = float(quotation_to_decimal(pos.expected_yield))
                
                result['positions'].append(position)
            
            log.info(f"Получен портфель, позиций: {len(result['positions'])}")
            return result
        
        try:
            return self._execute_with_client(get_portfolio_func)
        except Exception as e:
            log.error(f"Ошибка получения портфеля: {e}")
            return {'positions': [], 'total_amount': 0}
    
    # -----------------------------------------------------------------
    # ТОРГОВЫЕ МЕТОДЫ
    # -----------------------------------------------------------------
    
    def place_order(self, ticker: str, quantity: int, direction: str, 
                   order_type: str = 'limit', price: float = None) -> Dict:
        """Разместить заявку."""
        instrument = self.find_real_instrument(ticker)
        if not instrument:
            return {'error': f'Инструмент {ticker} не найден'}
        
        if not instrument['api_trade_available_flag']:
            return {'error': f'Инструмент {ticker} недоступен для торговли через API'}
        
        def place_order_func(client):
            account_id = self._get_account_id(client)
            
            # Преобразуем параметры
            order_direction = OrderDirection.ORDER_DIRECTION_BUY if direction.lower() == 'buy' else OrderDirection.ORDER_DIRECTION_SELL
            
            if order_type.lower() == 'market':
                order_type_enum = OrderType.ORDER_TYPE_MARKET
                response = client.orders.post_order(
                    figi=instrument['figi'],
                    quantity=quantity,
                    direction=order_direction,
                    account_id=account_id,
                    order_type=order_type_enum
                )
            else:
                order_type_enum = OrderType.ORDER_TYPE_LIMIT
                if price is None:
                    return {'error': 'Для лимитной заявки нужна цена'}
                
                price_quotation = decimal_to_quotation(Decimal(str(price)))
                response = client.orders.post_order(
                    figi=instrument['figi'],
                    quantity=quantity,
                    price=price_quotation,
                    direction=order_direction,
                    account_id=account_id,
                    order_type=order_type_enum
                )
            
            result = {
                'order_id': response.order_id,
                'execution_report_status': response.execution_report_status.name,
                'message': response.message,
                'lots_requested': quantity,
                'lots_executed': response.lots_executed,
                'initial_order_price': float(quotation_to_decimal(response.initial_order_price)) if response.initial_order_price else None,
                'executed_order_price': float(quotation_to_decimal(response.executed_order_price)) if response.executed_order_price else None,
                'total_order_amount': float(quotation_to_decimal(response.total_order_amount)) if response.total_order_amount else None,
                'direction': direction,
                'ticker': ticker
            }
            
            log.info(f"Заявка размещена: {ticker} {direction} {quantity} лотов")
            return result
        
        try:
            return self._execute_with_client(place_order_func)
        except Exception as e:
            log.error(f"Ошибка размещения заявки {ticker}: {e}")
            return {'error': str(e)}
    
    def cancel_order(self, order_id: str) -> Dict:
        """Отменить заявку."""
        def cancel_order_func(client):
            account_id = self._get_account_id(client)
            
            response = client.orders.cancel_order(
                account_id=account_id,
                order_id=order_id
            )
            
            result = {
                'order_id': order_id,
                'time': response.time,
                'success': True
            }
            
            log.info(f"Заявка отменена: {order_id}")
            return result
        
        try:
            return self._execute_with_client(cancel_order_func)
        except Exception as e:
            log.error(f"Ошибка отмены заявки {order_id}: {e}")
            return {'error': str(e), 'success': False}
    
    def get_orders(self) -> List[Dict]:
        """Получить активные заявки."""
        def get_orders_func(client):
            account_id = self._get_account_id(client)
            
            response = client.orders.get_orders(account_id=account_id)
            
            orders = []
            for order in response.orders:
                ticker = self._figi_to_ticker.get(order.figi, order.figi)
                
                orders.append({
                    'order_id': order.order_id,
                    'ticker': ticker,
                    'figi': order.figi,
                    'direction': order.direction.name,
                    'order_type': order.order_type.name,
                    'quantity': order.lots_requested,
                    'executed': order.lots_executed,
                    'price': float(quotation_to_decimal(order.initial_order_price)) if order.initial_order_price else None,
                    'status': order.execution_report_status.name,
                    'stage': order.order_stage.name if hasattr(order, 'order_stage') else None
                })
            
            log.debug(f"Получено заявок: {len(orders)}")
            return orders
        
        try:
            return self._execute_with_client(get_orders_func)
        except Exception as e:
            log.error(f"Ошибка получения заявок: {e}")
            return []
    
    # -----------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # -----------------------------------------------------------------
    
    def test_connection(self) -> bool:
        """Тест подключения к API."""
        def test_connection_func(client):
            accounts = client.users.get_accounts()
            
            if accounts.accounts:
                log.success("✅ Подключение к T-Tech API успешно")
                
                for account in accounts.accounts[:3]:
                    log.info(f"  Счет: {account.name} ({account.id}) - {account.type}")
                
                return True
            else:
                log.error("❌ Не найдено счетов")
                return False
        
        try:
            return self._execute_with_client(test_connection_func)
        except Exception as e:
            log.error(f"❌ Ошибка подключения: {str(e)}")
            return False
    
    def verify_all_instruments(self) -> Dict[str, bool]:
        """Проверить доступность инструментов."""
        log.info("Проверка инструментов через API...")
        
        tickers = [
            'IMOEXF', 'MXI-3.26', 'MIX-3.26', 'RTS-3.26', 'RTSM-3.26',
            'CNY-3.26', 'CNYRUBF', 'Si-3.26', 'USDRUBF', 'Eu-3.26', 'EURRUBF'
        ]
        
        results = {}
        for ticker in tickers:
            info = self.find_real_instrument(ticker)
            if info and info['api_trade_available_flag']:
                results[ticker] = True
                log.success(f"✅ {ticker}: доступен (FIGI: {info['figi']})")
            else:
                results[ticker] = False
                log.warning(f"❌ {ticker}: недоступен")
        
        available = sum(results.values())
        log.info(f"📊 Доступно: {available}/{len(results)} инструментов")
        return results


# Глобальный экземпляр
api_client = TTechInvestAPIClient()