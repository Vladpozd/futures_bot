# test_ttech_structure.py
from t_tech.invest import Client

# Создаем клиент (без реального подключения)
try:
    client = Client(token="dummy", target="invest-public-api.tinkoff.ru:443")
    
    # Попробуем разные варианты
    print("Проверяем структуру T-Tech Client:")
    
    # Проверяем наличие атрибутов
    attrs_to_check = [
        'instruments',
        'instruments_service', 
        'instrument_service',
        'market_data',
        'market_data_service',
        'users',
        'user_service',
        'operations',
        'operations_service',
        'orders',
        'orders_service'
    ]
    
    for attr in attrs_to_check:
        if hasattr(client, attr):
            print(f"✓ Найден: client.{attr}")
            try:
                # Пробуем вызвать метод
                service = getattr(client, attr)
                methods = [m for m in dir(service) if not m.startswith('_')]
                print(f"  Методы: {methods[:5]}...")  # Первые 5 методов
            except:
                print(f"  Не удалось получить методы")
        else:
            print(f"✗ Отсутствует: client.{attr}")
            
except Exception as e:
    print(f"Ошибка: {e}")