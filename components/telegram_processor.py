# 1. Добавляем импорты для работы с датой и временем
from datetime import datetime, timezone
from . import database_manager as db
from . import ai_processor
from . import approval_service

async def process_chat(client, chat_info, prompt_template, prompt_name, my_id):
    """
    Полный цикл обработки одного чата: от получения сегодняшних сообщений до отправки на утверждение.
    """
    original_chat_id = chat_info['chat_id']
    chat_type = chat_info.get('chat_type', 'group')
    processing_id = original_chat_id

    try:
        print(f"\n▶️ Обработка чата: {original_chat_id} (тип: {chat_type})")
        entity = await client.get_entity(original_chat_id)

        # Если это канал, ищем связанный чат для комментариев
        if chat_type == 'channel':
            if hasattr(entity, 'linked_chat_id') and entity.linked_chat_id:
                processing_id = entity.linked_chat_id
                entity = await client.get_entity(processing_id)
                print(f"  ✅ Найден связанный чат для комментариев: {processing_id}")
            else:
                print(f"  ⚠️ Для канала {original_chat_id} комментарии отключены. Пропускаем.")
                return

        # 2. КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Определяем начало сегодняшнего дня и получаем последний ID
        # Получаем ID последнего сообщения, которое было обработано ранее (возможно, вчера)
        last_id = db.get_last_message_id(processing_id)
        # Определяем начало сегодняшнего дня в UTC, чтобы запрашивать сообщения только за сегодня
        today_start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        print(f"  ID последнего обработанного сообщения из БД: {last_id}")
        print("  🔄 Получение новых сообщений, отправленных СЕГОДНЯ...")

        messages_to_process = []
        newest_message_id = last_id
        
        # 3. ИЗМЕНЕННЫЙ ЦИКЛ: Используем offset_date для загрузки сообщений только за сегодня
        async for message in client.iter_messages(entity, offset_date=today_start_utc, reverse=True):
            
            # Пропускаем сообщения, которые уже могли быть обработаны, если скрипт запускается не первый раз за день
            if message.id <= last_id:
                continue
            
            # Пропускаем сообщения от самого себя
            if message.sender_id == my_id:
                continue
            
            # Добавляем в список только сообщения с текстом
            if message and message.text:
                messages_to_process.append(message)
                if message.id > newest_message_id:
                    newest_message_id = message.id

        if not messages_to_process:
            print("  ✅ Новых сообщений для обработки сегодня нет.")
            return

        print(f"  📩 Найдено {len(messages_to_process)} новых сообщений за сегодня.")
        
        # --- БЛОК ПРОВЕРКИ НА КЛЮЧЕВЫЕ СЛОВА (остается без изменений) ---
        KEYWORD_TRIGGERS = ["массовый", "массового", "вахтой", "вахтовым"]
        print("  🔍 Проверка сообщений на ключевые слова...")
        for message in messages_to_process:
            if message.text and any(keyword in message.text.lower() for keyword in KEYWORD_TRIGGERS):
                print(f"  🚨 Найдено ключевое слово в сообщении {message.id} из чата {processing_id}!")
                alert_payload = {
                    'action_type': 'keyword_alert',
                    'target_chat_id': processing_id,
                    'original_message_text': message.text,
                    'reply_to_message_id': message.id
                }
                approval_service.send_action_for_approval(alert_payload)
        # --- КОНЕЦ БЛОКА ---
        
        actions = await ai_processor.get_ai_actions(messages_to_process, processing_id, prompt_template, prompt_name)

        if not actions:
            print("  ℹ️ AI не сгенерировал никаких действий.")
        else:
            print(f"  🤖 AI сгенерировал {len(actions)} действий. Отправка на утверждение...")
            for action in actions:
                original_text = next((msg.text for msg in messages_to_process if msg.id == action.get('reply_to_message_id')), "Текст не найден")
                action['original_message_text'] = original_text
                approval_service.send_action_for_approval(action)

        # Обновляем ID последнего сообщения, только если были найдены новые
        if newest_message_id > last_id:
            db.update_last_message_id(processing_id, newest_message_id)

    except Exception as e:
        print(f"❌ Произошла критическая ошибка при обработке чата {original_chat_id}: {e}")
    finally:
        print("-" * 50)