from supabase import create_client, Client
from datetime import date
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

def get_examples_by_status(prompt_name: str, status: str, limit: int = 10):
	print(f"🔄 Запрос {limit} примеров со статусом '{status}' для промта '{prompt_name}'...")
	try:
		response = supabase.table('ai_suggestions_log').select(
			"original_message_text, ai_generated_text"
		).eq(
			'status', status
		).eq(
			'prompt_version', prompt_name
		).order(
			'created_at', desc=True
		).limit(
			limit
		).execute()

		if response.data:
			print(f"✅ Найдено {len(response.data)} примеров.")
			return list(reversed(response.data))
		return []
	except Exception as e:
		print(f"❌ Ошибка при получении примеров для '{prompt_name}' со статусом '{status}': {e}")
		return []

def get_pending_actions():
	try:
		response = supabase.table('pending_actions').select('*').eq('is_completed', False).execute()
		if response.data:
			return response.data
		return []
	except Exception as e:
		print(f"❌ Ошибка при получении отложенных действий из Supabase: {e}")
		return []

def mark_action_as_completed(action_id):
	try:
		supabase.table('pending_actions').update({'is_completed': True}).eq('id', action_id).execute()
		return True
	except Exception as e:
		print(f"❌ Ошибка при обновлении статуса действия {action_id} в Supabase: {e}")
		return False

def is_agent_active():
	print("🔄 Проверка статуса агента в Supabase...")
	try:
		response = supabase.table('agent_status').select("is_active").eq('id', 1).single().execute()
		if response.data and 'is_active' in response.data:
			is_active = response.data['is_active']
			if is_active:
				print("✅ Агент активен. Продолжаем работу.")
				return True
			else:
				print("⏹️ Агент неактивен. Завершение работы.")
				return False
		print("⚠️ Статус агента не найден в Supabase. Завершение работы.")
		return False
	except Exception as e:
		print(f"❌ Ошибка при проверке статуса агента: {e}")
		return False

def get_last_initialization_date():
    """Получает дату последней инициализации агента."""
    print("🔄 Проверка даты последней инициализации...")
    try:
        response = supabase.table('agent_status').select("last_initialization_date").eq('id', 1).single().execute()
        if response.data and response.data.get('last_initialization_date'):
            # Преобразуем строку 'YYYY-MM-DD' в объект date
            return date.fromisoformat(response.data['last_initialization_date'])
        print("ℹ️ Дата инициализации не найдена.")
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении даты инициализации: {e}")
        return None

def update_initialization_date():
    """Обновляет дату инициализации на сегодня."""
    today_str = date.today().isoformat()
    print(f"🔄 Обновление даты инициализации на {today_str}...")
    try:
        supabase.table('agent_status').update({'last_initialization_date': today_str}).eq('id', 1).execute()
        print("✅ Дата инициализации успешно обновлена.")
    except Exception as e:
        print(f"❌ Ошибка при обновлении даты инициализации: {e}")