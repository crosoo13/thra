from datetime import datetime, timezone, timedelta
from . import database_manager as db
from . import ai_processor
from . import approval_service

async def process_chat_for_engagement(client, chat_info, my_id, keyword_triggers):
    """
    ОБНОВЛЕННАЯ ВЕРСИЯ:
    Обрабатывает ОДИН чат для публичного вовлечения ("Агент влияния").
    Добавлена проверка на часовой лимит, ограничение на количество сообщений для анализа
    и проверка на повторный контакт с пользователем в течение дня.
    """
    # --- НАСТРОЙКА ЛИМИТА ИСТОРИИ ---
    # 👇 Вот новая настройка. Можете менять это число.
    MESSAGE_HISTORY_LIMIT = 7 
    # ------------------------------------

    original_chat_id = chat_info['chat_id']
    chat_type = chat_info.get('chat_type', 'group')
    processing_id = original_chat_id

    try:
        print(f"\n▶️  Обработка чата (Агент влияния): {original_chat_id} (тип: {chat_type})")

        # --- ПРОВЕРКА ЧАСОВОГО ЛИМИТА ---
        last_post_time = db.get_last_post_time(processing_id)
        if last_post_time:
            time_since_last_post = datetime.now(timezone.utc) - last_post_time
            if time_since_last_post < timedelta(hours=1):
                print(f" 	⏳ Часовой лимит для чата {processing_id} еще не истек. Пропускаем.")
                print("-" * 50)
                return None
        
        entity = await client.get_entity(original_chat_id)

        # Логика для каналов и связанных с ними чатов комментариев
        if chat_type == 'channel':
            if hasattr(entity, 'linked_chat_id') and entity.linked_chat_id:
                processing_id = entity.linked_chat_id
                entity = await client.get_entity(processing_id)
                print(f" 	✅ Найден связанный чат для комментариев: {processing_id}")
            else:
                print(f" 	⚠️ Для канала {original_chat_id} комментарии отключены. Пропускаем.")
                return None

        # Получение новых сообщений
        last_id = db.get_last_message_id(processing_id)
        today_start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        print(f" 	ID последнего обработанного сообщения из БД: {last_id}")
        print(" 	🔄 Получение новых сообщений, отправленных СЕГОДНЯ...")

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
            if newest_message_id > last_id:
                db.update_last_message_id(processing_id, newest_message_id)
            print(" 	✅ Новых сообщений для публичного ответа нет.")
            return None

        print(f" 	📩 Найдено {len(messages_to_process)} новых сообщений для анализа.")
        
        # --- БЛОК ОГРАНИЧЕНИЯ КОЛИЧЕСТВА СООБЩЕНИЙ ДЛЯ АНАЛИЗА ---
        if len(messages_to_process) > 10:
            print(f" 	✂️ Сообщений слишком много. Для анализа будут взяты только последние 10.")
            messages_for_ai_analysis = messages_to_process[-10:]
        else:
            messages_for_ai_analysis = messages_to_process
        # --- КОНЕЦ БЛОКА ---

        # 1. Проверка на ключевые слова (проверяем все сообщения, а не только последние 10)
        if keyword_triggers:
            print(" 	🔍 Проверка сообщений на ключевые слова...")
            for message in messages_to_process:
                if message.text and any(keyword.lower() in message.text.lower() for keyword in keyword_triggers):
                    print(f" 	🚨 Найдено ключевое слово в сообщении {message.id}!")
                    alert_payload = {
                        'action_type': 'keyword_alert',
                        'target_chat_id': processing_id,
                        'original_message_text': message.text,
                        'reply_to_message_id': message.id
                    }
                    approval_service.send_action_for_approval(alert_payload)
        else:
            print(" 	ℹ️ Список ключевых слов пуст, проверка пропускается.")

        # 2. Запуск AI-конвейера для публичного ответа (используем ограниченный список)
        print(" 	🤖 Запуск AI-конвейера (Агент влияния)...")
        routing_decisions = await ai_processor.get_routing_decisions(messages_for_ai_analysis)

        if routing_decisions:
            decisions_to_reply = [d for d in routing_decisions if d.get('decision') == 'reply']
            
            final_decision = None
            if decisions_to_reply:
                if len(decisions_to_reply) > 1:
                    print(f" 	⚠️ AI предложил {len(decisions_to_reply)} ответов. Выбираем только первый, согласно правилу.")
                final_decision = decisions_to_reply[0]

            if final_decision:
                message_id_to_reply = final_decision.get('message_id')
                persona = final_decision.get('persona')
                # Важно: ищем сообщение в полном списке, чтобы получить правильный объект
                message_map = {msg.id: msg for msg in messages_to_process}
                target_message = message_map.get(message_id_to_reply)

                # --- НАЧАЛО НОВОГО БЛОКА ПРОВЕРКИ ---
                if target_message and db.was_user_contacted_today(target_message.sender_id):
                    print(f" 	🚫 Пользователь {target_message.sender_id} уже получал ответ сегодня. Ответ от 'Агента влияния' пропускается.")
                # --- КОНЕЦ НОВОГО БЛОКА ПРОВЕРКИ ---
                
                elif target_message and persona: # ИЗМЕНЕНО: добавлено 'elif'
                    
                    # --- НОВАЯ ЛОГИКА ОГРАНИЧЕНИЯ ИСТОРИИ ПЕРЕПИСКИ ---
                    print(f" 	🔄 Сбор контекста для сообщения {target_message.id}...")
                    try:
                        # Находим индекс целевого сообщения в списке, который видел AI
                        target_index = messages_for_ai_analysis.index(target_message)
                        # Берем срез всех сообщений до целевого (включительно)
                        history_slice = messages_for_ai_analysis[:target_index + 1]
                        # Из этого среза берем только N последних сообщений
                        conversation_history = history_slice[-MESSAGE_HISTORY_LIMIT:]
                    except ValueError:
                        # Если сообщение не найдено (маловероятно), берем его одно
                        conversation_history = [target_message]
                    # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

                    print(f" 	✅ Собран контекст из {len(conversation_history)} сообщений (лимит: {MESSAGE_HISTORY_LIMIT}).")

                    final_action = await ai_processor.generate_final_reply(conversation_history, persona, processing_id, my_id)
                    
                    if final_action:
                        print(" 	🚀 Сгенерирован 1 публичный ответ. Отправка на утверждение...")
                        approval_service.send_action_for_approval(final_action)
                    else:
                        print(" 	✅ AI решил ответить, но генератор не создал финальный текст.")
            else:
                print(" 	✅ AI (Агент влияния) не нашел подходящего сообщения для ответа.")

        # Обновляем ID последнего сообщения в базе данных (используя ID из полного списка)
        if newest_message_id > last_id:
            db.update_last_message_id(processing_id, newest_message_id)

        # Возвращаем полный список собранных сообщений для "Охотника за лидами"
        return messages_to_process

    except Exception as e:
        print(f"❌ Произошла критическая ошибка при обработке чата {original_chat_id}: {e}")
        return None
    finally:
        print("-" * 50)