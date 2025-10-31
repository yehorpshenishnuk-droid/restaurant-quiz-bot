import asyncio
import os
import random
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# === Загрузка переменных окружения ===
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Проверь .env или Environment Variables на Render")

# === Настройка Google Sheets ===
SERVICE_FILE = "/etc/secrets/project-telegram-bot-475412-704fc4e68815.json"
SHEET_NAME = "MenuQuiz"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Авторизация Google Sheets
creds = Credentials.from_service_account_file(SERVICE_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

try:
    sheet = client.open(SHEET_NAME).sheet1
except Exception as e:
    raise RuntimeError(f"❌ Ошибка при подключении к Google Sheets: {e}")

# === Инициализация бота ===
bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Состояние пользователей ===
user_states = {}

# === Функция для начала теста ===
async def start_quiz(message: types.Message):
    await message.answer("🍽 Почнемо тест по меню!")
    await send_question(message)

# === Получение случайного вопроса из Google Sheets ===
def get_random_question():
    data = sheet.get_all_records()
    if not data:
        return None
    question = random.choice(data)
    return {
        "question": question.get("Question", ""),
        "options": [
            question.get("Option1"),
            question.get("Option2"),
            question.get("Option3"),
            question.get("Option4"),
        ],
        "answer": str(question.get("Answer")).strip()
    }

# === Отправка вопроса ===
async def send_question(message: types.Message):
    q = get_random_question()
    if not q:
        await message.answer("❌ В таблиці поки немає питань.")
        return

    user_states[message.from_user.id] = {"answer": q["answer"]}

    # 🧩 Создаём клавиатуру (исправлено для Aiogram 3)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=str(opt)) for opt in q["options"] if opt]
        ],
        resize_keyboard=True
    )

    await message.answer(f"❓ {q['question']}", reply_markup=keyboard)

# === Обработчики команд ===
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("👋 Вітаю! Напиши /quiz щоб розпочати тест по меню.")

@dp.message(Command("quiz"))
async def quiz_command(message: types.Message):
    await start_quiz(message)

# === Обработка ответов пользователей ===
@dp.message()
async def answer_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        await message.answer("⚠️ Спочатку напиши /quiz щоб почати тест.")
        return

    correct = user_states[user_id]["answer"]

    if message.text.strip().lower() == correct.lower():
        await message.answer("✅ Правильно!")
    else:
        await message.answer(f"❌ Неправильно! Правильна відповідь: {correct}")

    await send_question(message)

# === Основной запуск ===
async def main():
    print("✅ Bot запущен и работает через polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
