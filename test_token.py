# check_api_v2.py
"""
🔍 ТЕСТ ПОДКЛЮЧЕНИЯ С ПЕСОЧНИЦЕЙ И НОВЫМИ МЕТОДАМИ
"""

import os
from dotenv import load_dotenv
from t_tech.invest import Client
from t_tech.invest.schemas import InstrumentIdType

def main():
    print("=" * 60)
    print("🔍 ПРОВЕРКА ПОДКЛЮЧЕНИЯ (с песочницей)")
    print("=" * 60)
    
    # 1. Загружаем токен
    load_dotenv()
    token = os.getenv('T_TECH_TOKEN', 't.l23hpVnXzBiu-J0LlsiuvJmS7c7YkKwi7AP6tsKHimyg0vsgcUl-mZFM7KhVZ7fwmO0tdIsA0txlZF83spOhug')
    
    print(f"Токен: {token[:20]}...")
    print(f"Длина: {len(token)} символов")
    
    # 2. Пробуем ПЕСОЧНИЦУ
    print("\n1. Пробуем подключиться к ПЕСОЧНИЦЕ...")
    try:
        client = Client(token=token, sandbox=True)
        print("✅ Клиент песочницы создан")
        
        # Пробуем получить счета в песочнице
        try:
            response = client.users.get_accounts()
            print(f"✅ Счета песочницы получены: {len(response.accounts)} шт.")
            for acc in response.accounts:
                print(f"   - {acc.name} ({acc.id})")
        except Exception as e:
            print(f"❌ Ошибка со счетами песочницы: {e}")
            
    except Exception as e:
        print(f"❌ Ошибка создания клиента песочницы: {e}")
    
    # 3. Пробуем БОЕВОЙ режим (без sandbox)
    print("\n2. Пробуем БОЕВОЙ режим (без sandbox)...")
    try:
        client = Client(token=token)  # Без sandbox = боевой режим
        print("✅ Боевой клиент создан")
        
        # Пробуем получить счета
        try:
            response = client.users.get_accounts()
            print(f"✅ Боевые счета получены: {len(response.accounts)} шт.")
        except Exception as e:
            print(f"❌ Ошибка с боевыми счетами: {e}")
            
    except Exception as e:
        print(f"❌ Ошибка создания боевого клиента: {e}")
    
    # 4. Проверяем доступные методы для инструментов
    print("\n3. Исследуем доступные методы...")
    try:
        client = Client(token=token, sandbox=True)
        
        # Смотрим, что есть в instruments
        if hasattr(client, 'instruments'):
            print("✅ instruments доступен")
            
            # Пробуем разные методы
            methods = [m for m in dir(client.instruments) if not m.startswith('_')]
            print(f"Доступные методы instruments: {methods}")
            
            # Пробуем получить фьючерсы (возможные названия методов)
            for method_name in ['futures', 'get_futures', 'find_instrument']:
                if hasattr(client.instruments, method_name):
                    print(f"\nПробую метод: {method_name}...")
                    try:
                        method = getattr(client.instruments, method_name)
                        result = method()
                        print(f"✅ {method_name} работает: {result}")
                        break
                    except Exception as e:
                        print(f"❌ {method_name} ошибка: {e}")
        else:
            print("❌ instruments не доступен")
            
    except Exception as e:
        print(f"❌ Ошибка исследования методов: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("1. Создайте НОВЫЙ токен в личном кабинете T-Tech")
    print("2. Убедитесь, что права: 'Торговля' (не 'Только просмотр')")
    print("3. Попробуйте оба режима: sandbox=True и sandbox=False")
    print("4. Обновите библиотеку: pip install --upgrade t-tech-investments")

if __name__ == "__main__":
    main()