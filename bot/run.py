#!/usr/bin/env python3
"""
Скрипт запуска торгового бота.
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main

if __name__ == "__main__":
    print("🚀 Запуск фьючерсного бота...")
    main()