# test_client_structure.py
from t_tech.invest import Client

# Попробуем создать клиент как в примерах
try:
    client = Client("dummy_token_for_test")
    print("✓ Client создан")
    
    # Проверяем наличие атрибутов
    print("\nПроверяем атрибуты Client:")
    print(f"  hasattr(client, 'instruments'): {hasattr(client, 'instruments')}")
    print(f"  hasattr(client, 'users'): {hasattr(client, 'users')}")
    print(f"  hasattr(client, 'market_data'): {hasattr(client, 'market_data')}")
    
    # Пробуем получить список атрибутов
    print("\nАтрибуты Client (первые 10):")
    attrs = [attr for attr in dir(client) if not attr.startswith('_')]
    for attr in attrs[:10]:
        print(f"  - {attr}")
        
except Exception as e:
    print(f"✗ Ошибка: {e}")