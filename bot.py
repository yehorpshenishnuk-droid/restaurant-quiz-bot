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

# ==================== МЕНЮ ДЛЯ ОФІЦІАНТІВ ====================

RESTAURANT_MENU = {
    "Плов який Ви полюбите": {
        "price": 169,
        "weight": "310 г",
        "description": "Плов, приготований у казані за старовинним рецептом з яловичиною та бараниною",
        "category": "Основні страви"
    },
    "Пельмені як мають бути з телятиною": {
        "price": 169,
        "weight": "310 г",
        "description": "Соковиті пельмені з телятиною, домашня технологія",
        "category": "Основні страви"
    },
    "Пельмені з філе курки": {
        "price": 169,
        "weight": "265 г",
        "description": "Соковиті пельмені з куркою, домашня технологія",
        "category": "Основні страви"
    },
    "Фрикадельки з індички у вершковому соусі з картопляним пюре": {
        "price": 219,
        "weight": "300 г",
        "description": "Ніжні фрикадельки з індички у вершковому соусі",
        "category": "Дитяче меню"
    },
    "Телячі щічки з вершковим пюре": {
        "price": 369,
        "weight": "370 г",
        "description": "Телячі щічки томлені 24 години у винно-овочевому соусі",
        "category": "Основні страви"
    },
    "Салат Цезар": {
        "price": 239,
        "weight": "300 г",
        "description": "Курка на грилі, бекон, салат, помідори, пармезан, перепелині яйця",
        "category": "Салати"
    },
    "Грецький салат": {
        "price": 199,
        "weight": "300 г",
        "description": "Помідори, огірки, оливки, фета, болгарський перець",
        "category": "Салати"
    },
    "Теплий салат з телятиною": {
        "price": 229,
        "weight": "260 г",
        "description": "Телятина на грилі, фрілліс, рукола, томати, болгарський перець",
        "category": "Салати"
    },
    "Овочевий салат з горіховою заправкою": {
        "price": 169,
        "weight": "300 г",
        "description": "Помідори, огірки, цибуля маринована, горіховий соус",
        "category": "Салати"
    },
    "Салат з запеченими овочами": {
        "price": 179,
        "weight": "310 г",
        "description": "Запечені баклажани, перець, цибуля, томат",
        "category": "Салати"
    },
    "Салат з хамоном та карамелізованою грушею": {
        "price": 259,
        "weight": "200 г",
        "description": "Хамон, карамелізована груша, Дор Блю, рукола, грецькі горіхи",
        "category": "Салати"
    },
    "Гарячий борщ": {
        "price": 179,
        "weight": "460 г",
        "description": "Український борщ зі сметаною та пампушками",
        "category": "Супи"
    },
    "Суп Вушка": {
        "price": 119,
        "weight": "320 г",
        "description": "Дрібні пельмені зі свининою в курячому бульйоні",
        "category": "Супи"
    },
    "Вершковий грибний крем-суп": {
        "price": 159,
        "weight": "310 г",
        "description": "Крем-суп з печериць на вершках з грінками",
        "category": "Супи"
    },
    "М'ясна солянка": {
        "price": 169,
        "weight": "310 г",
        "description": "М'ясний бульйон з копченостями та ковбасами",
        "category": "Супи"
    },
    "Крем-суп гарбузовий з беконом": {
        "price": 159,
        "weight": "310 г",
        "description": "Мускатний гарбуз з вершками та хрустким беконом",
        "category": "Супи"
    },
    "Картопля Фрі з соусами": {
        "price": 79,
        "weight": "140 г",
        "description": "Хрустка картопля з соусом на вибір",
        "category": "Закуски"
    },
    "Батат фрі з соусом цезар та пармезаном": {
        "price": 139,
        "weight": "155 г",
        "description": "Батат фрі з соусом цезар та пармезаном",
        "category": "Закуски"
    },
    "Стріпси з філе молодої курки": {
        "price": 129,
        "weight": "150 г",
        "description": "Хрустка курка з соусом на вибір",
        "category": "Закуски"
    },
    "Жульєн зі скоринкою Чедер": {
        "price": 139,
        "weight": "150 г",
        "description": "М'ясо птиці, печериці, вершковий соус, Чедер",
        "category": "Закуски"
    },
    "Люля-кебаб з трьома видами м'яса": {
        "price": 189,
        "weight": "260 г",
        "description": "Яловичина, свинина, курка з цибулею та спеціями",
        "category": "Гриль"
    },
    "Філе молодої курки": {
        "price": 249,
        "weight": "360 г",
        "description": "Мариноване філе фермерської курки на грилі",
        "category": "Гриль"
    },
    "Телятина на грилі": {
        "price": 339,
        "weight": "360 г",
        "description": "Соковита телятина, прожарювання Medium",
        "category": "Гриль"
    },
    "Шийна частина свинини": {
        "price": 329,
        "weight": "410 г",
        "description": "Мариноване м'ясо з маринованою цибулею",
        "category": "Гриль"
    },
    "Деруни зі сметаною": {
        "price": 99,
        "weight": "240 г",
        "description": "Хрусткі картопляні оладки зі сметаною",
        "category": "Деруни"
    },
    "Деруни з вершковим соусом та грибами": {
        "price": 119,
        "weight": "230 г",
        "description": "Деруни з грибами, вершковим соусом та пармезаном",
        "category": "Деруни"
    }
}

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

def get_techcard_categories():
    """Знайти ID категорій 'Тех. картки' та 'Напівфабрикати'"""
    categories = get_poster_categories()
    techcard_ids = set()
    
    for cat_id, cat_name in categories.items():
        # Шукаємо категорії за ключовими словами
        cat_name_lower = cat_name.lower()
        if any(keyword in cat_name_lower for keyword in ['тех', 'картк', 'напів', 'фабрикат']):
            techcard_ids.add(cat_id)
            logging.info(f"Found tech card category: {cat_name} (ID: {cat_id})")
    
    return techcard_ids

# ==================== ЗІСТАВЛЕННЯ МЕНЮ З ТЕХ.КАРТКАМИ ====================

def normalize_dish_name(name):
    """Нормалізує назву страви для зіставлення"""
    # Видаляємо вагу, об'єм
    name = re.sub(r',?\s*\d+[\.,]?\d*\s*(мл|л|г|кг)', '', name, flags=re.IGNORECASE)
    # Видаляємо зайві слова
    name = name.lower().strip()
    # Видаляємо розділові знаки
    name = re.sub(r'[^\w\s]', '', name)
    return name

def find_dish_in_techcards(dish_name, techcard_products):
    """Знаходить страву в тех.картках"""
    normalized_dish = normalize_dish_name(dish_name)
    
    for product in techcard_products:
        product_name = product.get('product_name', '')
        normalized_product = normalize_dish_name(product_name)
        
        # Перевіряємо схожість назв
        if normalized_dish in normalized_product or normalized_product in normalized_dish:
            return product
        
        # Перевіряємо по ключових словах
        dish_words = set(normalized_dish.split())
        product_words = set(normalized_product.split())
        common_words = dish_words & product_words
        
        # Якщо більше 60% слів співпадають - це наша страва
        if len(common_words) > 0 and len(dish_words) > 0:
            similarity = len(common_words) / len(dish_words)
            if similarity >= 0.6:
                return product
    
    return None

# ==================== ГЕНЕРАЦІЯ ПИТАНЬ ====================

def generate_questions_from_menu_and_techcards():
    """Генерує питання з меню офіціанта та тех.карток Poster"""
    global QUESTIONS_DB
    
    # Отримуємо продукти з тех.карток
    techcard_cat_ids = get_techcard_categories()
    if not techcard_cat_ids:
        logging.error("No tech card categories found!")
        return
    
    all_products = get_poster_products()
    techcard_products = [p for p in all_products if p.get('category_id') in techcard_cat_ids]
    
    logging.info(f"Found {len(techcard_products)} products in tech cards")
    
    questions = []
    
    # Проходимо по кожній страві з меню офіціанта
    for dish_name, dish_info in RESTAURANT_MENU.items():
        # Знаходимо цю страву в тех.картках
        techcard = find_dish_in_techcards(dish_name, techcard_products)
        
        if not techcard:
            logging.warning(f"Tech card not found for: {dish_name}")
            continue
        
        logging.info(f"✓ Matched: {dish_name} -> {techcard.get('product_name')}")
        
        # Отримуємо інгредієнти з тех.картки
        ingredients_raw = techcard.get('ingredients', [])
        if not isinstance(ingredients_raw, list) or len(ingredients_raw) < 2:
            continue
        
        # Фільтруємо інгредієнти
        valid_ingredients = []
        for ing in ingredients_raw:
            ing_name = ing.get('ingredient_name', '')
            
            if not ing_name or len(ing_name) < 3:
                continue
            
            # Пропускаємо інгредієнти схожі на назву страви
            if ing_name.lower() in dish_name.lower():
                continue
            
            valid_ingredients.append(ing_name)
        
        if len(valid_ingredients) < 2:
            continue
        
        # ПИТАННЯ 1: Що входить в склад страви?
        correct_ingredient = random.choice(valid_ingredients)
        
        # Збираємо неправильні варіанти з ІНШИХ страв
        wrong_ingredients = []
        for other_product in techcard_products:
            if other_product['product_id'] == techcard['product_id']:
                continue
            
            other_ings = other_product.get('ingredients', [])
            if isinstance(other_ings, list):
                for ing in other_ings:
                    ing_name = ing.get('ingredient_name', '')
                    if (ing_name and len(ing_name) >= 3 and 
                        ing_name not in valid_ingredients and 
                        ing_name not in wrong_ingredients):
                        wrong_ingredients.append(ing_name)
        
        if len(wrong_ingredients) >= 3:
            selected_wrong = random.sample(wrong_ingredients, 3)
            options = [correct_ingredient] + selected_wrong
            random.shuffle(options)
            
            questions.append({
                "question": f"Що входить в склад страви '{dish_name}'?",
                "options": options,
                "answer": correct_ingredient,
                "category": "ingredients",
                "dish": dish_name
            })
        
        # ПИТАННЯ 2: Скільки інгредієнтів в страві?
        ingredient_count = len(valid_ingredients)
        wrong_counts = [ingredient_count - 2, ingredient_count - 1, ingredient_count + 1, ingredient_count + 2]
        wrong_counts = [c for c in wrong_counts if c > 0 and c != ingredient_count]
        
        if len(wrong_counts) >= 3:
            selected_wrong_counts = random.sample(wrong_counts, 3)
            options_counts = [str(ingredient_count)] + [str(c) for c in selected_wrong_counts]
            random.shuffle(options_counts)
            
            questions.append({
                "question": f"Скільки основних інгредієнтів в страві '{dish_name}'?",
                "options": options_counts,
                "answer": str(ingredient_count),
                "category": "ingredient_count",
                "dish": dish_name
            })
    
    # Додаємо питання про ЦІНИ з меню
    for dish_name, dish_info in RESTAURANT_MENU.items():
        price = dish_info['price']
        
        # Беремо інші ціни для неправильних варіантів
        other_prices = [info['price'] for name, info in RESTAURANT_MENU.items() if name != dish_name]
        
        if len(other_prices) >= 3:
            wrong_prices = random.sample(other_prices, 3)
            options_prices = [str(price)] + [str(p) for p in wrong_prices]
            random.shuffle(options_prices)
            
            questions.append({
                "question": f"Яка ціна страви '{dish_name}'?",
                "options": [f"{p} ₴" for p in options_prices],
                "answer": f"{price} ₴",
                "category": "price",
                "dish": dish_name
            })
    
    # Додаємо питання про ВАГУ з меню
    for dish_name, dish_info in RESTAURANT_MENU.items():
        weight = dish_info['weight']
        
        # Беремо інші ваги для неправильних варіантів
        other_weights = [info['weight'] for name, info in RESTAURANT_MENU.items() 
                        if name != dish_name and info['weight'] != weight]
        
        if len(other_weights) >= 3:
            wrong_weights = random.sample(other_weights, 3)
            options_weights = [weight] + wrong_weights
            random.shuffle(options_weights)
            
            questions.append({
                "question": f"Яка вага порції '{dish_name}'?",
                "options": options_weights,
                "answer": weight,
                "category": "weight",
                "dish": dish_name
            })
    
    QUESTIONS_DB = questions
    logging.info(f"Generated {len(questions)} questions from menu + tech cards")

def get_random_questions(count=15):
    """Повертає випадкові питання"""
    if len(QUESTIONS_DB) < count:
        return QUESTIONS_DB.copy()
    return random.sample(QUESTIONS_DB, count)

# ==================== GOOGLE SHEETS ====================

def save_result_to_sheet(username, first_name, correct, total, percentage):
    """Зберігає результат в Google Sheets"""
    if not SPREADSHEET_ID:
        logging.warning("SPREADSHEET_ID not configured, skipping save")
        return False
    
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds_data = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not creds_data:
            logging.error("No Google credentials found")
            return False
        
        import json
        creds_dict = json.loads(creds_data)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, username, first_name, correct, total, f"{percentage:.1f}%"]
        sheet.append_row(row)
        
        logging.info(f"Saved result for {username}: {correct}/{total}")
        return True
        
    except Exception as e:
        logging.error(f"Error saving to sheet: {e}")
        return False

# ==================== ХЕНДЛЕРИ ====================

@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "👋 Привіт! Я бот для тестування знань меню.\n\n"
        "Я допоможу тобі вивчити:\n"
        "• Склад страв (з тех.карток)\n"
        "• Ціни страв\n"
        "• Вагу порцій\n"
        "• Інгредієнти\n\n"
        "Натисни /quiz щоб почати тест!\n"
        "Або /help для довідки"
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
    
    options = q['options'].copy()
    random.shuffle(options)
    
    options = [str(opt) for opt in options]
    
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
        result_text += "⚠️ Результати не збережені (Google Sheets не налаштовано)\n\n"
    
    result_text += "Щоб пройти тест знову, натисни /quiz"
    
    await message.answer(result_text, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "📚 Довідка\n\n"
        "Цей бот допоможе тобі вивчити меню ресторану.\n\n"
        "🎯 Типи питань:\n"
        "• Склад страв (з технічних карток)\n"
        "• Ціни страв\n"
        "• Вага порцій\n"
        "• Кількість інгредієнтів\n\n"
        "📱 Команди:\n"
        "/start - Початок роботи\n"
        "/quiz - Почати тест (15 питань)\n"
        "/help - Показати цю довідку\n"
        "/cancel - Скасувати поточний тест\n"
        "/reload - Оновити питання\n"
        "/stats - Показати статистику\n\n"
        "⏱ Умови тесту:\n"
        "• 15 випадкових питань\n"
        "• 10 секунд на кожну відповідь\n"
        "• 4 варіанти відповідей\n\n"
        "Удачі! 🍀"
    )
    await message.answer(help_text)

@dp.message(Command("reload"))
async def reload_command(message: types.Message):
    await message.answer("🔄 Оновлюю питання...")
    generate_questions_from_menu_and_techcards()
    await message.answer(f"✅ Завантажено {len(QUESTIONS_DB)} питань!")

@dp.message(Command("stats"))
async def stats_command(message: types.Message):
    if not QUESTIONS_DB:
        await message.answer("⚠️ База питань порожня")
        return
    
    # Підрахунок статистики
    categories = {}
    for q in QUESTIONS_DB:
        cat = q.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
    
    stats_text = f"📊 Статистика питань:\n\n"
    stats_text += f"Всього питань: {len(QUESTIONS_DB)}\n\n"
    
    cat_names = {
        'ingredients': '🥘 Склад страв',
        'ingredient_count': '🔢 Кількість інгредієнтів',
        'price': '💰 Ціни',
        'weight': '⚖️ Вага порцій'
    }
    
    for cat, count in categories.items():
        cat_name = cat_names.get(cat, cat)
        stats_text += f"{cat_name}: {count}\n"
    
    await message.answer(stats_text)

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
    logging.info("Loading menu and tech cards from Poster...")
    generate_questions_from_menu_and_techcards()
    
    if not QUESTIONS_DB:
        logging.error("Failed to generate questions!")
    
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
