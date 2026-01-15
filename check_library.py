
"""
Проверка структуры библиотеки t-tech-investments
"""
import sys
import pkgutil

print("Проверяем установленные модули...")

# Ищем модули связанные с t-tech
modules = []
for finder, name, ispkg in pkgutil.iter_modules():
    if 't' in name.lower() or 'tech' in name.lower() or 'invest' in name.lower():
        modules.append(name)

print("\nНайденные модули:")
for mod in sorted(modules):
    print(f"  - {mod}")

# Пробуем импортировать t-tech
print("\nПробуем импортировать...")
try:
    import t_tech
    print("✅ Успешно импортирован t_tech")
    print(f"   Путь: {t_tech.__file__}")
    
    # Пробуем найти подмодули
    print("\nПодмодули t_tech:")
    for item in dir(t_tech):
        if not item.startswith('_'):
            print(f"  - {item}")
except ImportError as e:
    print(f"❌ Ошибка импорта t_tech: {e}")

# Пробуем ttech (без подчеркивания)
try:
    import ttech
    print("✅ Успешно импортирован ttech")
    print(f"   Путь: {ttech.__file__}")
except ImportError as e:
    print(f"❌ Ошибка импорта ttech: {e}")

# Пробуем ttech.invest
try:
    import ttech.invest
    print("✅ Успешно импортирован ttech.invest")
    
    # Смотрим что внутри
    print("\nСодержимое ttech.invest:")
    for item in dir(ttech.invest):
        if not item.startswith('_'):
            print(f"  - {item}")
except ImportError as e:
    print(f"❌ Ошибка импорта ttech.invest: {e}")

# Проверяем Client
print("\nПроверяем наличие Client:")
try:
    from ttech.invest import Client
    print("✅ Client найден в ttech.invest")
except ImportError:
    try:
        from t_tech.invest import Client
        print("✅ Client найден в t_tech.invest")
    except ImportError as e:
        print(f"❌ Client не найден: {e}")

# Проверяем target в Client
print("\nПроверяем параметры Client.__init__:")
try:
    import inspect
    if 'Client' in locals():
        sig = inspect.signature(Client.__init__)
        print("Параметры Client.__init__:")
        for param_name, param in sig.parameters.items():
            if param_name != 'self':
                print(f"  - {param_name}: {param}")
except Exception as e:
    print(f"Ошибка проверки сигнатуры: {e}")
