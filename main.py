import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Импортируем все необходимые компоненты
from components import config
from components import database_manager as db
from components import telegram_processor
from components import sender_service

async def main():
    """Главная функция для запуска агента."""
    print("\n--- ✨ ЗАПУСК HR VISION AGENT ✨ ---\n")
    
    # 1. Загрузка промпта из базы данных
    prompt_name = "hr_assistant_prompt"
    prompt_template = db.get_prompt_template(prompt_name)
    if not prompt_template:
        return

    # 2. Получение сессии Telegram из базы данных
    session_string = db.get_session_string()
    
    # 3. Подключение к Telegram и основная логика
    print("🔄 Подключение к Telegram...")
    try:
        async with TelegramClient(StringSession(session_string), config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH) as client:
            print("✅ Клиент Telegram успешно инициализирован.")
            
            if not await client.is_user_authorized():
                print("❌ Пользователь не авторизован. Пожалуйста, запустите скрипт для создания сессии.")
                return

            # Получаем информацию о себе, чтобы игнорировать собственные сообщения
            me = await client.get_me()
            my_id = me.id
            print(f"✅ Скрипт запущен от имени: {me.first_name} (ID: {my_id})")

            # 4. Сначала отправляем все сообщения, ожидающие в очереди
            await sender_service.send_pending_messages(client)
            
            # 5. Затем получаем список целевых чатов для сканирования
            target_chats = db.get_target_chats()
            if not target_chats:
                print("ℹ️ Целевые чаты для обработки не найдены.")
                return

            print("\n--- 🚀 Начало обработки чатов ---")
            for chat_info in target_chats:
                # Передаем наш ID в обработчик, чтобы он фильтровал наши же сообщения
                await telegram_processor.process_chat(client, chat_info, prompt_template, prompt_name, my_id)
            
            print("\n--- ✅ Все чаты обработаны ---\n")

    except Exception as e:
        print(f"❌ Критическая ошибка в main: {e}")

# Точка входа для запуска скрипта
if __name__ == "__main__":
    try:
        # Проверяем наличие всех необходимых переменных окружения
        config.validate_config()
        # Запускаем асинхронную функцию main
        asyncio.run(main())
    except ValueError as e:
        print(e)
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при запуске: {e}")