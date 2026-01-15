"""
Главный анализатор, объединяющий все методы анализа.
Теперь с правильной системой расчета вероятности.
"""
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from data.history import HistoricalData
from analysis.technical.indicators import tech_indicators, IndicatorResult
from analysis.technical.psychological import psychological_levels
from analysis.patterns.basic_patterns import pattern_detector, PatternDetection
from analysis.elliott.waves import elliott_waves_analyzer
from analysis.gaps.analyzer import gap_analyzer
from analysis.imbalances.analyzer import imbalance_analyzer
from analysis.orderbook.analyzer import orderbook_analyzer
from analysis.probability_calculator import probability_calculator

from config.instruments import get_all_tickers
from utils.logger import log


class MarketAnalyzer:
    """
    Главный класс для анализа рынка.
    Объединяет все 8 методов анализа из требований.
    """
    
    def __init__(self):
        self.historical_data = HistoricalData()
        self.analysis_cache = {}
        self.probability_calculator = probability_calculator
        
        log.info("Инициализация комплексного анализатора рынка")
    
    def comprehensive_analysis(self, ticker: str, timeframe_str: str = "1h") -> Dict[str, Any]:
        """
        Полный комплексный анализ инструмента на выбранном таймфрейме.
        Объединяет все 8 модулей анализа.
        
        Args:
            ticker: Тикер инструмента
            timeframe_str: '15m', '1h', '4h', '1d'
            
        Returns:
            Словарь со всеми результатами анализа и итоговой вероятностью
        """
        cache_key = f"{ticker}_{timeframe_str}"
        
        # Проверяем кэш (сохраняем на 5 минут)
        if cache_key in self.analysis_cache:
            cached_time, cached_result = self.analysis_cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < 300:  # 5 минут
                log.debug(f"Используем кэшированный анализ: {cache_key}")
                return cached_result.copy()
        
        try:
            # Загружаем данные
            df = self.historical_data.load_data(ticker, timeframe_str)
            
            if df.empty:
                log.warning(f"Нет данных для анализа {ticker} {timeframe_str}")
                return self._get_empty_analysis(ticker, timeframe_str)
            
            # Выполняем все 8 видов анализа
            analysis_results = {}
            
            # 1. Технический анализ (20% веса)
            technical_analysis = self._analyze_technical(df, ticker)
            analysis_results['technical'] = technical_analysis
            
            # 2. Графические паттерны (25% веса)
            patterns_analysis = self._analyze_patterns(df)
            analysis_results['patterns'] = patterns_analysis
            
            # 3. Волны Эллиота (15% веса)
            elliott_analysis = self._analyze_elliott(df)
            analysis_results['elliott'] = elliott_analysis
            
            # 4. Гэпы (10% веса)
            gaps_analysis = self._analyze_gaps(df, ticker)
            analysis_results['gaps'] = gaps_analysis
            
            # 5. Имбалансы (10% веса)
            imbalances_analysis = self._analyze_imbalances(df)
            analysis_results['imbalances'] = imbalances_analysis
            
            # 6. Психологические уровни (10% веса)
            psychological_analysis = self._analyze_psychological(df, ticker)
            analysis_results['psychological'] = psychological_analysis
            
            # 7. Анализ стакана (10% веса) - если доступно
            orderbook_analysis = self._analyze_orderbook(ticker)
            analysis_results['orderbook'] = orderbook_analysis
            
            # Рассчитываем итоговую вероятность на основе всех модулей
            probability_result = self.probability_calculator.calculate_probability(analysis_results)
            
            # Генерируем итоговый сигнал
            integrated_signal = self._generate_integrated_signal(analysis_results, probability_result)
            
            # Формируем полный результат анализа
            analysis = {
                'ticker': ticker,
                'timeframe': timeframe_str,
                'timestamp': datetime.now().isoformat(),
                'current_price': float(df['close'].iloc[-1]),
                'volume': int(df['volume'].iloc[-1]),
                
                # Результаты всех модулей анализа
                'technical_analysis': technical_analysis,
                'patterns_analysis': patterns_analysis,
                'elliott_analysis': elliott_analysis,
                'gaps_analysis': gaps_analysis,
                'imbalances_analysis': imbalances_analysis,
                'psychological_analysis': psychological_analysis,
                'orderbook_analysis': orderbook_analysis,
                
                # Итоговые результаты
                'integrated_signal': integrated_signal,
                'probability_result': probability_result,
                'final_probability': probability_result['final_probability'],
                'can_open_position': probability_result['can_open_position'],
                'position_size_category': probability_result['position_size_category'],
                
                # Рекомендации для торговли
                'trading_recommendations': self._generate_trading_recommendations(
                    analysis_results, probability_result, df
                )
            }
            
            # Сохраняем в кэш
            self.analysis_cache[cache_key] = (datetime.now(), analysis.copy())
            
            log.info(f"✅ Анализ {ticker} {timeframe_str} завершен. "
                    f"Вероятность: {probability_result['final_probability']:.1%}, "
                    f"Сигнал: {integrated_signal['direction']}")
            
            return analysis
            
        except Exception as e:
            log.error(f"❌ Ошибка анализа {ticker}: {e}", exc_info=True)
            return self._get_empty_analysis(ticker, timeframe_str)
    
    def analyze_all_timeframes(self, ticker: str) -> Dict[str, Dict[str, Any]]:
        """
        Проанализировать инструмент на всех таймфреймах.
        """
        results = {}
        
        for timeframe in ['15m', '1h', '4h', '1d']:
            result = self.comprehensive_analysis(ticker, timeframe)
            results[timeframe] = result
        
        return results
    
    def _analyze_technical(self, df: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """Комплексный технический анализ"""
        if df.empty:
            return {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}}
        
        try:
            # Получаем все индикаторы
            indicators = tech_indicators.calculate_all(df)
            
            # Анализируем сигналы индикаторов
            buy_signals = 0
            sell_signals = 0
            total_strength = 0
            signals_count = 0
            
            for key, indicator in indicators.items():
                if indicator.signal == 'BUY':
                    buy_signals += 1
                    total_strength += indicator.strength
                    signals_count += 1
                elif indicator.signal == 'SELL':
                    sell_signals += 1
                    total_strength += indicator.strength
                    signals_count += 1
            
            # Определяем общий сигнал
            if buy_signals > sell_signals:
                signal = 'BUY'
                signal_strength = buy_signals / max(1, buy_signals + sell_signals)
            elif sell_signals > buy_signals:
                signal = 'SELL'
                signal_strength = sell_signals / max(1, buy_signals + sell_signals)
            else:
                signal = 'NEUTRAL'
                signal_strength = 0.5
            
            # Рассчитываем среднюю силу
            avg_strength = total_strength / max(1, signals_count)
            
            # Рассчитываем итоговый score (0-1)
            if signal != 'NEUTRAL':
                score = 0.5 + (signal_strength - 0.5) * (avg_strength / 100)
            else:
                score = 0.5
            
            # Уверенность на основе количества сигналов и силы
            confidence = min(1.0, (signals_count / 10) * (avg_strength / 100))
            
            return {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': {
                    'buy_signals': buy_signals,
                    'sell_signals': sell_signals,
                    'avg_strength': avg_strength,
                    'indicators_count': len(indicators)
                }
            }
            
        except Exception as e:
            log.error(f"Ошибка технического анализа: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _analyze_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ графических паттернов"""
        if len(df) < 10:
            return {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}}
        
        try:
            highs = df['high'].tolist()
            lows = df['low'].tolist()
            closes = df['close'].tolist()
            
            # Используем детектор паттернов
            patterns = pattern_detector.detect_all_patterns(highs, lows, closes)
            
            # Анализируем найденные паттерны
            buy_patterns = 0
            sell_patterns = 0
            total_confidence = 0
            patterns_count = len(patterns)
            
            for pattern in patterns:
                if pattern.signal == 'BUY':
                    buy_patterns += 1
                elif pattern.signal == 'SELL':
                    sell_patterns += 1
                total_confidence += pattern.confidence
            
            # Определяем сигнал
            if buy_patterns > sell_patterns:
                signal = 'BUY'
                pattern_score = 0.5 + (buy_patterns / max(1, patterns_count)) * 0.5
            elif sell_patterns > buy_patterns:
                signal = 'SELL'
                pattern_score = 0.5 - (sell_patterns / max(1, patterns_count)) * 0.5
            else:
                signal = 'NEUTRAL'
                pattern_score = 0.5
            
            # Рассчитываем уверенность
            avg_confidence = total_confidence / max(1, patterns_count) / 100
            confidence = min(1.0, avg_confidence * (patterns_count / 5))
            
            return {
                'score': min(1.0, max(0.0, pattern_score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': {
                    'patterns_found': patterns_count,
                    'buy_patterns': buy_patterns,
                    'sell_patterns': sell_patterns,
                    'avg_confidence': avg_confidence
                }
            }
            
        except Exception as e:
            log.error(f"Ошибка анализа паттернов: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _analyze_elliott(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ волн Эллиота"""
        if len(df) < 50:  # Нужно больше данных для волнового анализа
            return {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}}
        
        try:
            # Используем анализатор волн Эллиота
            waves_analysis = elliott_waves_analyzer.analyze(df)
            
            # Извлекаем результаты
            score = waves_analysis.get('score', 0.5)
            confidence = waves_analysis.get('confidence', 0.5)
            signal = waves_analysis.get('signal', 'NEUTRAL')
            
            return {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': waves_analysis.get('details', {})
            }
            
        except Exception as e:
            log.error(f"Ошибка анализа волн Эллиота: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _analyze_gaps(self, df: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """Анализ гэпов"""
        if len(df) < 10:
            return {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}}
        
        try:
            # Используем анализатор гэпов
            gaps_analysis = gap_analyzer.analyze(df, ticker)
            
            # Извлекаем результаты
            score = gaps_analysis.get('score', 0.5)
            confidence = gaps_analysis.get('confidence', 0.5)
            signal = gaps_analysis.get('signal', 'NEUTRAL')
            
            return {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': gaps_analysis.get('details', {})
            }
            
        except Exception as e:
            log.error(f"Ошибка анализа гэпов: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _analyze_imbalances(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Анализ имбалансов"""
        if len(df) < 10:
            return {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}}
        
        try:
            # Используем анализатор имбалансов
            imbalances_analysis = imbalance_analyzer.analyze(df)
            
            # Извлекаем результаты
            score = imbalances_analysis.get('score', 0.5)
            confidence = imbalances_analysis.get('confidence', 0.5)
            signal = imbalances_analysis.get('signal', 'NEUTRAL')
            
            return {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': imbalances_analysis.get('details', {})
            }
            
        except Exception as e:
            log.error(f"Ошибка анализа имбалансов: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _analyze_psychological(self, df: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """Анализ психологических уровней"""
        if df.empty:
            return {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}}
        
        try:
            current_price = df['close'].iloc[-1]
            
            # Получаем психологические уровни
            levels = psychological_levels.get_psychological_levels(current_price, ticker)
            
            # Проверяем, находится ли цена на психологическом уровне
            is_at_level = psychological_levels.is_psychological_level(current_price)
            
            # Безопасно получаем ближайшие уровни
            below_levels = levels.get('below', [])
            above_levels = levels.get('above', [])
            
            # Устанавливаем значения по умолчанию если списки пустые
            if not below_levels:
                nearest_below = current_price * 0.95
                below_levels = [nearest_below]
            else:
                nearest_below = below_levels[0]
            
            if not above_levels:
                nearest_above = current_price * 1.05
                above_levels = [nearest_above]
            else:
                nearest_above = above_levels[0]
            
            # Рассчитываем расстояние до уровней
            distance_to_below = (current_price - nearest_below) / current_price
            distance_to_above = (nearest_above - current_price) / current_price
            
            # Определяем сигнал на основе положения относительно уровней
            if distance_to_below < 0.01:  # Очень близко к уровню снизу (<1%)
                signal = 'SELL'  # Ожидаем отскока вниз
                score = 0.7
                confidence = 0.8
            elif distance_to_above < 0.01:  # Очень близко к уровню сверху (<1%)
                signal = 'BUY'  # Ожидаем пробития вверх
                score = 0.7
                confidence = 0.8
            elif distance_to_below < distance_to_above:
                signal = 'BUY'  # Ближе к поддержке
                score = 0.6
                confidence = 0.6
            else:
                signal = 'SELL'  # Ближе к сопротивлению
                score = 0.6
                confidence = 0.6
            
            return {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': {
                    'is_at_level': is_at_level,
                    'distance_to_below': distance_to_below,
                    'distance_to_above': distance_to_above,
                    'levels': levels
                }
            }
            
        except Exception as e:
            log.error(f"Ошибка анализа психологических уровней: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _analyze_orderbook(self, ticker: str) -> Dict[str, Any]:
        """Анализ стакана (Level 2)"""
        try:
            # Используем анализатор стакана
            orderbook_analysis = orderbook_analyzer.analyze(ticker)
            
            # Извлекаем результаты
            score = orderbook_analysis.get('score', 0.5)
            confidence = orderbook_analysis.get('confidence', 0.5)
            signal = orderbook_analysis.get('signal', 'NEUTRAL')
            
            return {
                'score': min(1.0, max(0.0, score)),
                'confidence': min(1.0, max(0.1, confidence)),
                'signal': signal,
                'details': orderbook_analysis.get('details', {})
            }
            
        except Exception as e:
            log.error(f"Ошибка анализа стакана: {e}")
            return {'score': 0.5, 'confidence': 0.1, 'signal': 'NEUTRAL', 'details': {'error': str(e)}}
    
    def _generate_integrated_signal(self, analysis_results: Dict[str, Any], 
                                   probability_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация итогового интегрированного сигнала.
        Объединяет результаты всех модулей с учетом вероятности.
        """
        # Собираем все сигналы
        signals = []
        signals_weights = []
        
        for module_name, module_data in analysis_results.items():
            signal = module_data.get('signal', 'NEUTRAL')
            confidence = module_data.get('confidence', 0.5)
            
            # Конвертируем в числовое значение
            if signal == 'BUY':
                signal_value = 1.0
            elif signal == 'SELL':
                signal_value = -1.0
            else:  # NEUTRAL
                signal_value = 0.0
            
            signals.append(signal_value)
            signals_weights.append(confidence)
        
        # Рассчитываем взвешенное среднее
        if not signals:
            return {'direction': 'NEUTRAL', 'strength': 0, 'confidence': 0}
        
        weighted_sum = sum(s * w for s, w in zip(signals, signals_weights))
        total_weight = sum(signals_weights)
        
        if total_weight > 0:
            weighted_signal = weighted_sum / total_weight
        else:
            weighted_signal = sum(signals) / len(signals)
        
        # Определяем направление и силу
        if weighted_signal > 0.1:
            direction = 'BUY'
            strength = min(100, weighted_signal * 100)
        elif weighted_signal < -0.1:
            direction = 'SELL'
            strength = min(100, abs(weighted_signal) * 100)
        else:
            direction = 'NEUTRAL'
            strength = 0
        
        # Уверенность на основе согласованности сигналов
        consistency = probability_result.get('signal_consistency', 0.5)
        
        return {
            'direction': direction,
            'strength': round(strength, 1),
            'confidence': round(consistency * 100, 1),
            'weighted_signal': weighted_signal,
            'signals_count': len(signals)
        }
    
    def _generate_trading_recommendations(self, analysis_results: Dict[str, Any],
                                        probability_result: Dict[str, Any],
                                        df: pd.DataFrame) -> Dict[str, Any]:
        """
        Генерация рекомендаций для торговли.
        """
        if df.empty:
            return {}
        
        current_price = float(df['close'].iloc[-1])
        final_probability = probability_result.get('final_probability', 0.5)
        can_open = probability_result.get('can_open_position', False)
        
        # Базовые рекомендации
        recommendations = {
            'open_position': can_open,
            'position_size_percentage': probability_calculator.calculate_position_size_percentage(
                final_probability
            ),
            'probability_category': probability_result.get('position_size_category', 'NONE'),
            'minimum_profit_target': current_price * 1.00091  # 0.091% минимум
        }
        
        # Если можно открывать позицию - добавляем детали
        if can_open:
            # Определяем предполагаемое направление
            integrated_signal = self._generate_integrated_signal(analysis_results, probability_result)
            direction = integrated_signal.get('direction', 'NEUTRAL')
            
            # Рассчитываем уровни стоп-лосса и тейк-профита
            atr = self._calculate_atr(df, period=14)
            
            if direction == 'BUY':
                recommendations['action'] = 'BUY'
                recommendations['stop_loss'] = current_price - (atr * 2)
                recommendations['take_profit'] = current_price + (atr * 3)
                recommendations['risk_reward'] = 1.5
            elif direction == 'SELL':
                recommendations['action'] = 'SELL'
                recommendations['stop_loss'] = current_price + (atr * 2)
                recommendations['take_profit'] = current_price - (atr * 3)
                recommendations['risk_reward'] = 1.5
            else:
                recommendations['action'] = 'WAIT'
        
        return recommendations
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Рассчитать Average True Range (ATR) для определения волатильности"""
        if len(df) < period + 1:
            return df['close'].std() if len(df) > 1 else 0
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR
        atr = tr.rolling(window=period).mean()
        
        return float(atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0)
    
    def _get_empty_analysis(self, ticker: str, timeframe: str) -> Dict[str, Any]:
        """Пустой анализ при ошибке"""
        empty_probability = {
            'final_probability': 0.0,
            'weighted_components': {},
            'signal_consistency': 0.0,
            'can_open_position': False,
            'position_size_category': 'NONE',
            'thresholds': probability_calculator.thresholds,
            'confidence_level': 'VERY_LOW'
        }
        
        return {
            'ticker': ticker,
            'timeframe': timeframe,
            'timestamp': datetime.now().isoformat(),
            'current_price': 0,
            'volume': 0,
            'technical_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'patterns_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'elliott_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'gaps_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'imbalances_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'psychological_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'orderbook_analysis': {'score': 0.5, 'confidence': 0.0, 'signal': 'NEUTRAL', 'details': {}},
            'integrated_signal': {'direction': 'NEUTRAL', 'strength': 0, 'confidence': 0},
            'probability_result': empty_probability,
            'final_probability': 0.0,
            'can_open_position': False,
            'position_size_category': 'NONE',
            'trading_recommendations': {}
        }
    
    def clear_cache(self):
        """Очистить кэш анализа"""
        self.analysis_cache.clear()
        log.info("Кэш анализа очищен")
    
    def get_analysis_summary(self, ticker: str, timeframe: str = "1h") -> Dict[str, Any]:
        """
        Получить краткую сводку анализа.
        """
        full_analysis = self.comprehensive_analysis(ticker, timeframe)
        
        # Извлекаем ключевую информацию
        summary = {
            'ticker': ticker,
            'timeframe': timeframe,
            'current_price': full_analysis.get('current_price', 0),
            'signal': full_analysis.get('integrated_signal', {}).get('direction', 'NEUTRAL'),
            'signal_strength': full_analysis.get('integrated_signal', {}).get('strength', 0),
            'probability': full_analysis.get('final_probability', 0),
            'can_open_position': full_analysis.get('can_open_position', False),
            'position_size': full_analysis.get('position_size_category', 'NONE'),
            'timestamp': full_analysis.get('timestamp', '')
        }
        
        return summary


# Глобальный экземпляр
market_analyzer = MarketAnalyzer()


def test_market_analyzer():
    """Тест комплексного анализатора"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ КОМПЛЕКСНОГО АНАЛИЗАТОРА")
    print("="*60)
    
    analyzer = MarketAnalyzer()
    
    # Тестируем на одном инструменте
    test_ticker = "IMOEXF"
    test_timeframe = "1h"
    
    print(f"Тестируем {test_ticker} на таймфрейме {test_timeframe}...")
    
    try:
        # Выполняем анализ
        analysis = analyzer.comprehensive_analysis(test_ticker, test_timeframe)
        
        # Выводим основные результаты
        print(f"\n📊 РЕЗУЛЬТАТЫ АНАЛИЗА:")
        print(f"Инструмент: {analysis['ticker']}")
        print(f"Таймфрейм: {analysis['timeframe']}")
        print(f"Цена: {analysis['current_price']:.2f}")
        print(f"Объем: {analysis['volume']}")
        
        print(f"\n🎯 ИТОГОВЫЙ СИГНАЛ:")
        signal = analysis['integrated_signal']
        print(f"Направление: {signal['direction']}")
        print(f"Сила: {signal['strength']}%")
        print(f"Уверенность: {signal['confidence']}%")
        
        print(f"\n📈 ВЕРОЯТНОСТЬ:")
        prob_result = analysis['probability_result']
        print(f"Вероятность успеха: {prob_result['final_probability']:.1%}")
        print(f"Открывать позицию: {'ДА' if prob_result['can_open_position'] else 'НЕТ'}")
        print(f"Размер позиции: {prob_result['position_size_category']}")
        
        print(f"\n🔍 РЕКОМЕНДАЦИИ:")
        rec = analysis['trading_recommendations']
        if rec.get('open_position'):
            print(f"Действие: {rec.get('action')}")
            print(f"Размер позиции: {rec.get('position_size_percentage'):.1f}% депозита")
            print(f"Стоп-лосс: {rec.get('stop_loss', 0):.2f}")
            print(f"Тейк-профит: {rec.get('take_profit', 0):.2f}")
            print(f"Risk/Reward: {rec.get('risk_reward', 0):.2f}")
        else:
            print("Ожидать лучших условий")
        
        print(f"\n⚙️ ДЕТАЛИ МОДУЛЕЙ:")
        modules = ['technical_analysis', 'patterns_analysis', 'elliott_analysis', 
                  'gaps_analysis', 'imbalances_analysis', 'psychological_analysis']
        
        for module in modules:
            if module in analysis:
                data = analysis[module]
                print(f"{module.replace('_analysis', '').upper()}: "
                      f"{data.get('signal', 'NEUTRAL')} "
                      f"(score: {data.get('score', 0):.2f}, "
                      f"conf: {data.get('confidence', 0):.2f})")
        
        print("\n" + "="*60)
        print("✅ ТЕСТ ЗАВЕРШЕН")
        print("="*60)
        
        return analysis
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Запуск теста при прямом выполнении файла
    test_result = test_market_analyzer()