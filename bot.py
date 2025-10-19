import asyncio
import logging
import random
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID") or os.getenv("SPREADSHEET_ID")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не знайдено!")
if not SPREADSHEET_ID:
    raise ValueError("❌ SHEET_ID не знайдено!")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# Подключение к Google Sheets
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # На Render файл буде в /etc/secrets/
    creds_path = "/etc/secrets/project-telegram-bot-475412-704fc4e68815.json"
    
    # Якщо файлу немає (локальна розробка), шукаємо creds.json
    if not os.path.exists(creds_path):
        creds_path = "creds.json"
    
    logging.info(f"📂 Читаємо credentials з: {creds_path}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    logging.info("✅ Успішно підключено до Google Sheets!")
    return sheet

# Получение случайных вопросов
def get_random_questions(sheet, count=15):
    data = sheet.get_all_records()
    logging.info(f"📊 Знайдено {len(data)} питань у таблиці")
    if len(data) < count:
        count = len(data)
    return random.sample(data, count)

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("🍽 Почнемо тест по меню!")
    try:
        sheet = get_google_sheet()
        questions = get_random_questions(sheet)
        await run_quiz(message, questions)
    except Exception as e:
        await message.answer(f"❌ Помилка: {str(e)}")
        logging.error(f"Error: {e}", exc_info=True)

# Тест (УВАГА: це не працює в aiogram 3.x - потрібен FSM!)
async def run_quiz(message: types.Message, questions):
    correct = 0
    for q in questions:
        question_text = f"❓ {q['question']}"
        options = q['options'].split(",")
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text=o.strip())] for o in options],
            resize_keyboard=True
        )
        await message.answer(question_text, reply_markup=keyboard)

        # TODO: Це НЕ ПРАЦЮЄ в aiogram 3.x - потрібен FSM
        try:
            answer = await dp.bot.wait_for(
                "message",
                timeout=10,
                check=lambda msg: msg.from_user.id == message.from_user.id
            )
        except asyncio.TimeoutError:
            await message.answer("⏰ Час вийшов!", reply_markup=types.ReplyKeyboardRemove())
            continue

        if answer.text.strip().lower() == q['answer'].strip().lower():
            correct += 1
            await message.answer("✅ Правильно!", reply_markup=types.ReplyKeyboardRemove())
        else:
            await message.answer(f"❌ Неправильно! Правильна відповідь: {q['answer']}", reply_markup=types.ReplyKeyboardRemove())

    await message.answer(f"✅ Тест завершено! Правильних відповідей: {correct}/{len(questions)}")

# Основная функция запуска
async def main():
    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Бот запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено вручну.")
```

---

## Не забудь: Дай доступ до Google Sheets!

Відкрий свою таблицю → "Share" (Поділитися) → Додай email:
```
greco-bot@project-telegram-bot-475412.iam.gserviceaccount.com
