"""
Модуль для работы с историческими данными.
Загрузка, кэширование и обработка исторических котировок.
"""
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np

from t_tech.invest import (
    Client,
    CandleInterval,
    HistoricCandle,
    SecurityTradingStatus
)
from t_tech.invest.utils import quotation_to_decimal

from config.settings import settings
from config.instruments import get_all_tickers, get_instrument
from core.api_client import api_client
from utils.logger import log


class HistoricalData:
    """Класс для работы с историческими данными."""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Кэш данных
        self.cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.cache_expiry: Dict[str, datetime] = {}
        
        # Настройки кэша
        self.cache_durations = {
            '15m': timedelta(hours=1),
            '1h': timedelta(hours=4),
            '4h': timedelta(days=1),
            '1d': timedelta(days=7)
        }
        
        log.info(f"Инициализация исторических данных. Директория: {self.data_dir}")
    
    def load_data(self, 
                  ticker: str, 
                  timeframe: str = "1h",
                  days: int = 30,
                  force_update: bool = False) -> Optional[pd.DataFrame]:
        """
        Загрузить исторические данные для инструмента.
        
        Args:
            ticker: Тикер инструмента
            timeframe: Таймфрейм (15m, 1h, 4h, 1d)
            days: Количество дней истории
            force_update: Принудительное обновление данных
            
        Returns:
            DataFrame с историческими данными или None при ошибке
        """
        cache_key = f"{ticker}_{timeframe}"
        
        # Проверяем кэш
        if not force_update and self._is_cached_valid(cache_key, timeframe):
            log.debug(f"Используем кэшированные данные для {cache_key}")
            return self.cache.get(cache_key)
        
        try:
            log.info(f"Загрузка данных {ticker} ({timeframe}) за {days} дней...")
            
            # Получаем информацию об инструменте
            instrument_info = api_client.find_real_instrument(ticker)
            if not instrument_info:
                log.error(f"Инструмент {ticker} не найден")
                return None
            
            # Загружаем данные через API
            data = self._fetch_from_api(instrument_info['figi'], timeframe, days)
            
            if data is None or data.empty:
                log.warning(f"Нет данных для {ticker} ({timeframe})")
                return None
            
            # Обогащаем данными
            data = self._enrich_data(data, ticker)
            
            # Сохраняем в кэш
            self.cache[cache_key] = data
            self.cache_expiry[cache_key] = datetime.now()
            
            # Сохраняем в файл
            self._save_to_file(ticker, timeframe, data)
            
            log.success(f"Загружено {len(data)} свечей для {ticker} ({timeframe})")
            return data
            
        except Exception as e:
            log.error(f"Ошибка загрузки данных для {ticker}: {e}")
            
            # Пробуем загрузить из файла
            cached_data = self._load_from_file(ticker, timeframe)
            if cached_data is not None:
                log.info(f"Используем сохраненные данные для {ticker}")
                self.cache[cache_key] = cached_data
                return cached_data
            
            return None
    
    def _fetch_from_api(self, 
                       figi: str, 
                       timeframe: str, 
                       days: int) -> Optional[pd.DataFrame]:
        """Загрузить данные через T-Tech API."""
        try:
            interval = self._get_interval(timeframe)
            if interval is None:
                return None
            
            # Рассчитываем даты
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            all_candles = []
            
            # ИСПРАВЛЕНИЕ: используем _execute_with_client вместо connect()
            def fetch_candles(client):
                # Загружаем данные по частям (API может иметь ограничения)
                current_from = from_date
                
                while current_from < to_date:
                    current_to = min(current_from + timedelta(days=7), to_date)
                    
                    try:
                        candles = client.get_all_candles(
                            figi=figi,
                            from_=current_from,
                            to=current_to,
                            interval=interval
                        )
                        
                        all_candles.extend(candles)
                        
                    except Exception as e:
                        log.warning(f"Ошибка загрузки части данных: {e}")
                    
                    current_from = current_to
                
                return all_candles
            
            # Вызываем через _execute_with_client API клиента
            api_client._execute_with_client(fetch_candles)
            
            # Преобразуем в DataFrame
            if not all_candles:
                return None
            
            data = self._candles_to_dataframe(all_candles)
            return data
            
        except Exception as e:
            log.error(f"Ошибка API при загрузке данных: {e}")
            return None
    
    def _get_interval(self, timeframe: str) -> Optional[CandleInterval]:
        """Преобразовать строку таймфрейма в CandleInterval."""
        intervals = {
            '1m': CandleInterval.CANDLE_INTERVAL_1_MIN,
            '5m': CandleInterval.CANDLE_INTERVAL_5_MIN,
            '15m': CandleInterval.CANDLE_INTERVAL_15_MIN,
            '1h': CandleInterval.CANDLE_INTERVAL_HOUR,
            '4h': CandleInterval.CANDLE_INTERVAL_4_HOUR,
            '1d': CandleInterval.CANDLE_INTERVAL_DAY
        }
        return intervals.get(timeframe)
    
    def _candles_to_dataframe(self, candles: List[HistoricCandle]) -> pd.DataFrame:
        """Преобразовать список свечей в DataFrame."""
        data = []
        
        for candle in candles:
            row = {
                'time': candle.time,
                'open': float(quotation_to_decimal(candle.open)),
                'high': float(quotation_to_decimal(candle.high)),
                'low': float(quotation_to_decimal(candle.low)),
                'close': float(quotation_to_decimal(candle.close)),
                'volume': candle.volume,
                'is_complete': candle.is_complete
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            # Сортируем по времени
            df.sort_values('time', inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            # Добавляем временные индексы - ОБРАБАТЫВАЕМ ПУСТЫЕ ЗНАЧЕНИЯ
            df['timestamp'] = pd.to_datetime(df['time'], errors='coerce')
            # Удаляем строки с некорректными временными метками
            df = df.dropna(subset=['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def _enrich_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Обогатить данные техническими показателями."""
        if df.empty or len(df) < 50:  # Нужно достаточно данных для индикаторов
            log.warning(f"Недостаточно данных для обогащения: {len(df)} строк")
            # Добавляем только базовые колонки
            df = df.copy()
            df['ticker'] = ticker
            return df
        
        try:
            # Копируем чтобы не модифицировать оригинал
            df = df.copy()
            
            # Проверяем, что есть достаточное количество данных
            min_data = 200  # Максимальный период для индикаторов
            
            # Очищаем от NaN значений в ключевых колонках
            df['close'] = df['close'].ffill().bfill()
            df['high'] = df['high'].ffill().bfill()
            df['low'] = df['low'].ffill().bfill()
            df['volume'] = df['volume'].ffill().bfill()
            
            # Простые скользящие средние
            window_20 = min(20, len(df) // 2)  # Не более половины данных
            window_50 = min(50, len(df) // 2)
            window_200 = min(200, len(df) // 2)
            
            df['sma_20'] = df['close'].rolling(window=window_20, min_periods=1).mean()
            df['sma_50'] = df['close'].rolling(window=window_50, min_periods=1).mean()
            df['sma_200'] = df['close'].rolling(window=window_200, min_periods=1).mean()
            
            # Экспоненциальные скользящие средние
            df['ema_12'] = df['close'].ewm(span=min(12, len(df)), adjust=False, min_periods=1).mean()
            df['ema_26'] = df['close'].ewm(span=min(26, len(df)), adjust=False, min_periods=1).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=min(9, len(df)), adjust=False, min_periods=1).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=min(14, len(df)), min_periods=1).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=min(14, len(df)), min_periods=1).mean()
            rs = gain / loss
            rs = rs.replace([np.inf, -np.inf], np.nan).ffill().bfill()
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            bb_window = min(20, len(df) // 2)
            df['bb_middle'] = df['close'].rolling(window=bb_window, min_periods=1).mean()
            bb_std = df['close'].rolling(window=bb_window, min_periods=1).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # ATR (Average True Range)
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['atr'] = true_range.rolling(window=min(14, len(df)), min_periods=1).mean()
            
            # Объемные показатели
            df['volume_sma'] = df['volume'].rolling(window=min(20, len(df)), min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma'].replace(0, 1)  # Избегаем деления на ноль
            
            # Волатильность
            df['volatility'] = df['close'].pct_change().rolling(window=min(20, len(df)), min_periods=1).std() * 100
            
            # Ценовые изменения
            df['returns'] = df['close'].pct_change()
            df['log_returns'] = np.log(df['close'] / df['close'].shift())
            
            # Уровни поддержки/сопротивления (упрощенные)
            support_window = min(20, len(df) // 2)
            df['resistance'] = df['high'].rolling(window=support_window, min_periods=1).max()
            df['support'] = df['low'].rolling(window=support_window, min_periods=1).min()
            
            # Добавляем метку тикера
            df['ticker'] = ticker
            
            # Заполняем NaN значения
            df = df.ffill().bfill()
            
            log.debug(f"Данные обогащены: {len(df)} строк, {len(df.columns)} колонок")
            return df
            
        except Exception as e:
            log.error(f"Ошибка при обогащении данных для {ticker}: {e}")
            # Возвращаем исходные данные без индикаторов
            df = df.copy()
            df['ticker'] = ticker
            return df
    
    def _is_cached_valid(self, cache_key: str, timeframe: str) -> bool:
        """Проверить, действительны ли кэшированные данные."""
        if cache_key not in self.cache:
            return False
        
        if cache_key not in self.cache_expiry:
            return False
        
        expiry_duration = self.cache_durations.get(timeframe, timedelta(hours=1))
        cache_time = self.cache_expiry[cache_key]
        
        return datetime.now() - cache_time < expiry_duration
    
    def _save_to_file(self, ticker: str, timeframe: str, data: pd.DataFrame):
        """Сохранить данные в файл."""
        try:
            file_path = self.data_dir / f"{ticker}_{timeframe}.pkl"
            
            # Сохраняем с информацией о времени
            save_data = {
                'ticker': ticker,
                'timeframe': timeframe,
                'data': data,
                'saved_at': datetime.now(),
                'rows': len(data)
            }
            
            with open(file_path, 'wb') as f:
                pickle.dump(save_data, f)
            
            log.debug(f"Данные сохранены в файл: {file_path}")
            
        except Exception as e:
            log.error(f"Ошибка сохранения данных в файл: {e}")
    
    def _load_from_file(self, ticker: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Загрузить данные из файла."""
        try:
            file_path = self.data_dir / f"{ticker}_{timeframe}.pkl"
            
            if not file_path.exists():
                return None
            
            with open(file_path, 'rb') as f:
                saved_data = pickle.load(f)
            
            # Проверяем актуальность (не старше 7 дней)
            saved_at = saved_data.get('saved_at')
            if saved_at and (datetime.now() - saved_at).days > 7:
                log.debug(f"Файловые данные устарели: {file_path}")
                return None
            
            log.info(f"Загружены сохраненные данные из файла: {file_path}")
            return saved_data.get('data')
            
        except Exception as e:
            log.error(f"Ошибка загрузки данных из файла: {e}")
            return None
    
    def get_latest_data(self, 
                       ticker: str, 
                       timeframe: str = "1h",
                       limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Получить последние данные.
        
        Args:
            ticker: Тикер инструмента
            timeframe: Таймфрейм
            limit: Количество последних записей
            
        Returns:
            DataFrame с последними данными
        """
        data = self.load_data(ticker, timeframe)
        
        if data is None or data.empty:
            return None
        
        return data.tail(limit)
    
    def get_price_at_time(self,
                         ticker: str,
                         target_time: datetime,
                         timeframe: str = "1h") -> Optional[float]:
        """
        Получить цену на определенное время.
        
        Args:
            ticker: Тикер инструмента
            target_time: Время для получения цены
            timeframe: Таймфрейм
            
        Returns:
            Цена закрытия или None если данных нет
        """
        data = self.load_data(ticker, timeframe)
        
        if data is None or data.empty:
            return None
        
        # Ищем ближайшую свечу к указанному времени
        time_diff = (data.index - target_time).abs()
        if time_diff.min() > timedelta(hours=24):
            return None
        
        idx = time_diff.argmin()
        return data.iloc[idx]['close']
    
    def get_statistics(self, ticker: str, timeframe: str = "1h") -> Dict[str, Any]:
        """
        Получить статистику по историческим данным.
        
        Args:
            ticker: Тикер инструмента
            timeframe: Таймфрейм
            
        Returns:
            Словарь со статистикой
        """
        data = self.load_data(ticker, timeframe)
        
        if data is None or data.empty:
            return {}
        
        stats = {
            'ticker': ticker,
            'timeframe': timeframe,
            'period_start': data.index[0],
            'period_end': data.index[-1],
            'total_candles': len(data),
            'price_stats': {
                'current': float(data['close'].iloc[-1]),
                'high': float(data['high'].max()),
                'low': float(data['low'].min()),
                'mean': float(data['close'].mean()),
                'std': float(data['close'].std())
            },
            'volume_stats': {
                'current': int(data['volume'].iloc[-1]),
                'average': float(data['volume'].mean()),
                'max': int(data['volume'].max())
            },
            'volatility': {
                'daily': float(data['returns'].std() * 100) if 'returns' in data else 0,
                'atr': float(data['atr'].iloc[-1]) if 'atr' in data else 0
            },
            'indicators': {
                'sma_20': float(data['sma_20'].iloc[-1]) if 'sma_20' in data else None,
                'sma_50': float(data['sma_50'].iloc[-1]) if 'sma_50' in data else None,
                'rsi': float(data['rsi'].iloc[-1]) if 'rsi' in data else None,
                'macd': float(data['macd'].iloc[-1]) if 'macd' in data else None
            }
        }
        
        return stats
    
    def clear_cache(self, ticker: str = None, timeframe: str = None):
        """
        Очистить кэш данных.
        
        Args:
            ticker: Очистить только для этого тикера
            timeframe: Очистить только для этого таймфрейма
        """
        if ticker and timeframe:
            cache_key = f"{ticker}_{timeframe}"
            if cache_key in self.cache:
                del self.cache[cache_key]
                del self.cache_expiry[cache_key]
                log.info(f"Кэш очищен для {cache_key}")
        elif ticker:
            # Удаляем все таймфреймы для тикера
            keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{ticker}_")]
            for key in keys_to_delete:
                del self.cache[key]
                del self.cache_expiry[key]
            log.info(f"Кэш очищен для тикера {ticker}")
        else:
            self.cache.clear()
            self.cache_expiry.clear()
            log.info("Весь кэш исторических данных очищен")


# Глобальный экземпляр
historical_data = HistoricalData()