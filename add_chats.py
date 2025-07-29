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

INPUT_FILE = "tg.txt"

# --- 2. ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase клиент успешно инициализирован.")
except Exception as e:
    print(f"❌ Ошибка инициализации Supabase: {e}")
    exit() # Выходим, если Supabase недоступен

# --- 3. ФУНКЦИИ РАБОТЫ С СЕССИЕЙ ---
def get_session_from_supabase():
    """Получает строку сессии из Supabase."""
    try:
        response = supabase.table('sessions').select("session_file").eq('agent_name', SESSION_NAME).single().execute()
        if response.data:
            print("✅ Сессия успешно получена из Supabase.")
            return response.data.get('session_file')
    except Exception as e:
        print(f"INFO: Рабочая сессия не найдена, будет создана новая. Ошибка: {e}")
    return None

# --- 4. ОСНОВНАЯ ЛОГИКА С ОТЛАДКОЙ ---
async def main():
    """Главная функция для добавления чатов в базу данных."""
    print("Запуск скрипта добавления чатов...")

    session_string = get_session_from_supabase()
    if not session_string:
        print("❌ Критическая ошибка: Не найдена сессия для входа.")
        print("💡 Сначала запустите ваш основной скрипт, чтобы авторизоваться и сохранить сессию в базе.")
        return

    async with TelegramClient(StringSession(session_string), TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
        print("✅ Успешная авторизация в Telegram!")

        if not os.path.exists(INPUT_FILE):
            print(f"❌ Файл {INPUT_FILE} не найден. Создайте его и добавьте ссылки.")
            return

        with open(INPUT_FILE, 'r') as f:
            for line in f:
                username = line.strip()
                if not username:
                    continue

                print(f"\n--- Обработка: {username} ---")

                try:
                    entity = await client.get_entity(username)
                    
                    chat_id = entity.id
                    chat_type = None

                    if isinstance(entity, Channel):
                        chat_id = int(f"-100{entity.id}")
                        chat_type = 'group' if entity.megagroup else 'channel'
                    else:
                        print(f"🟡 {username} не является каналом или группой. Пропускаем.")
                        continue

                    print(f"✅ Найден ID: {chat_id}")
                    print(f"✅ Тип определён: {chat_type}")
                    
                    # --- БЛОК ДИАГНОСТИКИ ---
                    print("[ДИАГНОСТИКА] Поиск существующих записей...")
                    
                    # 1. Ищем по chat_id
                    existing_by_id = supabase.table("target_chats").select("*").eq("chat_id", chat_id).execute()
                    if existing_by_id.data:
                        print(f"🟡 НАЙДЕНА запись по chat_id={chat_id}: {existing_by_id.data[0]}")
                    else:
                        print(f"🟢 Запись с chat_id={chat_id} НЕ найдена.")

                    # 2. Ищем по username
                    existing_by_username = supabase.table("target_chats").select("*").eq("username", username).execute()
                    if existing_by_username.data:
                        print(f"🟡 НАЙДЕНА запись по username='{username}': {existing_by_username.data[0]}")
                    else:
                        print(f"🟢 Запись с username='{username}' НЕ найдена.")
                    # --- КОНЕЦ БЛОКА ДИАГНОСТИКИ ---

                    # --- Запись в базу ---
                    record_to_upsert = {
                        "username": username,
                        "chat_id": chat_id,
                        "chat_type": chat_type
                    }
                    print(f"[ДЕЙСТВИЕ] Выполняется upsert с данными: {record_to_upsert}")
                    
                    response = supabase.table("target_chats").upsert(record_to_upsert).execute()

                    if response.data:
                         print(f"✅ Успешно обработано: {username} | {chat_id} | Тип: {chat_type}")
                    else:
                         # Upsert может вернуть пустые данные, если ничего не изменилось.
                         # Проверяем наличие ошибки в объекте ответа, если он есть
                         if hasattr(response, 'error') and response.error:
                             print(f"❌ Ошибка Supabase при upsert: {response.error}")
                         else:
                             print("🔵 Данные не изменились или upsert вернул пустой ответ, но без ошибок.")


                except ValueError:
                    print(f"❌ Не удалось найти чат или канал по ссылке: {username}. Проверьте правильность или доступ (для приватных каналов нужно вступить).")
                except Exception as e:
                    print(f"❌ Произошла НЕПРЕДВИДЕННАЯ ошибка с {username}: {e}")
                    # Добавляем вывод типа ошибки для лучшей диагностики
                    print(f"   Тип ошибки: {type(e).__name__}")


    print("\nРабота скрипта завершена.")

if __name__ == "__main__":
    asyncio.run(main())