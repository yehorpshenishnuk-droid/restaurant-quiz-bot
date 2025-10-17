import asyncio
import os
import random
import datetime
import gspread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from google.oauth2.service_account import Credentials

# --- Load environment variables ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
POSTER_TOKEN = os.getenv("POSTER_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")

# --- Google Sheets connection ---
credentials = Credentials.from_service_account_file(
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SHEET_ID).sheet1

# --- Bot initialization ---
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- Example questions ---
questions = [
    {
        "dish": "Салат Цезар",
        "question": "Яка вага салату Цезар?",
        "options": ["200 г", "250 г", "300 г", "350 г"],
        "answer": "300 г"
    },
    {
        "dish": "Плов який Ви полюбите",
        "question": "Яка ціна плову?",
        "options": ["139 ₴", "149 ₴", "159 ₴", "169 ₴"],
        "answer": "169 ₴"
    },
]

user_progress = {}

async def send_question(user_id):
    """Відправляє наступне питання користувачу"""
    if user_id not in user_progress:
        user_progress[user_id] = {"index": 0, "correct": 0}

    idx = user_progress[user_id]["index"]

    if idx >= len(questions):
        await bot.send_message(
            user_id,
            f"✅ Тест завершено! Правильних відповідей: {user_progress[user_id]['correct']}/{len(questions)}"
        )
        # запис у Google Sheet
        sheet.append_row([
            str(datetime.datetime.now()),
            str(user_id),
            user_progress[user_id]["correct"],
            len(questions)
        ])
        user_progress.pop(user_id)
        return

    q = questions[idx]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=opt)] for opt in q["options"]],
        resize_keyboard=True
    )

    await bot.send_message(user_id, f"❓ {q['question']}", reply_markup=keyboard)

    async def timeout():
        await asyncio.sleep(10)
        if user_progress.get(user_id) and user_progress[user_id]["index"] == idx:
            user_progress[user_id]["index"] += 1
            await bot.send_message(user_id, "⏰ Час вийшов!")
            await send_question(user_id)

    asyncio.create_task(timeout())

@dp.message(Command("start"))
async def start_test(message: types.Message):
    user_id = message.from_user.id
    user_progress[user_id] = {"index": 0, "correct": 0}
    await bot.send_message(user_id, "🍽️ Почнемо тест по меню!")
    await send_question(user_id)

@dp.message(F.text)
async def handle_message(message: types.Message):
    user_id = message.from_user.id

    if user_id not in user_progress:
        await bot.send_message(user_id, "Напиши /start щоб розпочати тест.")
        return

    idx = user_progress[user_id]["index"]
    q = questions[idx]

    if message.text == q["answer"]:
        user_progress[user_id]["correct"] += 1
        await bot.send_message(user_id, "✅ Правильно!")
    else:
        await bot.send_message(user_id, f"❌ Неправильно! Правильна відповідь: {q['answer']}")

    user_progress[user_id]["index"] += 1
    await send_question(user_id)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
