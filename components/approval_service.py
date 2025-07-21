# approval_service.py
import requests
import json
from . import config

def send_action_for_approval(action_data):
    """Отправляет сгенерированное AI действие на утверждение."""
    msg_id = action_data.get('reply_to_message_id')
    print(f"   📤 Отправка действия на утверждение для сообщения {msg_id}...")
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(config.CLOUDFLARE_WORKER_URL, data=json.dumps(action_data), headers=headers)
        response.raise_for_status() # Вызовет исключение для кодов 4xx/5xx
        print(f"   ✅ Действие для сообщения {msg_id} успешно отправлено.")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Ошибка отправки на утверждение для сообщения {msg_id}. Ошибка: {e}")