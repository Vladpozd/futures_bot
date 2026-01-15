
#!/usr/bin/env python3
"""
Тестовый запуск бота для проверки всех компонентов.
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from core.api_client import api_client
from utils.logger import log

def test_components():
    """Тест всех компонентов бота."""
    print("\n" + "="*60)
    print("🧪 ТЕСТ КОМПОНЕНТОВ БОТА")
    print("="*60)
    
    # 1. Проверяем настройки
    print("\n1. Проверка настроек...")
    print(f"   Режим: {'ПЕСОЧНИЦА' if settings.SANDBOX_MODE else 'РЕАЛЬНЫЙ СЧЕТ'}")
    print(f"   Депозит: {settings.INITIAL_DEPOSIT:.2f} руб")
    print(f"   Плечо: {settings.MIN_LEVERAGE}x - {settings.MAX_LEVERAGE}x")
    print(f"   Минимальная вероятность: {settings.MIN_PROBABILITY:.0%}")
    print("   ✅ Настройки загружены")
    
    # 2. Проверяем подключение к API
    print("\n2. Проверка подключения к Tinkoff API...")
    if api_client.test_connection():
        print("   ✅ Подключение к API успешно")
    else:
        print("   ❌ Ошибка подключения к API")
        return False
    
    # 3. Проверяем инструменты
    print("\n3. Проверка доступности инструментов...")
    results = api_client.verify_all_instruments()
    available = sum(results.values())
    total = len(results)
    print(f"   Доступно инструментов: {available}/{total}")
    
    if available == 0:
        print("   ⚠️ Нет доступных инструментов")
        return False
    
    print("   ✅ Инструменты проверены")
    
    # 4. Проверяем основные модули
    print("\n4. Проверка основных модулей...")
    
    try:
        from analysis.analyzer import market_analyzer
        print("   ✅ Анализатор загружен")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки анализатора: {e}")
        return False
    
    try:
        from trading.position_sizing import position_sizing
        print("   ✅ Калькулятор позиций загружен")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки калькулятора позиций: {e}")
        return False
    
    try:
        from trading.risk_manager import risk_manager
        print("   ✅ Менеджер рисков загружен")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки менеджера рисков: {e}")
        return False
    
    try:
        from trading.order_executor import order_executor
        print("   ✅ Исполнитель ордеров загружен")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки исполнителя ордеров: {e}")
        return False
    
    # 5. Проверяем портфель
    print("\n5. Проверка менеджера портфеля...")
    try:
        from core.portfolio import portfolio_manager
        stats = portfolio_manager.get_stats()
        print(f"   Депозит: {stats['current_deposit']:.2f} руб")
        print("   ✅ Портфель загружен")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки портфеля: {e}")
        return False
    
    # 6. Проверяем исторические данные
    print("\n6. Проверка исторических данных...")
    try:
        from data.history import historical_data
        # Пробуем загрузить данные для одного инструмента
        data = historical_data.load_data("Si-3.26", "1h", days=1, force_update=False)
        if data is not None:
            print(f"   Данные загружены: {len(data)} свечей")
            print("   ✅ Исторические данные работают")
        else:
            print("   ⚠️ Нет исторических данных (может быть нормально при первом запуске)")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки исторических данных: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ ВСЕ КОМПОНЕНТЫ ГОТОВЫ К РАБОТЕ!")
    print("="*60)
    
    return True

def main():
    """Главная функция теста."""
    try:
        if test_components():
            print("\n🚀 Бот готов к запуску!")
            print("\nЧтобы запустить бота, выполните:")
            print("  python bot/run.py")
            print("\nИли запустите главный цикл:")
            print("  from bot.main import main")
            print("  main()")
        else:
            print("\n❌ Обнаружены проблемы с компонентами бота.")
            print("Проверьте .env файл и настройки подключения.")
            
    except Exception as e:
        print(f"\n❌ Критическая ошибка при тестировании: {e}")
        print("Проверьте структуру проекта и зависимости.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())