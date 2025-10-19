import asyncio
import logging
import random
import gspread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os

# Завантаження змінних оточення
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SHEET_ID") or os.getenv("SPREADSHEET_ID")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not found!")
if not SPREADSHEET_ID:
    raise ValueError("SHEET_ID not found!")

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# FSM States для квізу
class QuizStates(StatesGroup):
    waiting_for_answer = State()

# Ініціалізація
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Підключення до Google Sheets
def get_google_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Шлях до credentials на Render або локально
    creds_path = "/etc/secrets/project-telegram-bot-475412-704fc4e68815.json"
    if not os.path.exists(creds_path):
        creds_path = "creds.json"
    
    logging.info(f"Reading credentials from: {creds_path}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    logging.info("Successfully connected to Google Sheets!")
    return sheet

# Отримання випадкових питань
def get_random_questions(sheet, count=15):
    data = sheet.get_all_records()
    logging.info(f"Found {len(data)} questions in sheet")
    if len(data) < count:
        count = len(data)
    return random.sample(data, count)

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(
        "🍽 Вітаю! Почнемо тест по меню ресторану!\n\n"
        "Я задам тобі 15 випадкових питань.\n"
        "Вибирай правильну відповідь з варіантів.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    try:
        # Завантажуємо питання з Google Sheets
        sheet = get_google_sheet()
        questions = get_random_questions(sheet)
        
        # Зберігаємо дані квізу в state
        await state.update_data(
            questions=questions,
            current_question=0,
            correct_answers=0
        )
        
        # Запускаємо квіз
        await send_question(message, state)
        
    except Exception as e:
        await message.answer(f"❌ Помилка підключення до бази питань:\n{str(e)}")
        logging.error(f"Error loading questions: {e}", exc_info=True)

# Відправка питання
async def send_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions = data['questions']
    current = data['current_question']
    
    # Перевірка чи є ще питання
    if current >= len(questions):
        await finish_quiz(message, state)
        return
    
    # Отримуємо поточне питання
    q = questions[current]
    question_text = f"❓ Питання {current + 1}/{len(questions)}\n\n{q['question']}"
    
    # Створюємо варіанти відповідей
    options = [opt.strip() for opt in q['options'].split(",")]
    
    # Клавіатура з варіантами
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(question_text, reply_markup=keyboard)
    await state.set_state(QuizStates.waiting_for_answer)

# Обробка відповіді
@dp.message(QuizStates.waiting_for_answer, F.text)
async def process_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions = data['questions']
    current = data['current_question']
    correct_count = data['correct_answers']
    
    # Перевірка відповіді
    correct_answer = questions[current]['answer'].strip().lower()
    user_answer = message.text.strip().lower()
    
    if user_answer == correct_answer:
        correct_count += 1
        await message.answer("✅ Правильно!", reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer(
            f"❌ Неправильно!\n\nПравильна відповідь: {questions[current]['answer']}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    # Оновлюємо дані
    await state.update_data(
        current_question=current + 1,
        correct_answers=correct_count
    )
    
    # Невелика затримка перед наступним питанням
    await asyncio.sleep(1)
    
    # Наступне питання
    await send_question(message, state)

# Завершення квізу
async def finish_quiz(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct = data['correct_answers']
    total = len(data['questions'])
    
    percentage = (correct / total) * 100
    
    # Визначаємо оцінку
    if percentage >= 90:
        grade = "🏆 Відмінно!"
    elif percentage >= 70:
        grade = "👍 Добре!"
    elif percentage >= 50:
        grade = "😐 Задовільно"
    else:
        grade = "😔 Потрібно підучити меню"
    
    result_text = (
        f"✅ Тест завершено!\n\n"
        f"📊 Результат: {correct}/{total} правильних відповідей\n"
        f"📈 Відсоток: {percentage:.1f}%\n\n"
        f"{grade}\n\n"
        f"Щоб пройти тест знову, натисни /start"
    )
    
    await message.answer(result_text, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

# Команда /help
@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "📚 Допомога\n\n"
        "Цей бот допоможе тобі вивчити меню ресторану.\n\n"
        "Команди:\n"
        "/start - Почати тест\n"
        "/help - Показати це повідомлення\n"
        "/cancel - Скасувати поточний тест\n\n"
        "Під час тесту просто вибирай правильну відповідь з варіантів."
    )
    await message.answer(help_text)

# Команда /cancel
@dp.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Зараз немає активного тесту.")
        return
    
    await state.clear()
    await message.answer(
        "❌ Тест скасовано.\n\nЩоб почати знову, натисни /start",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обробка невідомих повідомлень під час квізу
@dp.message(QuizStates.waiting_for_answer)
async def unknown_answer(message: types.Message):
    await message.answer(
        "⚠️ Будь ласка, вибери відповідь з варіантів на клавіатурі нижче."
    )

# Обробка всіх інших повідомлень
@dp.message()
async def echo(message: types.Message):
    await message.answer(
        "👋 Привіт! Натисни /start щоб почати тест по меню.\n"
        "Або /help для допомоги."
    )

# Головна функція запуску
async def main():
    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Bot started successfully!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
