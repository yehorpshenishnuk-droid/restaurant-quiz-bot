import asyncio
import logging
import random
import re
import gspread
import requests
from datetime import datetime
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
POSTER_TOKEN = os.getenv("POSTER_TOKEN")
POSTER_ACCOUNT = os.getenv("POSTER_ACCOUNT", "poka-net3")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not found!")
if not SPREADSHEET_ID:
    raise ValueError("SHEET_ID not found!")
if not POSTER_TOKEN:
    raise ValueError("POSTER_TOKEN not found!")

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

# Глобальна база питань
QUESTIONS_DB = []

# ==================== POSTER API ====================

def get_poster_categories():
    """Отримати всі категорії з Poster"""
    url = f"https://{POSTER_ACCOUNT}.joinposter.com/api/menu.getCategories"
    params = {"token": POSTER_TOKEN}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("response"):
            categories = {cat['category_id']: cat['category_name'] for cat in data['response']}
            logging.info(f"Loaded {len(categories)} categories from Poster")
            return categories
        return {}
    except Exception as e:
        logging.error(f"Error loading categories: {e}")
        return {}

def get_poster_products():
    """Отримати всі продукти з Poster"""
    url = f"https://{POSTER_ACCOUNT}.joinposter.com/api/menu.getProducts"
    params = {"token": POSTER_TOKEN}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("response"):
            products = data['response']
            logging.info(f"Loaded {len(products)} products from Poster")
            return products
        return []
    except Exception as e:
        logging.error(f"Error loading products: {e}")
        return []

# ==================== ГЕНЕРАЦІЯ ПИТАНЬ ====================

def generate_questions_from_poster():
    """Генерує питання на основі меню з Poster"""
    global QUESTIONS_DB
    
    categories = get_poster_categories()
    products = get_poster_products()
    
    if not products:
        logging.error("No products loaded from Poster!")
        return
    
    questions = []
    
    # ID категорій бару (ТІЛЬКИ КОКТЕЙЛІ)
    bar_category_ids = {34}  # Коктейлі
    
    # Генеруємо різні типи питань
    for product in products:
        product_name = product.get('product_name', '')
        category_id = product.get('category_id')
        
        # ФІЛЬТРУЄМО: Пропускаємо порожні назви
        if not product_name or len(product_name.strip()) < 2:
            continue
        
        # Пропускаємо продукти що починаються з + (це доплати/додатки)
        if product_name.strip().startswith('+'):
            continue
        
        # ВАЖЛИВО: Очищуємо назву від ваги/об'єму для ВСІХ питань
        clean_name = re.sub(r',?\s*\d+[\.,]?\d*\s*(мл|л|г|кг)', '', product_name, flags=re.IGNORECASE)
        clean_name = clean_name.strip().rstrip(',').strip()
        
        # Якщо після очищення назва дуже коротка - пропускаємо
        if len(clean_name) < 3:
            continue
        
        # КРИТИЧНО: Фільтруємо непотрібні продукти (соуси, хліб, сіки і т.д.)
        skip_products = [
            'соус', 'хліб', 'паста', 'булка', 'грінки', 'пампушки',
            'сік', 'морс', 'лимонад', 'компот', 'узвар', 'вода',
            'вино', 'пиво', 'віскі', 'коньяк', 'лікер', 'горілка', 
            'ром', 'джин', 'текіла', 'бренді', 'шампанське', 'просекко'
        ]
        should_skip = False
        for skip_word in skip_products:
            if skip_word in clean_name.lower():
                should_skip = True
                break
        
        if should_skip:
            continue
        
        # Визначаємо чи це бар чи кухня
        is_bar = category_id in bar_category_ids
        
        # ДЛЯ БАРУ: тільки коктейлі (категорія 34)
        if is_bar and category_id != 34:
            continue  # Пропускаємо все крім коктейлів
        
        # Ціна
        price_raw = product.get('price', 0)
        if isinstance(price_raw, dict):
            price = 0
        else:
            try:
                price = float(price_raw) / 100
            except (ValueError, TypeError):
                price = 0
        
        weight = product.get('out', '')
        
        # Інгредієнти
        ingredients_raw = product.get('ingredients', [])
        if isinstance(ingredients_raw, list):
            ingredients = ingredients_raw
        else:
            ingredients = []
        
        # 1. ПИТАННЯ ПРО ВАГУ (40% питань)
        if weight:
            # Конвертуємо вагу в строку
            weight_str = str(weight)
            
            # Беремо інші продукти для неправильних варіантів
            other_weights = [str(p.get('out', '')) for p in products if p.get('out') and p['product_id'] != product['product_id']]
            if len(other_weights) >= 3:
                # Вибираємо тільки унікальні варіанти
                wrong_weights = []
                for w in other_weights:
                    if w != weight_str and w not in wrong_weights:
                        wrong_weights.append(w)
                    if len(wrong_weights) == 3:
                        break
                
                if len(wrong_weights) == 3:
                    options = [weight_str] + wrong_weights
                    random.shuffle(options)
                    
                    questions.append({
                        "question": f"Яка вага/об'єм страви '{clean_name}'?",
                        "options": options,
                        "answer": weight_str,
                        "category": "weight",
                        "category_id": category_id
                    })
        
        # 2. ПИТАННЯ ПРО СКЛАД/ІНГРЕДІЄНТИ (40% питань)
        if ingredients and len(ingredients) > 0:
            # Пропускаємо супи, борщі - там занадто багато інгредієнтів
            skip_dishes = ['борщ', 'суп', 'солянка', 'крем-суп']
            should_skip_dish = False
            for skip_word in skip_dishes:
                if skip_word in clean_name.lower():
                    should_skip_dish = True
                    break
            
            if should_skip_dish:
                continue
            
            # Перевіряємо що є нормальні інгредієнти (мінімум 2)
            valid_ingredient_names = []
            for ing in ingredients:
                ing_name = ing.get('ingredient_name', '')
                
                if not ing_name or len(ing_name) < 3:
                    continue
                
                # Фільтруємо інгредієнти які схожі на назву страви
                ing_words = set(ing_name.lower().split())
                name_words = set(clean_name.lower().split())
                
                if len(ing_words) > 0:
                    common_words = ing_words & name_words
                    similarity = len(common_words) / len(ing_words)
                    
                    if similarity > 0.5:
                        continue
                
                if ing_name.lower() in clean_name.lower():
                    continue
                
                valid_ingredient_names.append(ing_name)
            
            # Якщо менше 2 інгредієнтів - пропускаємо
            if len(valid_ingredient_names) < 2:
                continue
            
            # Вибираємо випадковий інгредієнт
            real_ingredient = random.choice(valid_ingredient_names)
            
            # КРИТИЧНО: Збираємо інгредієнти ТІЛЬКИ З ТОГО Ж ТИПУ
            # Для бару - тільки з коктейлів (категорія 34)
            # Для кухні - тільки з кухні (всі крім 34)
            same_type_ingredients = set()
            
            for p in products:
                p_category = p.get('category_id')
                p_name = p.get('product_name', '')
                
                # Для бару: беремо інгредієнти ТІЛЬКИ з коктейлів (34)
                # Для кухні: беремо інгредієнти з усіх категорій КРІМ 34
                if is_bar:
                    # Якщо це бар - беремо тільки з категорії 34
                    if p_category != 34:
                        continue
                else:
                    # Якщо це кухня - беремо з усіх крім 34
                    if p_category == 34:
                        continue
                
                if isinstance(p.get('ingredients'), list):
                    for ing in p['ingredients']:
                        ing_name = ing.get('ingredient_name', '')
                        if ing_name and ing_name != real_ingredient and len(ing_name) > 2:
                            same_type_ingredients.add(ing_name)
            
            # Видаляємо правильну відповідь зі списку
            same_type_ingredients.discard(real_ingredient)
            
            if len(same_type_ingredients) >= 3:
                wrong_ingredients = random.sample(list(same_type_ingredients), 3)
                options = [real_ingredient] + wrong_ingredients
                random.shuffle(options)
                
                questions.append({
                    "question": f"Який інгредієнт входить до складу '{clean_name}'?",
                    "options": options,
                    "answer": real_ingredient,
                    "category": "ingredients",
                    "category_id": category_id
                })
        
        # 3. ПИТАННЯ ПРО ЦІНУ (20% питань) - менше ніж раніше
        if price > 0 and random.random() < 0.5:  # Генеруємо тільки для 50% страв
            # Створюємо правдоподібні неправильні ціни
            wrong_prices = [
                f"{int(price * 0.8)}₴",
                f"{int(price * 1.2)}₴",
                f"{int(price * 1.5)}₴"
            ]
            correct_price = f"{int(price)}₴"
            options = [correct_price] + wrong_prices
            random.shuffle(options)
            
            questions.append({
                "question": f"Скільки коштує '{clean_name}'?",
                "options": options,
                "answer": correct_price,
                "category": "price",
                "category_id": category_id
            })
    
    QUESTIONS_DB = questions
    logging.info(f"Generated {len(QUESTIONS_DB)} questions from Poster menu")

# ==================== GOOGLE SHEETS ====================

def get_google_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_path = "/etc/secrets/project-telegram-bot-475412-704fc4e68815.json"
    if not os.path.exists(creds_path):
        creds_path = "creds.json"
    
    logging.info(f"Reading credentials from: {creds_path}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    logging.info("Successfully connected to Google Sheets!")
    return sheet

def save_result_to_sheet(username, first_name, correct, total, percentage):
    try:
        sheet = get_google_sheet()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display_name = f"{first_name} (@{username})" if username else first_name
        
        sheet.append_row([now, display_name, f"{correct}/{total}", f"{percentage:.1f}%"])
        logging.info(f"Result saved for {display_name}: {correct}/{total} ({percentage:.1f}%)")
        return True
    except Exception as e:
        logging.error(f"Error saving to sheet: {e}")
        return False

# ==================== КВІЗ ====================

# Отримання випадкових питань з балансом між категоріями
def get_random_questions(count=15):
    if len(QUESTIONS_DB) < count:
        count = len(QUESTIONS_DB)
    
    # Розділяємо питання на БАР (коктейлі) та КУХНЮ
    bar_category_ids = {34}  # Тільки коктейлі
    
    bar_questions = [q for q in QUESTIONS_DB if q.get('category_id') in bar_category_ids]
    kitchen_questions = [q for q in QUESTIONS_DB if q.get('category_id') not in bar_category_ids]
    
    # Беремо 3 питання з бару та 12 з кухні
    selected_questions = []
    
    # 3 питання про бар
    if len(bar_questions) >= 3:
        selected_questions.extend(random.sample(bar_questions, 3))
    else:
        selected_questions.extend(bar_questions)
    
    # 12 питань про кухню (або скільки залишилось)
    remaining = count - len(selected_questions)
    if len(kitchen_questions) >= remaining:
        selected_questions.extend(random.sample(kitchen_questions, remaining))
    else:
        selected_questions.extend(kitchen_questions)
        # Якщо не вистачає, додаємо з бару
        still_needed = count - len(selected_questions)
        if still_needed > 0 and len(bar_questions) > 3:
            selected_questions.extend(random.sample([q for q in bar_questions if q not in selected_questions], min(still_needed, len(bar_questions) - 3)))
    
    # Перемішуємо питання
    random.shuffle(selected_questions)
    
    return selected_questions

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(
        "🍽 Вітаю! Почнемо тест по меню ресторану!\n\n"
        "📋 Умови тесту:\n"
        "• 15 випадкових питань\n"
        "• 10 секунд на відповідь\n"
        "• 4 варіанти відповідей\n"
        "• Вибирай відповідь з варіантів\n\n"
        "Готовий? Натисни /quiz щоб почати!",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(Command("quiz"))
async def quiz_command(message: types.Message, state: FSMContext):
    if not QUESTIONS_DB:
        await message.answer("⚠️ База питань ще завантажується. Спробуй за хвилину!")
        return
    
    questions = get_random_questions(15)
    
    await state.update_data(
        questions=questions,
        current_question=0,
        correct_answers=0,
        username=message.from_user.username or "Unknown",
        first_name=message.from_user.first_name or "User"
    )
    
    await message.answer("🚀 Починаємо тест! Удачі!")
    await asyncio.sleep(1)
    
    await send_question(message, state)

async def send_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions = data['questions']
    current = data['current_question']
    
    if current >= len(questions):
        await finish_quiz(message, state)
        return
    
    q = questions[current]
    question_text = f"❓ Питання {current + 1}/{len(questions)}\n\n{q['question']}"
    
    # ВАЖЛИВО: Перемішуємо варіанти відповідей щоразу!
    options = q['options'].copy()
    random.shuffle(options)
    
    # КРИТИЧНО: Конвертуємо всі варіанти в строки для KeyboardButton
    options = [str(opt) for opt in options]
    
    # Клавіатура з 4 варіантами відповідей (по 2 в ряд)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=options[0]), types.KeyboardButton(text=options[1])],
            [types.KeyboardButton(text=options[2]), types.KeyboardButton(text=options[3])]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(question_text, reply_markup=keyboard)
    await message.answer("⏱ У тебе 10 секунд!")
    
    await state.update_data(question_start_time=asyncio.get_event_loop().time())
    await state.set_state(QuizStates.waiting_for_answer)
    
    asyncio.create_task(question_timer(message, state, current))

async def question_timer(message: types.Message, state: FSMContext, question_number: int):
    await asyncio.sleep(10)
    
    data = await state.get_data()
    current_state = await state.get_state()
    
    if (current_state == QuizStates.waiting_for_answer and 
        data.get('current_question') == question_number):
        
        await message.answer(
            "⏰ Час вийшов!\n"
            f"Правильна відповідь: {data['questions'][question_number]['answer']}",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        await state.update_data(current_question=question_number + 1)
        await asyncio.sleep(1.5)
        await send_question(message, state)

@dp.message(QuizStates.waiting_for_answer, F.text)
async def process_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions = data['questions']
    current = data['current_question']
    correct_count = data['correct_answers']
    
    question_start = data.get('question_start_time', 0)
    elapsed_time = asyncio.get_event_loop().time() - question_start
    
    if elapsed_time > 10:
        return
    
    # ВАЖЛИВО: Конвертуємо обидві відповіді в строки та нижній регістр
    correct_answer = str(questions[current]['answer']).strip().lower()
    user_answer = str(message.text).strip().lower()
    
    if user_answer == correct_answer:
        correct_count += 1
        await message.answer("✅ Правильно!", reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer(
            f"❌ Неправильно!\n\nПравильна відповідь: {questions[current]['answer']}",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.update_data(
        current_question=current + 1,
        correct_answers=correct_count
    )
    
    await asyncio.sleep(1.5)
    await send_question(message, state)

async def finish_quiz(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct = data['correct_answers']
    total = len(data['questions'])
    username = data['username']
    first_name = data['first_name']
    
    percentage = (correct / total) * 100
    
    if percentage >= 90:
        grade = "🏆 Відмінно!"
        emoji = "🎉"
    elif percentage >= 70:
        grade = "👍 Добре!"
        emoji = "😊"
    elif percentage >= 50:
        grade = "😐 Задовільно"
        emoji = "🤔"
    else:
        grade = "😔 Потрібно підучити меню"
        emoji = "📚"
    
    result_text = (
        f"{emoji} Тест завершено!\n\n"
        f"📊 Результат: {correct}/{total} правильних відповідей\n"
        f"📈 Відсоток: {percentage:.1f}%\n\n"
        f"{grade}\n\n"
    )
    
    saved = save_result_to_sheet(username, first_name, correct, total, percentage)
    
    if saved:
        result_text += "✅ Результат збережено!\n\n"
    else:
        result_text += "⚠️ Помилка збереження результату\n\n"
    
    result_text += "Щоб пройти тест знову, натисни /quiz"
    
    await message.answer(result_text, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "📚 Довідка\n\n"
        "Цей бот допоможе тобі вивчити меню ресторану.\n\n"
        "🎯 Команди:\n"
        "/start - Початок роботи\n"
        "/quiz - Почати тест (15 питань)\n"
        "/help - Показати цю довідку\n"
        "/cancel - Скасувати поточний тест\n"
        "/reload - Оновити питання з Poster\n\n"
        "⏱ Умови тесту:\n"
        "• 15 випадкових питань\n"
        "• 10 секунд на кожну відповідь\n"
        "• 4 варіанти відповідей\n"
        "• Результати зберігаються автоматично\n\n"
        "Удачі! 🍀"
    )
    await message.answer(help_text)

@dp.message(Command("reload"))
async def reload_command(message: types.Message):
    await message.answer("🔄 Оновлюю питання з Poster...")
    generate_questions_from_poster()
    await message.answer(f"✅ Завантажено {len(QUESTIONS_DB)} питань!")

@dp.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Зараз немає активного тесту.")
        return
    
    await state.clear()
    await message.answer(
        "❌ Тест скасовано.\n\nЩоб почати знову, натисни /quiz",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(QuizStates.waiting_for_answer)
async def unknown_answer(message: types.Message):
    await message.answer(
        "⚠️ Будь ласка, вибери відповідь з варіантів на клавіатурі."
    )

@dp.message()
async def echo(message: types.Message):
    await message.answer(
        "👋 Привіт! Я бот для тестування знань меню.\n\n"
        "Натисни /quiz щоб почати тест\n"
        "Або /help для довідки"
    )

# ==================== ЗАПУСК ====================

async def main():
    logging.info("Loading menu from Poster...")
    generate_questions_from_poster()
    
    if not QUESTIONS_DB:
        logging.error("Failed to load questions from Poster!")
    
    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Bot started successfully!")
    logging.info(f"📚 Loaded {len(QUESTIONS_DB)} questions")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
