from . import database_manager as db
from . import ai_processor
from . import approval_service

async def process_chat(client, chat_info, prompt_template, prompt_name, my_id):
    """
    Полный цикл обработки одного чата: от получения сообщений до отправки на утверждение.
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
                print(f"   ✅ Найден связанный чат для комментариев: {processing_id}")
            else:
                print(f"   ⚠️ Для канала {original_chat_id} комментарии отключены. Пропускаем.")
                return

        last_id = db.get_last_message_id(processing_id)

        # Первый запуск для чата
        if last_id == 0:
            print(f"   --- ПЕРВЫЙ ЗАПУСК для чата {processing_id} ---")
            async for last_message in client.iter_messages(entity, limit=1):
                if last_message:
                    db.update_last_message_id(processing_id, last_message.id)
                    print(f"   ✅ Точка старта установлена на ID: {last_message.id}. Обработка начнется со следующего запуска.")
                else:
                    print("   ⚠️ Чат пуст. Невозможно установить точку старта.")
                return

        print(f"   ID последнего обработанного сообщения: {last_id}")
        print("   🔄 Получение новых сообщений...")

        messages_to_process = []
        newest_message_id = last_id
        async for message in client.iter_messages(entity, min_id=last_id, limit=None, reverse=True):
            
            if message.sender_id == my_id:
                continue
            
            if message and message.text:
                messages_to_process.append(message)
                if message.id > newest_message_id:
                    newest_message_id = message.id

        if not messages_to_process:
            print("   ✅ Новых сообщений для обработки нет.")
            return

        print(f"   📩 Найдено {len(messages_to_process)} новых сообщений.")
        
        # --- БЛОК ПРОВЕРКИ НА КЛЮЧЕВЫЕ СЛОВА ---
        KEYWORD_TRIGGERS = ["массовый", "массового", "вахтой", "вахтовым"]
        print("   🔍 Проверка сообщений на ключевые слова...")
        for message in messages_to_process:
            if message.text and any(keyword in message.text.lower() for keyword in KEYWORD_TRIGGERS):
                print(f"   🚨 Найдено ключевое слово в сообщении {message.id} из чата {processing_id}!")
                alert_payload = {
                    'action_type': 'keyword_alert',
                    'target_chat_id': processing_id,
                    'original_message_text': message.text,
                    'reply_to_message_id': message.id
                }
                # <--- ИЗМЕНЕНИЕ: Убираем комментарий, чтобы отправка работала
                approval_service.send_action_for_approval(alert_payload)
        # --- КОНЕЦ БЛОКА ---
        
        actions = await ai_processor.get_ai_actions(messages_to_process, processing_id, prompt_template, prompt_name)

        if not actions:
            print("   ℹ️ AI не сгенерировал никаких действий.")
        else:
            print(f"   🤖 AI сгенерировал {len(actions)} действий. Отправка на утверждение...")
            for action in actions:
                original_text = next((msg.text for msg in messages_to_process if msg.id == action.get('reply_to_message_id')), "Текст не найден")
                action['original_message_text'] = original_text
                # <--- ИЗМЕНЕНИЕ: И здесь тоже убираем комментарий
                approval_service.send_action_for_approval(action)

        if newest_message_id > last_id:
            db.update_last_message_id(processing_id, newest_message_id)

    except Exception as e:
        print(f"❌ Произошла критическая ошибка при обработке чата {original_chat_id}: {e}")
    finally:
        print("-" * 50)