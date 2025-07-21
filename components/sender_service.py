# components/sender_service.py

from . import database_manager as db

async def send_pending_messages(client):
    """
    Проверяет очередь в Supabase и отправляет все одобренные, неопубликованные сообщения.
    
    Эта функция:
    1. Получает из базы данных все действия со статусом is_completed = false.
    2. Итерируется по ним и отправляет сообщения через Telethon.
    3. В случае успеха обновляет статус действия на is_completed = true.
    4. Логирует все успехи и ошибки.
    """
    print("\n--- 📬 Проверка очереди на отправку ---")
    
    # 1. Получаем список действий из базы данных
    pending_actions = db.get_pending_actions() 
    
    if not pending_actions:
        print("✅ Очередь на отправку пуста.")
        print("-" * 50)
        return

    print(f"📥 Найдено {len(pending_actions)} сообщений для отправки.")
    
    successful_sends = 0
    # 2. Проходим по каждому действию
    for action in pending_actions:
        action_id = action.get('id')
        try:
            # Извлекаем необходимые данные из записи
            chat_id = action['target_chat_id']
            reply_to_id = action['reply_to_message_id']
            message_text = action['message_text']
            
            print(f"  -> Отправка action_id: {action_id} в чат {chat_id}...")
            
            # 3. Используем клиент Telethon для отправки
            await client.send_message(
                entity=int(chat_id),       # Убедимся, что ID чата - это число
                message=message_text,
                reply_to=int(reply_to_id)  # И ID для ответа тоже
            )
            
            # 4. Если отправка успешна, помечаем действие как выполненное
            db.mark_action_as_completed(action_id)
            print(f"     ✅ Успешно отправлено. Запись {action_id} помечена как выполненная.")
            successful_sends += 1

        except TypeError as e:
            print(f"     ❌ Ошибка данных для action_id: {action_id}. Возможно, неверный ID чата или сообщения. Ошибка: {e}")
            # Возможно, стоит пометить это действие как ошибочное в БД
        except Exception as e:
            print(f"     ❌ Критическая ошибка при отправке action_id: {action_id}. Ошибка: {e}")
            # Оставляем is_completed = false для повторной попытки в следующий раз
            
    print(f"\n--- ✅ Отправка завершена. Успешно: {successful_sends} из {len(pending_actions)} ---")
    print("-" * 50)