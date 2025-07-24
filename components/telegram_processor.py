# 1. Все необходимые импорты
from datetime import datetime, timezone
from . import database_manager as db
from . import ai_processor
from . import approval_service

async def process_chat(client, chat_info, prompt_template, prompt_name, my_id):
    """
    Финальная версия цикла обработки одного чата со всеми исправлениями.
    """
    original_chat_id = chat_info['chat_id']
    chat_type = chat_info.get('chat_type', 'group')
    processing_id = original_chat_id

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
        
        # --- ВОЗВРАЩАЕМ БЛОК ПРОВЕРКИ НА КЛЮЧЕВЫЕ СЛОВА ---
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

        print("  🤖 Запуск AI-конвейера...")
        # ЭТАП 1: Получаем решения от "сортировщика"
        routing_decisions = await ai_processor.get_routing_decisions(messages_to_process)

        if not routing_decisions:
            print("  ℹ️ Сортировщик не вернул никаких решений. Обработка завершена.")
        else:
            final_actions_to_approve = []
            message_map = {msg.id: msg for msg in messages_to_process}

            # ЭТАП 2: Генерируем ответы
            for decision in routing_decisions:
                if decision.get('decision') == 'reply':
                    message_id = decision.get('message_id')
                    persona = decision.get('persona')
                    message_to_reply = message_map.get(message_id)

                    if message_to_reply and persona:
                        final_action = await ai_processor.generate_final_reply(message_to_reply, persona, processing_id)
                        if final_action:
                            final_actions_to_approve.append(final_action)
            
            if final_actions_to_approve:
                print(f"  🚀 Сгенерировано {len(final_actions_to_approve)} ответов. Отправка на утверждение...")
                for action in final_actions_to_approve:
                    approval_service.send_action_for_approval(action)
            else:
                 print("  ✅ AI обработал сообщения, но не сгенерировал ни одного ответа для отправки.")

        # Обновляем ID последнего сообщения, только если были найдены новые
        if newest_message_id > last_id:
            db.update_last_message_id(processing_id, newest_message_id)

    except Exception as e:
        print(f"❌ Произошла критическая ошибка при обработке чата {original_chat_id}: {e}")
    finally:
        print("-" * 50)