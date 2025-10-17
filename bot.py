import asyncio
import logging
import random
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os

# Загрузка переменных окружения (.env)
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Категории (если нужно использовать фильтры)
HOT_CATEGORIES = {4, 13, 15, 46, 33}
COLD_CATEGORIES = {7, 8, 11, 16, 18, 19, 29, 32, 36, 44}
BAR_CATEGORIES = {9, 14, 27, 28, 34, 41, 42, 47, 22, 24, 25, 26, 39, 30}

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# Подключение к Google Sheets
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet

# Получение случайных вопросов
def get_random_questions(sheet, count=15):
    data = sheet.get_all_records()
    if len(data) < count:
        count = len(data)
    return random.sample(data, count)

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("🍽 Почнемо тест по меню!")
    sheet = get_google_sheet()
    questions = get_random_questions(sheet)
    await run_quiz(message, questions)

# Тест
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
    await bot.delete_webhook(drop_pending_updates=True)  # снимает конфликт polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено вручну.")
