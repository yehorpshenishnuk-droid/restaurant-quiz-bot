import os
import json
import random
import asyncio
import logging
import requests
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from datetime import datetime
from dotenv import load_dotenv

# ------------------ Настройки ------------------
logging.basicConfig(level=logging.INFO)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
POSTER_TOKEN = os.getenv("POSTER_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")

HOT_CATEGORY_IDS = list(map(int, os.getenv("HOT_CATEGORY_IDS", "").split(",")))
COLD_CATEGORY_IDS = list(map(int, os.getenv("COLD_CATEGORY_IDS", "").split(",")))
BAR_CATEGORY_IDS = list(map(int, os.getenv("BAR_CATEGORY_IDS", "").split(",")))

# Google Sheets
try:
    gc = gspread.service_account(filename="/etc/secrets/project-telegram-bot-475412-704fc4e68815.json")
    sheet = gc.open_by_key(SHEET_ID).sheet1
except Exception as e:
    raise RuntimeError(f"❌ Google Sheets ошибка: {e}")

# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ------------------ Poster API ------------------
def get_products_by_category(category_ids):
    all_products = []
    for cat_id in category_ids:
        url = f"https://joinposter.com/api/menu.getProducts?token={POSTER_TOKEN}&category_id={cat_id}"
        try:
            resp = requests.get(url, timeout=10).json()
            if "response" in resp:
                all_products.extend(resp["response"])
        except Exception as e:
            logging.error(f"Ошибка загрузки категории {cat_id}: {e}")
    return all_products

def load_menu():
    hot = get_products_by_category(HOT_CATEGORY_IDS)
    cold = get_products_by_category(COLD_CATEGORY_IDS)
    bar = get_products_by_category(BAR_CATEGORY_IDS)
    return hot + cold + bar

# ------------------ Генерация вопросов ------------------
def generate_questions(products):
    questions = []
    for item in products:
        name = item.get("product_name")
        price = item.get("price")
        weight = item.get("out")
        composition = item.get("ingredients")

        if not name or not price:
            continue

        # Цена
        questions.append({
            "question": f"💰 Скільки коштує '{name}'?",
            "correct": str(price),
            "options": generate_options(str(price))
        })

        # Вага
        if weight:
            questions.append({
                "question": f"⚖️ Яка вага порції '{name}'?",
                "correct": str(weight),
                "options": generate_options(str(weight))
            })

        # Склад
        if composition:
            main_ing = composition.split(",")[0].strip()
            questions.append({
                "question": f"🥗 Що входить до складу '{name}'?",
                "correct": main_ing,
                "options": generate_ingredient_options(main_ing)
            })

    random.shuffle(questions)
    return questions[:300]

def generate_options(correct):
    opts = [correct]
    while len(opts) < 4:
        opts.append(str(random.randint(50, 500)))
    random.shuffle(opts)
    return opts

def generate_ingredient_options(correct):
    fake = ["сіль", "олія", "перець", "томат", "сир", "хліб"]
    opts = [correct] + random.sample(fake, 3)
    random.shuffle(opts)
    return opts

# ------------------ Telegram Bot ------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🍽️ Вітаю! Почнемо тест по меню ресторану!\n\n"
        "📋 Умови тесту:\n"
        "• 15 випадкових питань\n"
        "• 10 секунд на відповідь\n"
        "• 4 варіанти відповідей\n\n"
        "Готовий? Натисни /quiz щоб почати!"
    )

@dp.message(Command("quiz"))
async def start_quiz(message: types.Message):
    await message.answer("📦 Завантажую меню з Poster API...")
    products = load_menu()
    if not products:
        await message.answer("⚠️ Не вдалося отримати меню.")
        return

    questions = generate_questions(products)
    quiz = random.sample(questions, min(15, len(questions)))

    score = 0
    total = len(quiz)
    await message.answer("🚀 Починаємо тест! Удачі!")

    for i, q in enumerate(quiz, start=1):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for opt in q["options"]:
            markup.add(opt)
        await message.answer(f"❓ {i}/{total}\n{q['question']}", reply_markup=markup)
        try:
            ans = await bot.wait_for("message", timeout=10)
            if ans.text == q["correct"]:
                score += 1
                await ans.answer("✅ Правильно!")
            else:
                await ans.answer(f"❌ Неправильно. Вірна відповідь: {q['correct']}")
        except asyncio.TimeoutError:
            await message.answer(f"⏰ Час вийшов! Правильна відповідь: {q['correct']}")

    percent = round((score / total) * 100, 1)
    await message.answer(f"🏁 Тест завершено! Результат: {score}/{total} ({percent}%)")

    try:
        sheet.append_row([datetime.now().isoformat(), message.from_user.full_name, f"{score}/{total}", f"{percent}%"])
    except Exception as e:
        logging.error(f"Помилка запису в Google Sheets: {e}")

# ------------------ Render Heartbeat ------------------
async def heartbeat():
    while True:
        try:
            requests.get("https://api.render.com", timeout=5)
        except:
            pass
        await asyncio.sleep(300)

# ------------------ Main ------------------
async def main():
    asyncio.create_task(heartbeat())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
