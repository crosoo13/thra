# main.py

import asyncio
from datetime import date
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# --- Компоненты системы ---
from components import config
from components import database_manager as db
from components import telegram_processor
# 💡 Импортируем наш новый менеджер сессий
from components import session_manager 

# --- Эта функция осталась без изменений ---
async def initialize_first_run_of_day(client):
    """
    Выполняет первую инициализацию для нового дня.
    """
    print("\n--- 🌅 ПЕРВЫЙ ЗАПУСК ДНЯ: РЕЖИМ ИНИЦИАЛИЗАЦИИ ---\n")
    target_chats = db.get_target_chats()
    if not target_chats:
        print("ℹ️ Целевые чаты не найдены. Инициализация не требуется.")
        return

    for chat_info in target_chats:
        chat_id = chat_info['chat_id']
        processing_id = chat_id
        print(f"▶️ Инициализация чата: {chat_id}")
        try:
            entity = await client.get_entity(chat_id)
            
            # Если это канал со связанным чатом, работаем с чатом комментариев
            if hasattr(entity, 'linked_chat_id') and entity.linked_chat_id:
                processing_id = entity.linked_chat_id
                print(f"   ✅ Канал {chat_id} связан с чатом для комментариев {processing_id}.")
                entity_to_read = await client.get_entity(processing_id)
            else:
                entity_to_read = entity

            # Получаем последнее сообщение и обновляем ID в базе
            async for last_message in client.iter_messages(entity_to_read, limit=1):
                db.update_last_message_id(processing_id, last_message.id)
                break
            else:
                print(f"   ⚠️ В чате {processing_id} нет сообщений, пропускаем.")

        except Exception as e:
            print(f"   ❌ Ошибка при инициализации чата {chat_id}: {e}")

    db.update_initialization_date()
    print("\n--- ✅ Инициализация на сегодня завершена ---")


async def main():
    """
    Основная логика работы агента с интегрированным созданием и проверкой сессии.
    """
    if not db.is_agent_active():
        print("ℹ️ Агент неактивен в базе данных. Запуск отменен.")
        return

    # --- 🚀 НАДЁЖНАЯ СИСТЕМА УПРАВЛЕНИЯ СЕССИЕЙ ---
    session_string = db.get_session_string()
    client = None

    # Шаг 1: Попытка использовать существующую сессию
    if session_string:
        print("ℹ️ Найдена существующая сессия. Проверяем...")
        # Инициализируем клиент с уникальными параметрами
        client = TelegramClient(
            StringSession(session_string), 
            config.TELEGRAM_API_ID, 
            config.TELEGRAM_API_HASH,
            device_model="HR Vision Agent",
            system_version="Windows 11",
            app_version="1.0.0"
        )
        try:
            await client.connect()
            if not await client.is_user_authorized():
                print("⚠️ Существующая сессия недействительна или истекла.")
                session_string = None
                await client.disconnect()
                client = None
            else:
                print("✅ Сессия действительна.")
        except Exception as e:
            print(f"⚠️ Ошибка при проверке сессии: {e}. Будет создана новая.")
            session_string = None
            if client and client.is_connected():
                await client.disconnect()
            client = None

    # Шаг 2: Создание новой сессии, если она отсутствует или невалидна
    if not session_string:
        session_string = await session_manager.create_new_session()
        if not session_string:
            print("❌ Не удалось создать новую сессию. Работа агента прервана.")
            return
        # После создания новой сессии, нужно заново инициализировать клиент для основной работы
        client = TelegramClient(
            StringSession(session_string), 
            config.TELEGRAM_API_ID, 
            config.TELEGRAM_API_HASH,
            device_model="HR Vision Agent",
            system_version="Windows 11",
            app_version="1.0.0"
        )
    # --- КОНЕЦ СИСТЕМЫ УПРАВЛЕНИЯ СЕССИЕЙ ---

    try:
        # `async with` сам управляет подключением и отключением клиента
        async with client:
            last_init_date = db.get_last_initialization_date()
            today = date.today()

            # --- Первоначальная логика без изменений ---
            if last_init_date is None or last_init_date < today:
                await initialize_first_run_of_day(client)
                return

            print("\n--- ✨ ЗАПУСК HR VISION AGENT (РАБОЧИЙ РЕЖИМ) ✨ ---\n")
            
            me = await client.get_me()
            my_id = me.id
            print(f"✅ Скрипт запущен от имени: {me.first_name} (ID: {my_id})")

            target_chats = db.get_target_chats()
            if not target_chats:
                print("ℹ️ Целевые чаты для обработки не найдены.")
                return

            keyword_triggers = db.get_keyword_triggers()
            all_messages_for_lead_hunter = []
            
            print("\n--- 🚀 Начало последовательной обработки чатов (Агент влияния) ---")
            for chat_info in target_chats:
                processed_messages = await telegram_processor.process_chat_for_engagement(
                    client, chat_info, my_id, keyword_triggers
                )
                if processed_messages:
                    all_messages_for_lead_hunter.extend(processed_messages)
            
            print("\n--- ✅ Все чаты обработаны 'Агентом влияния' ---")

            if all_messages_for_lead_hunter:
                print("\n--- 🕵️‍♂️ Запуск 'Охотника за лидами' по всем собранным сообщениям ---")
                from components import lead_hunter_service 
                await lead_hunter_service.find_and_process_leads(client, all_messages_for_lead_hunter)
                print("\n--- ✅ Поиск лидов завершен ---")
            else:
                print("\n--- ℹ️ Новых сообщений для поиска лидов не найдено ---")

            print("\n--- 🏁 Работа агента на этот запуск завершена ---\n")

    except Exception as e:
        print(f"❌ Критическая ошибка в main: {e}")


if __name__ == "__main__":
    try:
        # Проверяем наличие всех необходимых переменных окружения перед запуском
        config.validate_config()
        # Убедимся, что база данных готова к работе
        if hasattr(db, 'init_db'):
            db.init_db()
        asyncio.run(main())
    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при запуске: {e}")