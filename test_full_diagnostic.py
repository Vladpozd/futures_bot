# test_advanced_diagnostic.py
from t_tech.invest import Client

client = Client("dummy_token")

print("=== РАСШИРЕННАЯ ДИАГНОСТИКА CLIENT ===")

print("1. Все публичные атрибуты Client:")
all_attrs = [attr for attr in dir(client) if not attr.startswith('_')]
for attr in all_attrs:
    print(f"  - {attr}")

print("\n2. Проверяем какие методы можно вызвать:")
callable_methods = []
for attr in all_attrs:
    try:
        obj = getattr(client, attr)
        if callable(obj):
            callable_methods.append(attr)
            # Пробуем посмотреть сигнатуру (без вызова)
            print(f"  ✓ {attr}() - вызываемый")
    except:
        pass

print(f"\n3. Всего вызываемых методов: {len(callable_methods)}")

print("\n4. Проверяем есть ли методы с 'service' в названии:")
service_methods = [m for m in all_attrs if 'service' in m.lower()]
for method in service_methods:
    print(f"  - {method}")

print("\n5. Пробуем создать клиент с реальными параметрами:")
try:
    # Импортируем настройки
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.settings import settings
    
    print(f"  Токен: {'установлен' if hasattr(settings, 'TINKOFF_TOKEN') else 'отсутствует'}")
    print(f"  Режим песочницы: {getattr(settings, 'SANDBOX_MODE', 'неизвестно')}")
    
    # Пробуем создать клиента с реальным токеном
    if hasattr(settings, 'TINKOFF_TOKEN') and settings.TINKOFF_TOKEN:
        try:
            real_client = Client(token=settings.TINKOFF_TOKEN)
            print("  ✓ Клиент создан с реальным токеном")
            
            # Проверяем методы
            print("  Методы реального клиента (первые 5):")
            real_attrs = [attr for attr in dir(real_client) if not attr.startswith('_')]
            for attr in real_attrs[:5]:
                print(f"    - {attr}")
                
        except Exception as e:
            print(f"  ✗ Ошибка создания клиента: {e}")
    else:
        print("  ℹ️ Токен не найден в настройках")
        
except ImportError:
    print("  ℹ️ Не удалось импортировать настройки")
except Exception as e:
    print(f"  ✗ Ошибка: {e}")

print("\n6. Проверяем документацию по Client:")
try:
    print(f"  Документация: {Client.__doc__[:200] if Client.__doc__ else 'отсутствует'}...")
except:
    print("  ℹ️ Документация недоступна")