# main.py
# Этот скрипт предназначен для запуска по расписанию (cron).
# Его задача - читать чаты, находить цели и передавать их воркеру.

import asyncio
from datetime import date
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# --- Компоненты системы ---
from components import config
from components import database_manager as db
from components import telegram_processor
# Новый сервис для поиска лидов будет импортирован позже, прямо перед использованием

async def initialize_first_run_of_day(client):
    """
    Выполняет первую инициализацию для нового дня.
    (Этот код остался без изменений)
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
                print(f"  ✅ Канал {chat_id} связан с чатом для комментариев {processing_id}.")
                entity_to_read = await client.get_entity(processing_id)
            else:
                entity_to_read = entity

            # Получаем последнее сообщение и обновляем ID в базе
            async for last_message in client.iter_messages(entity_to_read, limit=1):
                db.update_last_message_id(processing_id, last_message.id)
                break
            else:
                print(f"  ⚠️ В чате {processing_id} нет сообщений, пропускаем.")

        except Exception as e:
            print(f"  ❌ Ошибка при инициализации чата {chat_id}: {e}")

    db.update_initialization_date()
    print("\n--- ✅ Инициализация на сегодня завершена ---")


async def main():
    """
    Основная логика работы агента-обнаружителя.
    """
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
            # Если сегодня еще не было инициализации, выполняем ее и завершаем скрипт
            if last_init_date is None or last_init_date < today:
                await initialize_first_run_of_day(client)
                return

            print("\n--- ✨ ЗАПУСК HR VISION AGENT (РАБОЧИЙ РЕЖИМ) ✨ ---\n")
            
            if not await client.is_user_authorized():
                print("❌ Пользователь не авторизован. Пожалуйста, запустите скрипт для создания сессии.")
                return

            me = await client.get_me()
            my_id = me.id
            print(f"✅ Скрипт запущен от имени: {me.first_name} (ID: {my_id})")

            # ВАЖНО: Логика отправки сообщений из очереди удалена,
            # так как теперь этим занимается веб-сервер на Railway.
            
            target_chats = db.get_target_chats()
            if not target_chats:
                print("ℹ️ Целевые чаты для обработки не найдены.")
                return

            # Загружаем ключевые слова ОДИН РАЗ в начале
            keyword_triggers = db.get_keyword_triggers()

            # --- ГИБРИДНЫЙ ПОДХОД К ОБРАБОТКЕ ---

            # 1. Готовим пустой список для сбора ВСЕХ сообщений для "Охотника за лидами"
            all_messages_for_lead_hunter = []
            
            print("\n--- 🚀 Начало последовательной обработки чатов (Агент влияния) ---")
            for chat_info in target_chats:
                # 2. Обрабатываем каждый чат старой логикой.
                # Функция теперь возвращает сообщения, которые она обработала.
                processed_messages = await telegram_processor.process_chat_for_engagement(
                    client, chat_info, my_id, keyword_triggers
                )
                
                # 3. Добавляем обработанные сообщения в общий список для "Охотника"
                if processed_messages:
                    all_messages_for_lead_hunter.extend(processed_messages)
            
            print("\n--- ✅ Все чаты обработаны 'Агентом влияния' ---")

            # 4. ПОСЛЕ цикла, запускаем новую логику ("Охотник за лидами") на всех собранных сообщениях
            if all_messages_for_lead_hunter:
                print("\n--- 🕵️‍♂️ Запуск 'Охотника за лидами' по всем собранным сообщениям ---")
                
                # Импортируем новый сервис прямо здесь, чтобы избежать циклических зависимостей
                # и сохранить код чистым.
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
        asyncio.run(main())
    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при запуске: {e}")