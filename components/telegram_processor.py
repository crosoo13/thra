from datetime import datetime, timezone
from . import database_manager as db
from . import ai_processor
from . import approval_service

async def process_chat(client, chat_info, prompt_template, prompt_name, my_id):
    """
    Финальная версия цикла обработки одного чата со сбором контекста
    и строгим правилом "один ответ на один запуск".
    """
    original_chat_id = chat_info['chat_id']
    chat_type = chat_info.get('chat_type', 'group')
    processing_id = original_chat_id

    # Загружаем ключевые слова из БД
    keyword_triggers = db.get_keyword_triggers()

    try:
        print(f"\n▶️ Обработка чата: {original_chat_id} (тип: {chat_type})")
        entity = await client.get_entity(original_chat_id)

        if chat_type == 'channel':
            if hasattr(entity, 'linked_chat_id') and entity.linked_chat_id:
                processing_id = entity.linked_chat_id
                entity = await client.get_entity(processing_id)
                print(f"  ✅ Найден связанный чат для комментариев: {processing_id}")
            else:
                print(f"  ⚠️ Для канала {original_chat_id} комментарии отключены. Пропускаем.")
                return

        last_id = db.get_last_message_id(processing_id)
        today_start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        print(f"  ID последнего обработанного сообщения из БД: {last_id}")
        print("  🔄 Получение новых сообщений, отправленных СЕГОДНЯ...")

        messages_to_process = []
        newest_message_id = last_id
        
        async for message in client.iter_messages(entity, offset_date=today_start_utc, reverse=True):
            if message.id <= last_id:
                continue
            if message.sender_id == my_id:
                continue
            if message and message.text:
                messages_to_process.append(message)
                if message.id > newest_message_id:
                    newest_message_id = message.id

        if not messages_to_process:
            print("  ✅ Новых сообщений для обработки сегодня нет.")
            return

        print(f"  📩 Найдено {len(messages_to_process)} новых сообщений.")
        
        if keyword_triggers:
            print("  🔍 Проверка сообщений на ключевые слова...")
            for message in messages_to_process:
                if message.text and any(keyword.lower() in message.text.lower() for keyword in keyword_triggers):
                    print(f"  🚨 Найдено ключевое слово в сообщении {message.id} из чата {processing_id}!")
                    alert_payload = {
                        'action_type': 'keyword_alert',
                        'target_chat_id': processing_id,
                        'original_message_text': message.text,
                        'reply_to_message_id': message.id
                    }
                    approval_service.send_action_for_approval(alert_payload)
        else:
            print("  ℹ️ Список ключевых слов пуст, проверка пропускается.")


        print("  🤖 Запуск AI-конвейера...")
        routing_decisions = await ai_processor.get_routing_decisions(messages_to_process)

        if routing_decisions:
            decisions_to_reply = [d for d in routing_decisions if d.get('decision') == 'reply']
            
            final_decision = None
            if decisions_to_reply:
                if len(decisions_to_reply) > 1:
                    print(f"  ⚠️ AI предложил {len(decisions_to_reply)} ответов. Выбираем только первый, согласно правилу.")
                final_decision = decisions_to_reply[0]

            if final_decision:
                message_id_to_reply = final_decision.get('message_id')
                persona = final_decision.get('persona')
                message_map = {msg.id: msg for msg in messages_to_process}
                target_message = message_map.get(message_id_to_reply)

                if target_message and persona:
                    print(f"  🔄 Сбор контекста для сообщения {target_message.id}...")
                    conversation_history = []
                    # Собираем 5 сообщений до целевого + само целевое сообщение
                    async for msg in client.iter_messages(entity, limit=6, offset_id=target_message.id + 1):
                        conversation_history.append(msg)
                    
                    # Переворачиваем, чтобы сообщения шли в хронологическом порядке
                    conversation_history.reverse()
                    
                    print(f"  ✅ Собран контекст из {len(conversation_history)} сообщений.")

                    final_action = await ai_processor.generate_final_reply(conversation_history, persona, processing_id, my_id)
                    
                    if final_action:
                        print(f"  🚀 Сгенерирован 1 ответ. Отправка на утверждение...")
                        approval_service.send_action_for_approval(final_action)
                    else:
                        print("  ✅ AI решил ответить, но генератор не создал финальный текст.")
            else:
                print("  ✅ AI обработал сообщения, но не нашел ни одного подходящего для ответа.")

        if newest_message_id > last_id:
            db.update_last_message_id(processing_id, newest_message_id)

    except Exception as e:
        print(f"❌ Произошла критическая ошибка при обработке чата {original_chat_id}: {e}")
    finally:
        print("-" * 50)