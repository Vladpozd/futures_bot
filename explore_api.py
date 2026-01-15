# run_multi_tf_test.py
import sys
from pathlib import Path

# Добавляем путь к проекту
root_dir = Path(__file__).parent
sys.path.append(str(root_dir))

def main():
    """Главная функция для теста многотаймфреймного анализа"""
    print("\n" + "="*70)
    print("🤖 ТЕСТ МУЛЬТИТАЙМФРЕЙМНОГО АНАЛИЗА")
    print("="*70)
    
    try:
        # Сначала исправляем циклические импорты "на лету"
        import core
        
        # Проверяем, что core.__init__ не импортирует data
        print("✅ core модули загружены")
        
        # Теперь можем импортировать анализатор
        from analysis.analyzer import MarketAnalyzer
        
        print("✅ Анализатор загружен")
        
        # Запускаем анализ
        analyzer = MarketAnalyzer()
        ticker = "IMOEXF"
        timeframes = ['15m', '1h', '4h', '1d']
        
        results = {}
        
        print(f"\n🔍 Запускаю анализ {ticker} на {len(timeframes)} таймфреймах...")
        print("-"*70)
        
        for tf in timeframes:
            print(f"Анализ {tf}...", end=" ", flush=True)
            
            try:
                result = analyzer.comprehensive_analysis(ticker, tf)
                results[tf] = result
                
                signal = result['integrated_signal']
                print(f"✅ {signal['direction']} (сила: {signal['strength']}%, "
                      f"вероятность: {result['final_probability']:.1%})")
                
            except Exception as e:
                print(f"❌ Ошибка: {str(e)[:50]}...")
                results[tf] = None
        
        # Выводим сводку
        print("\n" + "="*70)
        print("📊 РЕЗУЛЬТАТЫ АНАЛИЗА")
        print("="*70)
        
        print(f"\n{'Таймфрейм':<8} {'Сигнал':<8} {'Сила':<8} {'Вероятность':<12} {'Позиция':<15}")
        print("-"*70)
        
        for tf in timeframes:
            if results[tf]:
                r = results[tf]
                signal = r['integrated_signal']
                
                signal_emoji = "🟢" if signal['direction'] == 'BUY' else "🔴" if signal['direction'] == 'SELL' else "⚪"
                position = "✅ ОТКРЫВАТЬ" if r['can_open_position'] else "⏸️ ЖДАТЬ"
                
                print(f"{tf:<8} {signal_emoji} {signal['direction']:<7} "
                      f"{signal['strength']:<7.1f}% "
                      f"{r['final_probability']:<11.1%} "
                      f"{position:<15}")
            else:
                print(f"{tf:<8} ❌ ОШИБКА")
        
        # Анализ согласованности
        valid_results = [r for r in results.values() if r]
        if valid_results:
            signals = [r['integrated_signal']['direction'] for r in valid_results]
            
            buy_count = signals.count('BUY')
            sell_count = signals.count('SELL') 
            neutral_count = signals.count('NEUTRAL')
            
            print(f"\n🎯 Согласованность: BUY={buy_count}, SELL={sell_count}, NEUTRAL={neutral_count}")
            
            if buy_count > sell_count and buy_count > neutral_count:
                print("🎯 ОБЩИЙ СИГНАЛ: BUY 🟢")
            elif sell_count > buy_count and sell_count > neutral_count:
                print("🎯 ОБЩИЙ СИГНАЛ: SELL 🔴")
            else:
                print("🎯 ОБЩИЙ СИГНАЛ: NEUTRAL ⚪")
        
        print("\n" + "="*70)
        print("✅ ТЕСТ ЗАВЕРШЕН")
        print("="*70)
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("\nСовет: Исправьте циклические импорты:")
        print("1. В core/__init__.py удалите: 'from data.history import historical_data'")
        print("2. В data/__init__.py удалите: 'from core.api_client import api_client'")
        print("3. Перезапустите скрипт")
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()