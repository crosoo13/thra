# ai_processor.py
import json
import google.generativeai as genai
from . import config

try:
    genai.configure(api_key=config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
    print("✅ Успешная инициализация Gemini AI.")
except Exception as e:
    print(f"❌ Ошибка инициализации Gemini AI: {e}")
    exit()

async def get_ai_actions(messages, chat_id, prompt_template: str, prompt_name: str):
    messages_for_prompt = [
        {"message_id": msg.id, "text": msg.text.strip()}
        for msg in messages if msg.text and not msg.text.isspace()
    ]

    if not messages_for_prompt:
        print("   ℹ️ В пакете не осталось сообщений с текстом для анализа.")
        return []

    messages_json = json.dumps(messages_for_prompt, ensure_ascii=False, indent=4)
    full_prompt = prompt_template.replace('{messages_for_prompt}', messages_json)

    try:
        print(f"   🤖 Отправка {len(messages_for_prompt)} сообщений в Gemini...")
        response = await gemini_model.generate_content_async(full_prompt)

        # Логирование ответа для отладки
        print("\n--- 📥 Ответ от Gemini AI ---\n", response.text, "\n----------------------------\n")

        cleaned_response_text = response.text.strip().removeprefix('```json').removesuffix('```')
        ai_actions = json.loads(cleaned_response_text)

        # Обогащаем каждое действие дополнительной информацией
        for action in ai_actions:
            action.update({
                'target_chat_id': chat_id,
                'action_type': 'reply',
                'model_version': config.GEMINI_MODEL_NAME,
                'prompt_version': prompt_name
            })
        return ai_actions

    except json.JSONDecodeError:
        print(f"   ❌ Ошибка: Gemini вернул невалидный JSON. Ответ залогирован выше.")
        return []
    except Exception as e:
        print(f"   ❌ Критическая ошибка при работе с Gemini API: {e}")
        return []