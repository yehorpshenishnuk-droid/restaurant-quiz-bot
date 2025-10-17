import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import gspread
import os
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO)

# ==== Конфигурация ====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")

# ==== Авторизация в Google Sheets ====
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("project-telegram-bot-475412-704fc4e68815.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

# ==== Настройка Telegram ====
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ==== Вопросы ====
QUESTIONS = [
    {"q": "🥗 Яка вага Цезаря з куркою?", "options": ["180 г", "200 г", "220 г", "250 г"], "a": "200 г"},
    {"q": "🍛 Яка ціна плову?", "options": ["139 ₴", "149 ₴", "159 ₴", "169 ₴"], "a": "169 ₴"},
]

# ==== Состояния пользователей ====
user_progress = {}


# ==== Отправка вопроса ====
async def send_question(user_id):
    progress = user_progress[user_id]
    if progress["index"] >= len(QUESTIONS):
        await bot.send_message(user_id, f"✅ Тест завершено! Правильних відповідей: {progress['correct']}/{len(QUESTIONS)}")
        sheet.append_row([progress["name"], str(datetime.now()), progress["correct"], len(QUESTIONS)])
        return

    q = QUESTIONS[progress["index"]]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=opt)] for opt in q["options"]],
        resize_keyboard=True
    )

    await bot.send_message(user_id, f"❓ {q['q']}", reply_markup=keyboard)

    # 10 секунд на ответ
    await asyncio.sleep(10)
    if progress["waiting"]:
        progress["waiting"] = False
        await bot.send_message(user_id, "⏰ Час вийшов!")
        progress["index"] += 1
        await send_question(user_id)


# ==== Команда /start ====
@dp.message(Command("start"))
async def start_test(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.full_name

    user_progress[user_id] = {"index": 0, "correct": 0, "waiting": True, "name": name}

    await message.answer("🍽 Почнемо тест по меню!")
    await send_question(user_id)


# ==== Обработка ответов ====
@dp.message()
async def handle_answer(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_progress:
        await message.answer("Напиши /start щоб розпочати тест.")
        return

    progress = user_progress[user_id]
    if not progress["waiting"]:
        return

    q = QUESTIONS[progress["index"]]
    answer = message.text.strip()

    progress["waiting"] = False
    if answer == q["a"]:
        progress["correct"] += 1
        await message.answer("✅ Правильно!")
    else:
        await message.answer(f"❌ Неправильно! Правильна відповідь: {q['a']}")

    progress["index"] += 1
    await send_question(user_id)


# ==== Запуск ====
async def main():
    # сбрасываем старые webhook/polling сессии (решает TelegramConflictError)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook удалён, запускаем polling…")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
