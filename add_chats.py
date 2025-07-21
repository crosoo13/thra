import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel

# --- 1. ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()

TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
YOUR_PHONE_NUMBER = os.getenv('YOUR_PHONE_NUMBER')
SESSION_NAME = "hr_vision_agent_session"

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Имя файла, из которого читаем ссылки
INPUT_FILE = "tg.txt"

# --- 2. ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase клиент успешно инициализирован.")
except Exception as e:
    print(f"❌ Ошибка инициализации Supabase: {e}")

# --- 3. ФУНКЦИИ РАБОТЫ С СЕССИЕЙ ---
def get_session_from_supabase():
    """Получает строку сессии из Supabase."""
    try:
        response = supabase.table('sessions').select("session_file").eq('agent_name', SESSION_NAME).single().execute()
        if response.data:
            print("✅ Сессия успешно получена из Supabase.")
            return response.data.get('session_file')
    except Exception:
        print("INFO: Рабочая сессия не найдена, будет создана новая.")
    return None

# --- 4. ОСНОВНАЯ ЛОГИКА ---
async def main():
    """Главная функция для добавления чатов в базу данных."""
    print("Запуск скрипта добавления чатов...")

    session_string = get_session_from_supabase()
    if not session_string:
        print("❌ Критическая ошибка: Не найдена сессия для входа.")
        print("💡 Сначала запустите ваш основной скрипт, чтобы авторизоваться и сохранить сессию в базе.")
        return

    client = TelegramClient(StringSession(session_string), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    
    print("Подключение к Telegram...")
    await client.connect()
    if not await client.is_user_authorized():
        print("❌ Пользователь не авторизован. Запустите основной скрипт.")
        return
    
    print("✅ Успешная авторизация в Telegram!")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Файл {INPUT_FILE} не найден. Создайте его и добавьте ссылки.")
        return

    with open(INPUT_FILE, 'r') as f:
        for line in f:
            username = line.strip()
            if not username:
                continue

            try:
                print(f"--- Обработка: {username} ---")
                entity = await client.get_entity(username)
                
                chat_id = entity.id
                chat_type = None

                # --- НОВОЕ: Логика определения типа (канал или группа) ---
                if isinstance(entity, Channel):
                    # Преобразуем ID для каналов и супергрупп
                    chat_id = int(f"-100{entity.id}")
                    
                    # Свойство 'megagroup' равно True для супергрупп (чатов) и False для каналов
                    if entity.megagroup:
                        chat_type = 'group'
                    else:
                        chat_type = 'channel'
                else:
                    # Если это не Channel (например, обычный чат или бот), пропускаем
                    print(f"🟡 {username} не является каналом или группой. Пропускаем.")
                    continue
                # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

                print(f"✅ Найден ID: {chat_id}")
                print(f"✅ Тип определён: {chat_type}")

                # --- ИЗМЕНЕНО: Добавляем 'chat_type' в запись ---
                print(f"Запись в базу...")
                supabase.table("target_chats").upsert({
                    "username": username,
                    "chat_id": chat_id,
                    "chat_type": chat_type  # Добавляем тип
                }).execute()

                print(f"✅ Успешно добавлено: {username} | {chat_id} | Тип: {chat_type}")

            except ValueError:
                print(f"❌ Не удалось найти чат или канал по ссылке: {username}. Проверьте правильность или доступ.")
            except Exception as e:
                print(f"❌ Произошла непредвиденная ошибка с {username}: {e}")

    await client.disconnect()
    print("\nРабота скрипта завершена.")

if __name__ == "__main__":
    asyncio.run(main())