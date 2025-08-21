# components/database_manager.py - НОВЫЙ КОД ДЛЯ NEON

import psycopg2
import psycopg2.extras  # Необходим для получения результатов в виде словарей
from datetime import date, datetime
from . import config

def _get_db_connection():
    """Создает и возвращает новое соединение с базой данных Neon."""
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к базе данных Neon: {e}")
        exit()

# --- Управление сессией ---

def get_session_string():
    print("🔄 Попытка получить сессию из Neon...")
    sql = "SELECT session_file FROM public.sessions WHERE agent_name = %s LIMIT 1"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (config.SESSION_NAME,))
                result = cur.fetchone()
                if result:
                    print("✅ Сессия успешно получена из Neon.")
                    return result[0]
                print("ℹ️ Сессия не найдена в Neon.")
                return None
    except Exception as e:
        print(f"❌ Ошибка при получении сессии из Neon: {e}")
        return None

def save_session_string(session_string):
    print("🔄 Сохранение новой сессии в Neon...")
    sql = """
        INSERT INTO public.sessions (agent_name, session_file) 
        VALUES (%s, %s)
        ON CONFLICT (agent_name) 
        DO UPDATE SET session_file = EXCLUDED.session_file;
    """
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (config.SESSION_NAME, session_string))
            conn.commit()
            print("✅ Сессия успешно сохранена в Neon.")
    except Exception as e:
        print(f"❌ Ошибка при сохранении сессии в Neon: {e}")

# --- Работа с чатами и сообщениями ---

def get_target_chats():
    print("🔄 Получение списка целевых чатов из Neon...")
    sql = "SELECT chat_id, chat_type FROM public.target_chats"
    try:
        with _get_db_connection() as conn:
            # RealDictCursor гарантирует, что результат будет списком словарей,
            # как это делала библиотека Supabase, чтобы не ломать остальной код.
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                chats = cur.fetchall()
                print(f"✅ Найдено {len(chats)} целевых чатов.")
                return chats
    except Exception as e:
        print(f"❌ Ошибка при получении чатов из Neon: {e}")
        return []

def get_last_message_id(chat_id):
    sql = "SELECT last_message_id FROM public.channel_state WHERE chat_id = %s"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (chat_id,))
                result = cur.fetchone()
                return int(result[0]) if result else 0
    except Exception:
        return 0

def update_last_message_id(chat_id, message_id):
    print(f"🔄 Обновление ID последнего сообщения для чата {chat_id} на {message_id}...")
    sql = """
        INSERT INTO public.channel_state (chat_id, last_message_id) 
        VALUES (%s, %s)
        ON CONFLICT (chat_id) 
        DO UPDATE SET last_message_id = EXCLUDED.last_message_id;
    """
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (chat_id, message_id))
            conn.commit()
            print(f"✅ ID последнего сообщения для чата {chat_id} успешно обновлен.")
    except Exception as e:
        print(f"❌ Критическая ошибка при записи ID последнего сообщения для чата {chat_id}: {e}")

def get_last_post_time(chat_id: int) -> datetime | None:
    sql = "SELECT last_agent_post_timestamp FROM public.channel_state WHERE chat_id = %s"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (chat_id,))
                result = cur.fetchone()
                # psycopg2 автоматически преобразует таймстемп в объект datetime
                return result[0] if result and result[0] else None
    except Exception:
        return None

def update_last_post_time(chat_id: int):
    print(f"🔄 Установка метки времени последнего ответа для чата {chat_id}...")
    # Используем SQL-функцию NOW() для установки текущего времени на сервере
    sql = """
        INSERT INTO public.channel_state (chat_id, last_agent_post_timestamp) 
        VALUES (%s, NOW())
        ON CONFLICT (chat_id) 
        DO UPDATE SET last_agent_post_timestamp = NOW();
    """
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (chat_id,))
            conn.commit()
            print(f"✅ Метка времени для чата {chat_id} успешно установлена.")
    except Exception as e:
        print(f"❌ Ошибка при обновлении метки времени для чата {chat_id}: {e}")

# --- Работа с промптами и логами ---

def get_prompt_template(prompt_name: str):
    print(f"🔄 Загрузка промпта '{prompt_name}' из Neon...")
    sql = "SELECT content FROM public.prompts WHERE name = %s"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (prompt_name,))
                result = cur.fetchone()
                if result:
                    print(f"✅ Промпт '{prompt_name}' успешно загружен.")
                    return result[0].replace('\r\n', '\n')
                print(f"❌ Промпт '{prompt_name}' не найден в Neon.")
                return None
    except Exception as e:
        print(f"❌ Ошибка при загрузке промпта '{prompt_name}': {e}")
        return None

def get_examples_by_status(prompt_name: str, status: str, limit: int = 5):
    print(f"🔄 Запрос {limit} примеров со статусом '{status}' для промпта '{prompt_name}'...")
    sql = """
        SELECT original_message_text, ai_generated_text 
        FROM public.ai_suggestions_log
        WHERE status = %s AND prompt_version = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    try:
        with _get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (status, prompt_name, limit))
                examples = cur.fetchall()
                if examples:
                    print(f"✅ Найдено {len(examples)} примеров.")
                    return list(reversed(examples)) # Сохраняем логику разворота списка
                return []
    except Exception as e:
        print(f"❌ Ошибка при получении примеров для '{prompt_name}' со статусом '{status}': {e}")
        return []

# --- Работа с отложенными действиями ---

def get_pending_actions():
    sql = "SELECT * FROM public.pending_actions WHERE is_completed = FALSE"
    try:
        with _get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                return cur.fetchall()
    except Exception as e:
        print(f"❌ Ошибка при получении отложенных действий из Neon: {e}")
        return []

def mark_action_as_completed(action_id):
    sql = "UPDATE public.pending_actions SET is_completed = TRUE WHERE id = %s"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (action_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ Ошибка при обновлении статуса действия {action_id} в Neon: {e}")
        return False

# --- Работа со статусом агента ---

def is_agent_active():
    print("🔄 Проверка статуса агента в Neon...")
    sql = "SELECT is_active FROM public.agent_status WHERE id = '1'"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchone()
                if result:
                    is_active = result[0]
                    if is_active:
                        print("✅ Агент активен. Продолжаем работу.")
                        return True
                    else:
                        print("⏹️ Агент неактивен. Завершение работы.")
                        return False
                print("⚠️ Статус агента не найден. Завершение работы.")
                return False
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса агента: {e}")
        return False

def get_last_initialization_date():
    print("🔄 Проверка даты последней инициализации...")
    sql = "SELECT last_initialization_date FROM public.agent_status WHERE id = '1'"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchone()
                if result and result[0]:
                    # psycopg2 сам преобразует в объект date, fromisoformat не нужен
                    return result[0]
                print("ℹ️ Дата инициализации не найдена.")
                return None
    except Exception as e:
        print(f"❌ Ошибка при получении даты инициализации: {e}")
        return None

def update_initialization_date():
    today = date.today()
    print(f"🔄 Обновление даты инициализации на {today.isoformat()}...")
    sql = "UPDATE public.agent_status SET last_initialization_date = %s WHERE id = '1'"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (today,))
            conn.commit()
            print("✅ Дата инициализации успешно обновлена.")
    except Exception as e:
        print(f"❌ Ошибка при обновлении даты инициализации: {e}")

# --- Ключевые слова и контакты ---

def get_keyword_triggers():
    print("🔄 Загрузка ключевых слов-триггеров из Neon...")
    sql = "SELECT keyword FROM public.keyword_triggers"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                # Преобразуем список кортежей [('слово1',), ...] в простой список ['слово1', ...]
                keywords = [item[0] for item in cur.fetchall()]
                print(f"✅ Загружено {len(keywords)} ключевых слов.")
                return keywords
    except Exception as e:
        print(f"❌ Ошибка при загрузке ключевых слов: {e}")
        return []

def was_user_contacted_today(user_id: int) -> bool:
    sql = "SELECT 1 FROM public.daily_user_contacts WHERE user_id = %s AND last_contact_date = %s"
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, date.today()))
                # Если fetchone() что-то вернул, значит запись есть
                return cur.fetchone() is not None
    except Exception:
        return False

def record_user_contact(user_id: int):
    print(f"🔄 Запись о контакте с пользователем {user_id} на сегодня...")
    sql = """
        INSERT INTO public.daily_user_contacts (user_id, last_contact_date) 
        VALUES (%s, %s)
        ON CONFLICT (user_id) 
        DO UPDATE SET last_contact_date = EXCLUDED.last_contact_date;
    """
    try:
        with _get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, date.today()))
            conn.commit()
            print(f"✅ Успешно записан контакт с пользователем {user_id}.")
    except Exception as e:
        print(f"❌ Ошибка при записи контакта с пользователем {user_id}: {e}")