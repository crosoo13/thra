# database_manager.py
from supabase import create_client, Client
from . import config

try:
    supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    print("✅ Успешное подключение к Supabase.")
except Exception as e:
    print(f"❌ Ошибка подключения к Supabase: {e}")
    exit()

def get_session_string():
    print("🔄 Попытка получить сессию из Supabase...")
    try:
        response = supabase.table('sessions').select("session_file").eq('agent_name', config.SESSION_NAME).single().execute()
        if response.data and response.data.get('session_file'):
            print("✅ Сессия успешно получена из Supabase.")
            return response.data.get('session_file')
        print("ℹ️ Сессия не найдена в Supabase.")
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении сессии из Supabase: {e}")
        return None

def save_session_string(session_string):
    print("🔄 Сохранение новой сессии в Supabase...")
    try:
        supabase.table('sessions').upsert({'agent_name': config.SESSION_NAME, 'session_file': session_string}).execute()
        print("✅ Сессия успешно сохранена в Supabase.")
    except Exception as e:
        print(f"❌ Ошибка при сохранении сессии в Supabase: {e}")

def get_target_chats():
    print("🔄 Получение списка целевых чатов из Supabase...")
    try:
        response = supabase.table('target_chats').select('chat_id, chat_type').execute()
        chats = response.data or []
        print(f"✅ Найдено {len(chats)} целевых чатов.")
        return chats
    except Exception as e:
        print(f"❌ Ошибка при получении чатов из Supabase: {e}")
        return []

def get_last_message_id(chat_id):
    try:
        response = supabase.table('channel_state').select('last_message_id').eq('chat_id', chat_id).single().execute()
        return int(response.data.get('last_message_id', 0)) if response.data else 0
    except Exception:
        return 0

def update_last_message_id(chat_id, message_id):
    print(f"🔄 Обновление ID последнего сообщения для чата {chat_id} на {message_id}...")
    try:
        supabase.table('channel_state').upsert({'chat_id': chat_id, 'last_message_id': message_id}).execute()
        print(f"✅ ID последнего сообщения для чата {chat_id} успешно обновлен.")
    except Exception as e:
        print(f"❌ Критическая ошибка при записи ID последнего сообщения для чата {chat_id}: {e}")

def get_prompt_template(prompt_name: str):
    print(f"🔄 Загрузка промпта '{prompt_name}' из Supabase...")
    try:
        response = supabase.table('prompts').select('content').eq('name', prompt_name).single().execute()
        if response.data:
            print(f"✅ Промпт '{prompt_name}' успешно загружен.")
            return response.data['content'].replace('\r\n', '\n')
        print(f"❌ Промпт '{prompt_name}' не найден в Supabase.")
        return None
    except Exception as e:
        print(f"❌ Ошибка при загрузке промпта '{prompt_name}': {e}")
        return None

# =================================================================
# 👇👇👇 ДОБАВЛЕННЫЙ КОД 👇👇👇
# =================================================================

def get_pending_actions():
    """
    Получает все записи из таблицы 'pending_actions', которые еще не выполнены.
    """
    try:
        # Выбираем все строки, где is_completed равно False
        response = supabase.table('pending_actions').select('*').eq('is_completed', False).execute()
        
        # response.data содержит список словарей, каждый из которых - это строка таблицы
        if response.data:
            return response.data
        return []
    except Exception as e:
        print(f"❌ Ошибка при получении отложенных действий из Supabase: {e}")
        return []

def mark_action_as_completed(action_id):
    """
    Обновляет запись в 'pending_actions', устанавливая is_completed = True.
    """
    try:
        # Находим строку по её 'id' и обновляем поле 'is_completed'
        supabase.table('pending_actions').update({'is_completed': True}).eq('id', action_id).execute()
        return True
    except Exception as e:
        print(f"❌ Ошибка при обновлении статуса действия {action_id} в Supabase: {e}")
        return False