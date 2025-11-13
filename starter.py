#!/usr/bin/env python3
"""
Casino Bot Starter
Запуск телеграм бота казино
"""

import sys
import os
import asyncio

# Добавляем src в путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, 'src')
sys.path.insert(0, current_dir)
sys.path.insert(0, src_path)


def check_requirements():
    """Проверка установленных зависимостей"""
    required = {
        'aiogram': 'aiogram>=3.4.1',
        'aiohttp': 'aiohttp>=3.9.1',
        'PIL': 'Pillow>=10.2.0',
        'aiofiles': 'aiofiles>=23.2.1'
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Отсутствуют необходимые модули!")
        print("\nУстановите их командой:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True


def check_config():
    """Проверка конфигурации"""
    import configparser
    
    config_path = os.path.join(current_dir, 'config.cfg')
    
    if not os.path.exists(config_path):
        print("❌ Файл config.cfg не найден!")
        print("\nСоздайте его и добавьте BOT_TOKEN от @BotFather")
        return False
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    bot_token = config.get('TELEGRAM', 'BOT_TOKEN', fallback='')
    if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
        print("❌ BOT_TOKEN не настроен в config.cfg!")
        print("\n1. Откройте @BotFather в Telegram")
        print("2. Создайте бота командой /newbot")
        print("3. Скопируйте токен в config.cfg")
        return False
    
    return True


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════╗
    ║      🎰 CASINO BOT STARTING 🎰       ║
    ╚══════════════════════════════════════╝
    """)
    
    # Проверяем зависимости
    if not check_requirements():
        input("\nНажмите Enter для выхода...")
        sys.exit(1)
    
    # Проверяем конфигурацию
    if not check_config():
        input("\nНажмите Enter для выхода...")
        sys.exit(1)
    
    print("✅ Все проверки пройдены!\n")
    print("🚀 Запуск бота...\n")
    
    try:
        # Импортируем main только после проверок
        from main import main
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для выхода...")
        sys.exit(1)

