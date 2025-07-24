import json
import google.generativeai as genai
from . import config
from . import database_manager as db # Добавляем импорт для доступа к промптам

try:
    genai.configure(api_key=config.GEMINI_API_KEY)
    # Инициализируем ДВЕ модели
    gemini_flash_model = genai.GenerativeModel(config.GEMINI_FLASH_MODEL_NAME)
    gemini_pro_model = genai.GenerativeModel(config.GEMINI_PRO_MODEL_NAME)
    print("✅ Успешная инициализация моделей Gemini Flash и Pro.")
except Exception as e:
    print(f"❌ Ошибка инициализации Gemini AI: {e}")
    exit()

async def get_routing_decisions(messages):
    """
    ЭТАП 1: Вызывает Gemini Flash для принятия решения: ответить или игнорировать.
    Возвращает список решений от AI.
    """
    print("   🤖 Этап 1: Отправка сообщений на сортировку в Gemini Flash...")
    prompt_template = db.get_prompt_template("router_prompt")
    if not prompt_template:
        print("   ❌ Не найден 'router_prompt' в базе данных!")
        return []

    messages_for_prompt = [
        {"message_id": msg.id, "text": msg.text.strip()}
        for msg in messages if msg.text and not msg.text.isspace()
    ]

    if not messages_for_prompt:
        return []

    messages_json = json.dumps(messages_for_prompt, ensure_ascii=False, indent=4)
    full_prompt = prompt_template.replace('{messages_for_prompt}', messages_json)

    try:
        response = await gemini_flash_model.generate_content_async(full_prompt)
        cleaned_response_text = response.text.strip().removeprefix('```json').removesuffix('```')
        decisions = json.loads(cleaned_response_text)
        print(f"   ✅ Сортировщик принял {len(decisions)} решений.")
        return decisions
    except Exception as e:
        print(f"   ❌ Критическая ошибка на этапе сортировки: {e}")
        return []

async def generate_final_reply(message, persona: str, chat_id: int):
    """
    ЭТАП 2: Вызывает Gemini Pro для генерации финального ответа на основе выбранной личности.
    """
    prompt_name = f"{persona}_prompt"
    print(f"   🤖 Этап 2: Генерация ответа с личностью '{persona}' через Gemini Pro...")

    prompt_template = db.get_prompt_template(prompt_name)
    if not prompt_template:
        print(f"   ❌ Не найден промпт '{prompt_name}' в базе данных!")
        return None

    # В личностный промпт передается только текст одного сообщения
    full_prompt = prompt_template.replace('{message_text}', message.text)

    try:
        response = await gemini_pro_model.generate_content_async(full_prompt)
        print("\n--- 📥 Ответ от Gemini Pro ---\n", response.text, "\n--------------------------\n")

        cleaned_response_text = response.text.strip().removeprefix('```json').removesuffix('```')
        # Ожидаем, что Pro вернет массив с одним объектом или пустой массив
        ai_actions = json.loads(cleaned_response_text)

        if not ai_actions:
            print(f"   ℹ️ Персона '{persona}' решила не отвечать на это сообщение.")
            return None

        # Берем первый (и единственный) сгенерированный ответ
        action = ai_actions[0]

        # Обогащаем действие дополнительной информацией для отправки на утверждение
        action.update({
            'target_chat_id': chat_id,
            'action_type': 'reply',
            'model_version': config.GEMINI_PRO_MODEL_NAME, # Указываем PRO модель
            'prompt_version': prompt_name,
            'original_message_text': message.text # Добавляем оригинальный текст
        })
        return action

    except Exception as e:
        print(f"   ❌ Критическая ошибка на этапе генерации ответа: {e}")
        return None