from . import ai_processor
from . import approval_service

async def find_and_process_leads(client, messages):
    """
    Основная функция "Охотника за лидами".
    1. Классифицирует все сообщения, чтобы найти лиды.
    2. Для каждого найденного лида генерирует персонализированное сообщение.
    3. Отправляет готовый результат на утверждение.
    """
    if not messages:
        # Это дополнительная проверка, хотя main.py уже делает такую.
        return

    # 1. Отправляем ВСЕ сообщения на классификацию для поиска лидов
    print("  🕵️‍♂️ Отправка сообщений на классификацию (поиск лидов)...")
    lead_decisions = await ai_processor.get_lead_decisions(messages)
    
    if not lead_decisions:
        print("  ✅ AI-классификатор не вернул решений.")
        return

    # 2. Фильтруем результаты, чтобы работать только с лидами
    hot_leads = [d for d in lead_decisions if d.get('lead_type') == 'hot_lead']
    cold_leads = [d for d in lead_decisions if d.get('lead_type') == 'cold_lead']

    if not hot_leads and not cold_leads:
        print("  ✅ Потенциальные лиды не найдены после классификации.")
        return

    print(f"  🔥 Найдено горячих лидов: {len(hot_leads)}. ❄️ Найдено холодных: {len(cold_leads)}.")

    all_leads = hot_leads + cold_leads
    # Создаем словарь для быстрого доступа к объекту сообщения по его ID
    message_map = {msg.id: msg for msg in messages}

    # 3. Обрабатываем каждый найденный лид
    for lead_decision in all_leads:
        message_id = lead_decision.get('message_id')
        target_message = message_map.get(message_id)

        if not target_message or not hasattr(target_message, 'sender') or not target_message.sender:
            print(f"  ⚠️ Пропускаем лид для сообщения {message_id}: не найден автор.")
            continue
        
        # 4. Для каждого лида генерируем персонализированное сообщение
        print(f"  🤖 Генерация персонального сообщения для лида (ID сообщения: {message_id})...")
        generated_pitch = await ai_processor.generate_lead_outreach_message(target_message)

        if not generated_pitch or not generated_pitch.get('pitch_text'):
            print(f"  ⚠️ AI-генератор не создал текст для лида {message_id}.")
            continue

        # 5. Формируем полный пакет данных и отправляем его воркеру на утверждение
        lead_payload = {
            'action_type': 'lead_outreach', # Новый тип действия для воркера
            'lead_type': lead_decision.get('lead_type'),
            'lead_user_id': target_message.sender.id,
            'lead_username': target_message.sender.username,
            'lead_first_name': target_message.sender.first_name,
            'original_message_text': target_message.text,
            'original_message_id': target_message.id,
            'source_chat_id': target_message.chat_id,
            'pitch_text': generated_pitch.get('pitch_text')
        }
        
        print(f"  📤 Отправка лида '{lead_payload['lead_first_name']}' ({lead_payload['lead_type']}) на утверждение...")
        # Используем уже существующий сервис для отправки
        approval_service.send_action_for_approval(lead_payload)