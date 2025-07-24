import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла, если он существует (для локальной разработки)
load_dotenv()

# --- Конфигурация Telegram ---
TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
# Имя сессии берется из окружения, со значением по умолчанию для удобства
SESSION_NAME = os.getenv("SESSION_NAME", "hr_vision_agent_session")

# --- Конфигурация Supabase ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# --- Конфигурация Gemini AI (ИЗМЕНЕННЫЙ БЛОК) ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# Модель для быстрой и дешевой классификации (Сортировщик)
GEMINI_FLASH_MODEL_NAME = 'gemini-2.5-flash'
# Модель для генерации качественных ответов (Генератор)
GEMINI_PRO_MODEL_NAME = 'gemini-2.5-pro'


# --- Конфигурация Внешних Сервисов ---
CLOUDFLARE_WORKER_URL = os.getenv('CLOUDFLARE_WORKER_URL')

def validate_config():
    """Проверяет, что все необходимые переменные окружения установлены."""
    required_vars = [
        'TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'SUPABASE_URL',
        'SUPABASE_KEY', 'GEMINI_API_KEY', 'CLOUDFLARE_WORKER_URL'
    ]

    # Проверяем, что каждая переменная из списка имеет значение
    missing_vars = [var for var in required_vars if not globals().get(var)]

    if missing_vars:
        # Если каких-то переменных не хватает, вызываем ошибку
        raise ValueError(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют переменные окружения: {', '.join(missing_vars)}")

    print("✅ Все переменные окружения успешно загружены.")