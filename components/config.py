# components/config.py - ПРАВИЛЬНЫЙ ВАРИАНТ ДЛЯ NEON

import os
from dotenv import load_dotenv

load_dotenv()

# --- Конфигурация Telegram ---
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_NAME = os.getenv("SESSION_NAME", "hr_vision_agent_session")

# --- Конфигурация базы данных Neon ---
# 👇 УДАЛИЛИ SUPABASE_URL и SUPABASE_KEY, ЗАМЕНИЛИ НА ЭТО:
DATABASE_URL = os.getenv('NEON_DB_CONNECTION_STRING')

# --- Конфигурация Gemini AI ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_FLASH_MODEL_NAME = 'gemini-2.5-flash'
GEMINI_PRO_MODEL_NAME = 'gemini-2.5-pro'

# --- Конфигурация Внешних Сервисов ---
CLOUDFLARE_WORKER_URL = os.getenv('CLOUDFLARE_WORKER_URL')

def validate_config():
    """Проверяет, что все необходимые переменные окружения установлены."""
    
    # 👇 ВОТ ГЛАВНОЕ ИЗМЕНЕНИЕ:
    # Мы убрали 'SUPABASE_URL' и 'SUPABASE_KEY' и добавили 'DATABASE_URL'
    required_vars = [
        'TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'DATABASE_URL',
        'GEMINI_API_KEY', 'CLOUDFLARE_WORKER_URL'
    ]

    missing_vars = [var for var in required_vars if not globals().get(var)]

    if missing_vars:
        raise ValueError(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют переменные окружения: {', '.join(missing_vars)}")

    print("✅ Все переменные окружения успешно загружены.")