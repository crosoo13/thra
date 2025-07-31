# components/session_manager.py

import os
import logging
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

# Импортируем общие компоненты
from . import config
from . import database_manager as db

# Загружаем переменные окружения для доступа к номеру телефона
load_dotenv()
YOUR_PHONE_NUMBER = os.getenv('YOUR_PHONE_NUMBER')

async def create_new_session():
    """
    Интерактивно создает новую строковую сессию Telegram и сохраняет ее в базу данных.
    
    Эта функция вызывается, когда основной скрипт не находит валидной сессии.
    Она использует уникальные параметры клиента (device_model, app_version), 
    чтобы повысить стабильность сессии и избежать разлогинивания со стороны Telegram.

    Возвращает:
        str: Строку сессии в случае успеха.
        None: В случае ошибки или отмены пользователем.
    """
    print("\n--- 🔑 Требуется новая сессия Telegram ---")

    if not YOUR_PHONE_NUMBER:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Переменная YOUR_PHONE_NUMBER не найдена в .env файле!")
        return None

    # Инициализируем клиент с уникальными параметрами для нашего "приложения",
    # чтобы Telegram считал его легитимным и не разлогинивал.
    client = TelegramClient(
        StringSession(), 
        config.TELEGRAM_API_ID, 
        config.TELEGRAM_API_HASH,
        device_model="HR Vision Agent",
        system_version="Windows 11", # Можете указать любую ОС, например "Ubuntu 22.04"
        app_version="1.0.0" # Версия вашего бота
    )

    session_string = None
    try:
        await client.connect()

        print(f" - Для авторизации будет использован номер: {YOUR_PHONE_NUMBER}")
        await client.send_code_request(YOUR_PHONE_NUMBER)
        print(" - Код подтверждения отправлен в Telegram.")

        try:
            await client.sign_in(YOUR_PHONE_NUMBER, input(' - Пожалуйста, введите код подтверждения: '))
        except SessionPasswordNeededError:
            print(" - Требуется пароль двухфакторной аутентификации (2FA).")
            await client.sign_in(password=input(' - Пожалуйста, введите ваш пароль 2FA: '))

        me = await client.get_me()
        if not me:
            raise Exception("Не удалось получить информацию о пользователе после входа.")

        print(f"\n✅ Успешный вход от имени: {me.first_name} ({me.username})")

        # Получаем строку сессии из объекта сессии в памяти
        session_string = client.session.save()

        if not session_string or len(session_string) < 50:
            print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM НЕ ВЕРНУЛ ВАЛИДНУЮ СЕССИЮ!")
            return None

        print("--- ✅ Сессия успешно сгенерирована. ---")
        
        # Сохраняем валидную строку в базу данных для дальнейшего использования
        db.save_session_string(session_string)
        print("--- ✅ Сессия успешно сохранена в базу данных. ---")

    except Exception as e:
        print(f"\n❌ Произошла ошибка в процессе создания сессии: {e}")
        return None
    finally:
        # Важно отключать временный клиент, который использовался только для входа
        if client.is_connected():
            await client.disconnect()
            print("\n--- Временный клиент для создания сессии отключен. ---")
    
    return session_string