# components/sender_service.py

from . import database_manager as db

async def send_pending_messages(client):
    """
    Проверяет очередь в Supabase и отправляет все одобренные, неопубликованные сообщения.
    
    ИЗМЕНЕНИЕ: После успешной отправки любого сообщения, записывает контакт с пользователем,
    чтобы избежать повторных сообщений в тот же день.
    """
    print("\n--- 📬 Проверка очереди на отправку ---")
    
    pending_actions = db.get_pending_actions()  
    
    if not pending_actions:
        print("✅ Очередь на отправку пуста.")
        print("-" * 50)
        return

    print(f"📥 Найдено {len(pending_actions)} действий для выполнения.")
    
    successful_sends = 0
    # Проходим по каждому действию
    for action in pending_actions:
        action_id = action.get('id')
        try:
            # Извлекаем необходимые данные из записи
            action_type = action.get('action_type', 'reply') # По умолчанию 'reply' для совместимости
            
            # В зависимости от типа действия, определяем получателя и текст
            if action_type == 'lead_outreach':
                # Это сообщение в личку лиду
                target_user_id = action.get('lead_user_id')
                message_text = action.get('pitch_text')
                # Для личных сообщений entity - это ID пользователя
                entity_to_send = int(target_user_id) if target_user_id else None
                reply_to_id = None # В личных сообщениях не отвечаем на что-то конкретное
                print(f"  -> Подготовка личного сообщения (lead_outreach) для пользователя {target_user_id}...")
            else: # action_type == 'reply' или 'keyword_alert'
                # Это ответ в публичном чате
                target_user_id = action.get('target_user_id')
                chat_id = action.get('target_chat_id')
                message_text = action.get('message_text')
                reply_to_id = action.get('reply_to_message_id')
                entity_to_send = int(chat_id) if chat_id else None
                print(f"  -> Подготовка ответа (reply) в чат {chat_id}...")

            # Проверяем, все ли данные на месте перед отправкой
            if not all([entity_to_send, message_text]):
                 print(f"      ❌ Пропуск action_id: {action_id}. Недостаточно данных (ID получателя или текст).")
                 continue
            
            # Используем клиент Telethon для отправки
            await client.send_message(
                entity=entity_to_send,
                message=message_text,
                reply_to=int(reply_to_id) if reply_to_id else None
            )
            
            # Если отправка успешна, помечаем действие как выполненное
            db.mark_action_as_completed(action_id)
            print(f"      ✅ Успешно отправлено. Запись {action_id} помечена как выполненная.")
            successful_sends += 1

            # --- ОБНОВЛЕННЫЙ БЛОК ЛОГИРОВАНИЯ ---
            # 1. Записываем, что мы связались с этим пользователем сегодня
            if target_user_id:
                db.record_user_contact(int(target_user_id))

            # 2. Обновляем метку времени последнего *публичного ответа* в чате, чтобы соблюдать часовой лимит
            if action_type == 'reply':
                db.update_last_post_time(int(action.get('target_chat_id')))
            # --- КОНЕЦ ОБНОВЛЕННОГО БЛОКА ---

        except TypeError as e:
            print(f"      ❌ Ошибка данных для action_id: {action_id}. Возможно, неверный ID. Ошибка: {e}")
            # Возможно, стоит пометить это действие как ошибочное в БД
        except Exception as e:
            print(f"      ❌ Критическая ошибка при отправке action_id: {action_id}. Ошибка: {e}")
            # Оставляем is_completed = false для повторной попытки в следующий раз
            
    print(f"\n--- ✅ Отправка завершена. Успешно: {successful_sends} из {len(pending_actions)} ---")
    print("-" * 50)