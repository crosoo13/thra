# create_session.py
# ВЕРСИЯ, ИСПРАВЛЕННАЯ ДЛЯ ГЕНЕРАЦИИ СТРОКОВОЙ СЕССИИ

import asyncio
import os
import logging
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
# ❗ Важное изменение: импортируем StringSession для работы с сессиями в памяти
from telethon.sessions import StringSession

# --- Компоненты системы ---
# Убедитесь, что эти файлы существуют и находятся в правильном месте
from components import config
from components import database_manager as db

# Включаем подробное логирование ДО любого кода Telethon
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(logging.WARNING) # Можно поставить WARNING, чтобы не видеть слишком много деталей

print("--- ⚠️  РЕЖИМ СОЗДАНИЯ СЕССИИ АКТИВИРОВАН ⚠️ ---")

# Загружаем переменные и номер телефона
load_dotenv()
YOUR_PHONE_NUMBER = os.getenv('YOUR_PHONE_NUMBER')

async def main():
    """
    Основная функция для создания и сохранения сессии в виде строки.
    """
    print("\n--- Создание новой сессии Telegram (Автономный режим) ---")

    if not YOUR_PHONE_NUMBER:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Переменная YOUR_PHONE_NUMBER не найдена в .env файле!")
        return

    # ❗ Ключевое изменение:
    # Вместо имени файла (config.SESSION_NAME) передаем объект StringSession().
    # Это говорит Telethon, что мы хотим работать со строковой сессией, а не с файлом.
    client = TelegramClient(StringSession(), config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f" - Авторизация не требуется. Используем номер: {YOUR_PHONE_NUMBER}")
            await client.send_code_request(YOUR_PHONE_NUMBER)
            print(" - Код подтверждения отправлен.")

            try:
                await client.sign_in(YOUR_PHONE_NUMBER, input(' - Пожалуйста, введите код подтверждения: '))
            except SessionPasswordNeededError:
                print(" - Требуется пароль двухфакторной аутентификации.")
                await client.sign_in(password=input(' - Пожалуйста, введите ваш пароль 2FA: '))

        me = await client.get_me()
        if not me:
            raise Exception("Не удалось получить информацию о пользователе после входа.")

        print(f"\n✅ Успешный вход от имени: {me.first_name} ({me.username})")

        # Теперь .save() корректно вернет строку сессии, так как клиент был инициализирован с StringSession
        session_string = client.session.save()

        print("\n--- 🕵️  Проверка сгенерированной сессии 🕵️ ---")
        print(f"  - Длина строки сессии: {len(session_string) if session_string else 0}")

        if not session_string or len(session_string) < 50:
            print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM НЕ ВЕРНУЛ ВАЛИДНУЮ СЕССИЮ!")
            return

        print("--- ✅ Диагностика пройдена. Сессия выглядит корректной. ---")
        
        # Вызываем функцию сохранения в БД. Теперь у нее есть валидная строка для записи.
        db.save_session_string(session_string)
        print("--- ✅ Сессия успешно сохранена в базу данных. ---")

    except Exception as e:
        print(f"\n❌ Произошла ошибка в процессе: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()
            print("\n--- Клиент Telegram отключен. ---")


if __name__ == "__main__":
    try:
        print("✅ Запуск автономного создателя сессий...")
        # Убедимся, что база данных готова к работе перед запуском
        if hasattr(db, 'init_db'):
             db.init_db()
        asyncio.run(main())
    except Exception as e:
        print(f"  - Глобальная ошибка: {e}")