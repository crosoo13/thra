# ai_processor.py

import json
import google.generativeai as genai
from . import config
from . import database_manager as db

try:
    genai.configure(api_key=config.GEMINI_API_KEY)
    gemini_flash_model = genai.GenerativeModel(config.GEMINI_FLASH_MODEL_NAME)
    gemini_pro_model = genai.GenerativeModel(config.GEMINI_PRO_MODEL_NAME)
    print("✅ Успешная инициализация моделей Gemini Flash и Pro.")
except Exception as e:
    print(f"❌ Ошибка инициализации Gemini AI: {e}")
    exit()

async def get_routing_decisions(messages):
    """
    ЭТАП 1: Вызывает Gemini Flash для принятия решения: ответить или игнорировать.
    """
    print("  🤖 Этап 1: Отправка сообщений на сортировку в Gemini Flash...")
    prompt_template = db.get_prompt_template("router_prompt")
    if not prompt_template:
        print("    ❌ Не найден 'router_prompt' в базе данных!")
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
        print(f"    ✅ Сортировщик принял {len(decisions)} решений.")
        return decisions
    except Exception as e:
        print(f"    ❌ Критическая ошибка на этапе сортировки: {e}")
        return []

async def generate_final_reply(conversation_history, persona: str, chat_id: int, my_id: int):
    """
    ЭТАП 2: Вызывает Gemini Pro для генерации ответа, используя контекст переписки.
    """
    prompt_name = f"{persona.lower()}_prompt"
    print(f"  🤖 Этап 2: Генерация ответа с личностью '{persona}' (промпт: '{prompt_name}')...")

    prompt_template = db.get_prompt_template(prompt_name)
    if not prompt_template:
        print(f"    ❌ Не найден промпт '{prompt_name}' в базе данных!")
        return None

    # --- ФОРМИРОВАНИЕ ПРИМЕРОВ ---
    good_examples = db.get_examples_by_status(prompt_name, status='approved', limit=10)
    good_examples_string = ""
    if good_examples:
        example_texts = [f"Исходное сообщение: {ex['original_message_text']}\nТвой удачный ответ: {ex['ai_generated_text']}" for ex in good_examples if ex.get('original_message_text') and ex.get('ai_generated_text')]
        if example_texts:
            good_examples_string = "Вот несколько свежих примеров твоих удачных ответов в этой роли. Изучи их, чтобы сохранить свой стиль:\n" + "\n---\n".join(example_texts)

    bad_examples = db.get_examples_by_status(prompt_name, status='declined', limit=10)
    bad_examples_string = ""
    if bad_examples:
        example_texts = [f"Исходное сообщение: {ex['original_message_text']}\nТвой НЕУДАЧНЫЙ ответ: {ex['ai_generated_text']}" for ex in bad_examples if ex.get('original_message_text') and ex.get('ai_generated_text')]
        if example_texts:
            bad_examples_string = "\nА вот так делать НЕ НАДО. Это примеры твоих недавних неудачных ответов, которые были отклонены. Изучи их, чтобы не повторять ошибок:\n" + "\n---\n".join(example_texts)

    # --- СБОРКА ФИНАЛЬНОГО ПРОМТА ---
    prompt_with_good = prompt_template.replace('{dynamic_examples}', good_examples_string)
    prompt_with_bad = prompt_with_good.replace('{bad_examples}', bad_examples_string)

    # Форматируем историю переписки в JSON
    history_for_prompt = []
    for msg in conversation_history:
        history_for_prompt.append({
            "id": msg.id,
            "author": "me" if msg.sender_id == my_id else "user",
            "text": msg.text.strip() if msg.text else ""
        })
    
    history_json_string = json.dumps(history_for_prompt, ensure_ascii=False, indent=4)
    full_prompt = prompt_with_bad.replace('{conversation_history_json}', history_json_string)
    
    # --- ВЫЗОВ AI И ОБРАБОТКА ОТВЕТА ---
    try:
        response = await gemini_pro_model.generate_content_async(full_prompt)
        print("\n--- 📥 Ответ от Gemini Pro ---\n", response.text, "\n--------------------------\n")

        cleaned_response_text = response.text.strip().removeprefix('```json').removesuffix('```')
        ai_actions = json.loads(cleaned_response_text)

        if not ai_actions:
            print(f"    ℹ️ Персона '{persona}' решила не отвечать на это сообщение.")
            return None

        action = ai_actions[0]
        
        # Важно: текст оригинального сообщения теперь - это текст ПОСЛЕДНЕГО сообщения в треде
        original_message_text = conversation_history[-1].text if conversation_history else ""

        action.update({
            'target_chat_id': chat_id,
            'action_type': 'reply',
            'model_version': config.GEMINI_PRO_MODEL_NAME,
            'prompt_version': prompt_name,
            'original_message_text': original_message_text
        })
        return action

    except json.JSONDecodeError:
        print(f"    ❌ Ошибка: Gemini Pro вернул невалидный JSON. Ответ залогирован выше.")
        return None
    except Exception as e:
        print(f"    ❌ Критическая ошибка на этапе генерации ответа: {e}")
        return None