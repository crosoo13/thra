import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

from components import config
from components import database_manager as db
from components import telegram_processor
from components import sender_service

async def main():
	if not db.is_agent_active():
		return

	print("\n--- ✨ ЗАПУСК HR VISION AGENT ✨ ---\n")
	
	prompt_name = "hr_assistant_prompt"
	prompt_template = db.get_prompt_template(prompt_name)
	if not prompt_template:
		return

	session_string = db.get_session_string()
	
	print("🔄 Подключение к Telegram...")
	try:
		async with TelegramClient(StringSession(session_string), config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH) as client:
			print("✅ Клиент Telegram успешно инициализирован.")
			
			if not await client.is_user_authorized():
				print("❌ Пользователь не авторизован. Пожалуйста, запустите скрипт для создания сессии.")
				return

			me = await client.get_me()
			my_id = me.id
			print(f"✅ Скрипт запущен от имени: {me.first_name} (ID: {my_id})")

			await sender_service.send_pending_messages(client)
			
			target_chats = db.get_target_chats()
			if not target_chats:
				print("ℹ️ Целевые чаты для обработки не найдены.")
				return

			print("\n--- 🚀 Начало обработки чатов ---")
			for chat_info in target_chats:
				await telegram_processor.process_chat(client, chat_info, prompt_template, prompt_name, my_id)
			
			print("\n--- ✅ Все чаты обработаны ---\n")

	except Exception as e:
		print(f"❌ Критическая ошибка в main: {e}")

if __name__ == "__main__":
	try:
		config.validate_config()
		asyncio.run(main())
	except ValueError as e:
		print(e)
	except Exception as e:
		print(f"❌ Непредвиденная ошибка при запуске: {e}")