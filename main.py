import asyncio
from datetime import date
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from components import config
from components import database_manager as db
from components import telegram_processor
from components import sender_service

async def initialize_first_run_of_day(client):
    """
    Выполняет первую инициализацию для нового дня.
    Просто обновляет last_message_id на ID последнего сообщения в чате.
    """
    print("\n--- 🌅 ПЕРВЫЙ ЗАПУСК ДНЯ: РЕЖИМ ИНИЦИАЛИЗАЦИИ ---\n")
    target_chats = db.get_target_chats()
    if not target_chats:
        print("ℹ️ Целевые чаты не найдены. Инициализация не требуется.")
        return

    for chat_info in target_chats:
        chat_id = chat_info['chat_id']
        processing_id = chat_id # ID для записи в channel_state
        print(f"▶️ Инициализация чата: {chat_id}")
        try:
            entity = await client.get_entity(chat_id)
            
            if hasattr(entity, 'linked_chat_id') and entity.linked_chat_id:
                processing_id = entity.linked_chat_id
                print(f"  ✅ Канал {chat_id} связан с чатом для комментариев {processing_id}.")
                entity_to_read = await client.get_entity(processing_id)
            else:
                entity_to_read = entity

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
    if not db.is_agent_active():
        return
    
    last_init_date = db.get_last_initialization_date()
    today = date.today()

    session_string = db.get_session_string()
    if not session_string:
        print("❌ Сессия не найдена. Пожалуйста, запустите скрипт для создания сессии.")
        return

    try:
        async with TelegramClient(StringSession(session_string), config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH) as client:
            if last_init_date is None or last_init_date < today:
                await initialize_first_run_of_day(client)
                return

            print("\n--- ✨ ЗАПУСК HR VISION AGENT (РАБОЧИЙ РЕЖИМ) ✨ ---\n")
            
            prompt_name = "hr_assistant_prompt"
            prompt_template = db.get_prompt_template(prompt_name)
            if not prompt_template:
                return

            if not await client.is_user_authorized():
                print("❌ Пользователь не авторизован. Пожалуйста, запустите скрипт для создания сессии.")
                return

            me = await client.get_me()
            my_id = me.id
            print(f"✅ Скрипт запущен от имени: {me.first_name} (ID: {my_id})")

            await sender_service.send_pending_messages(client)
            
            target_chats = db.get_target_chats()
            if not target_chats:
                print("ℹ️ Целевые чаты для обработки не найдены.")
                return

            # --- ИЗМЕНЕНИЕ: Загружаем ключевые слова ОДИН РАЗ ---
            keyword_triggers = db.get_keyword_triggers()

            print("\n--- 🚀 Начало обработки чатов ---")
            for chat_info in target_chats:
                # --- ИЗМЕНЕНИЕ: Передаем список как аргумент ---
                await telegram_processor.process_chat(client, chat_info, prompt_template, prompt_name, my_id, keyword_triggers)
            
            print("\n--- ✅ Все чаты обработаны ---\n")

    except Exception as e:
        print(f"❌ Критическая ошибка в main: {e}")


if __name__ == "__main__":
    try:
        config.validate_config()
        asyncio.run(main())
    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при запуске: {e}")