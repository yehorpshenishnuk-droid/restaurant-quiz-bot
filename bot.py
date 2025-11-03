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

# ==================== МЕНЮ РЕСТОРАНУ ====================
# Тільки назва, ціна та вага. Склад береться з Poster API (тех.картки)

RESTAURANT_MENU = {
    "Плов який Ви полюбите": {"price": 169, "weight": "310 г"},
    "Пельмені як мають бути з телятиною": {"price": 169, "weight": "310 г"},
    "Пельмені з філе курки": {"price": 169, "weight": "265 г"},
    "Фрикадельки з індички у вершковому соусі з картопляним пюре": {"price": 219, "weight": "300 г"},
    "Телячі щічки з вершковим пюре": {"price": 369, "weight": "370 г"},
    "Салат Цезар": {"price": 239, "weight": "300 г"},
    "Грецький салат": {"price": 199, "weight": "300 г"},
    "Теплий салат з телятиною": {"price": 229, "weight": "260 г"},
    "Овочевий салат з горіховою заправкою": {"price": 169, "weight": "300 г"},
    "Салат з запеченими овочами": {"price": 179, "weight": "310 г"},
    "Пісний овочевий з горіховою заправкою": {"price": 169, "weight": "280 г"},
    "Легкий салат з запеченим гарбузом": {"price": 199, "weight": "310 г"},
    "Салат з хамоном та карамелізованою грушею": {"price": 259, "weight": "200 г"},
    "Мікс салату з куркою сувід": {"price": 199, "weight": "245 г"},
    "Піде з моцарелою, томатами та песто": {"price": 289, "weight": "600 г"},
    "Сирне піде з інжиром та фісташкою": {"price": 289, "weight": "450 г"},
    "Піде з сиром та часниковим соусом": {"price": 259, "weight": "505 г"},
    "Піде з грушею і чотирма сирами": {"price": 329, "weight": "530 г"},
    "Піде з телятиною": {"price": 279, "weight": "550 г"},
    "Піде з куркою та томатами": {"price": 259, "weight": "550 г"},
    "Гарячий борщ": {"price": 179, "weight": "460 г"},
    "Гарячий борщ з сальцем, хріном та гірчицею": {"price": 269, "weight": "540 г"},
    "Суп Вушка": {"price": 119, "weight": "320 г"},
    "Вершковий грибний крем-суп": {"price": 159, "weight": "310 г"},
    "М'ясна солянка": {"price": 169, "weight": "310 г"},
    "Крем-суп гарбузовий з беконом": {"price": 159, "weight": "310 г"},
    "Картопля Фрі з соусами": {"price": 79, "weight": "140 г"},
    "Батат фрі з соусом цезар та пармезаном": {"price": 139, "weight": "155 г"},
    "Стріпси з філе молодої курки": {"price": 129, "weight": "150 г"},
    "Сирні хрусткі палички": {"price": 199, "weight": "220 г"},
    "Картопля селянка": {"price": 99, "weight": "265 г"},
    "Картопля по-селянськи з грибами": {"price": 159, "weight": "390 г"},
    "Сирна тарілка": {"price": 265, "weight": "215 г"},
    "Бадриджани з крем сиром та волоським горіхом": {"price": 189, "weight": "200 г"},
    "Оливковий мікс": {"price": 129, "weight": "100 г"},
    "Жульєн зі скоринкою Чедер": {"price": 139, "weight": "150 г"},
    "Манти з сиром та зеленню": {"price": 34, "weight": "1 шт"},
    "Манти з яловичиною (класичні)": {"price": 34, "weight": "1 шт"},
    "Манти з яловичиною та свининою": {"price": 34, "weight": "1 шт"},
    "Деруни зі сметаною": {"price": 99, "weight": "240 г"},
    "Деруни з вершковим соусом та грибами": {"price": 119, "weight": "230 г"},
    "Люля-кебаб з трьома видами м'яса": {"price": 189, "weight": "260 г"},
    "Люля-кебаб з сиром та трьома видами м'яса": {"price": 189, "weight": "260 г"},
    "Реберця в медово-гірчичному соусі": {"price": 249, "weight": "410 г"},
    "Ніжне куряче стегно гриль": {"price": 239, "weight": "360 г"},
    "Філе молодої курки": {"price": 249, "weight": "360 г"},
    "Телятина на грилі": {"price": 339, "weight": "360 г"},
    "Шийна частина свинини": {"price": 329, "weight": "410 г"},
    "Млинці з куркою та грибами": {"price": 129, "weight": "230 г"},
    "Млинці з куркою": {"price": 129, "weight": "230 г"},
    "Млинці солодкі з ванільним сиром": {"price": 129, "weight": "230 г"},
    "Сирники": {"price": 119, "weight": "190 г"},
    "Гарбузовий тост з лісовими лисичками та яйцем пашот": {"price": 209, "weight": "195 г"},
    "Сніданок Фрітата": {"price": 169, "weight": "330 г"},
    "Сніданок Бюргер": {"price": 189, "weight": "400 г"},
    "Сніданок Субмарина": {"price": 209, "weight": "440 г"},
    "Сніданок Шакшука": {"price": 159, "weight": "340 г"},
    "Сніданок Як вдома": {"price": 179, "weight": "320 г"},
    "Ніжне крем-брюле": {"price": 129, "weight": "160 г"},
    "Шоколадний фондан": {"price": 169, "weight": "140 г"},
    "Чизкейк LA": {"price": 139, "weight": "165 г"},
    "Вафельний десерт з натяком на рафаело": {"price": 99, "weight": "115 г"},
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
        cat_name_lower = cat_name.lower()
        # Шукаємо категорії за ключовими словами
        if any(keyword in cat_name_lower for keyword in ['тех', 'картк', 'напів', 'фабрикат']):
            techcard_ids.add(cat_id)
            logging.info(f"Found tech card category: {cat_name} (ID: {cat_id})")
    
    return techcard_ids

# ==================== ЗІСТАВЛЕННЯ СТРАВ ====================

def normalize_dish_name(name):
    """Нормалізує назву страви для зіставлення"""
    # Видаляємо вагу, об'єм
    name = re.sub(r',?\s*\d+[\.,]?\d*\s*(мл|л|г|кг)', '', name, flags=re.IGNORECASE)
    # Видаляємо зайві слова
    name = name.lower().strip()
    # Видаляємо розділові знаки
    name = re.sub(r'[^\wа-яії\s]', '', name, flags=re.UNICODE)
    # Видаляємо зайві пробіли
    name = ' '.join(name.split())
    return name

def find_dish_in_techcards(dish_name, techcard_products):
    """Знаходить страву з меню в тех.картках Poster"""
    normalized_dish = normalize_dish_name(dish_name)
    dish_words = set(normalized_dish.split())
    
    best_match = None
    best_score = 0
    
    for product in techcard_products:
        product_name = product.get('product_name', '')
        normalized_product = normalize_dish_name(product_name)
        product_words = set(normalized_product.split())
        
        # Точне співпадіння
        if normalized_dish == normalized_product:
            return product
        
        # Один містить інший
        if normalized_dish in normalized_product or normalized_product in normalized_dish:
            return product
        
        # Рахуємо схожість по словам
        if len(dish_words) > 0 and len(product_words) > 0:
            common_words = dish_words & product_words
            similarity = len(common_words) / max(len(dish_words), len(product_words))
            
            if similarity > best_score:
                best_score = similarity
                best_match = product
    
    # Повертаємо найкраще співпадіння якщо схожість більше 40%
    if best_score >= 0.4:
        return best_match
    
    return None

# ==================== ГЕНЕРАЦІЯ ПИТАНЬ ====================

def generate_questions_from_menu_and_techcards():
    """Генерує питання з меню (ціна, вага) та тех.карток (склад)"""
    global QUESTIONS_DB
    
    # Отримуємо тех.картки з Poster
    techcard_cat_ids = get_techcard_categories()
    
    if not techcard_cat_ids:
        logging.warning("No tech card categories found! Questions will only be about price/weight")
    
    all_products = get_poster_products()
    techcard_products = [p for p in all_products if p.get('category_id') in techcard_cat_ids]
    
    logging.info(f"Found {len(techcard_products)} products in tech cards")
    
    questions = []
    matched_dishes = 0
    
    # Проходимо по кожній страві з меню
    for dish_name, dish_info in RESTAURANT_MENU.items():
        price = dish_info['price']
        weight = dish_info['weight']
        
        # ПИТАННЯ ПРО ЦІНУ
        other_prices = [info['price'] for name, info in RESTAURANT_MENU.items() if name != dish_name]
        if len(other_prices) >= 3:
            # Вибираємо унікальні ціни
            unique_prices = list(set(other_prices))
            if len(unique_prices) >= 3:
                wrong_prices = random.sample(unique_prices, min(3, len(unique_prices)))
                options = [f"{price} ₴"] + [f"{p} ₴" for p in wrong_prices if p != price][:3]
                
                if len(options) == 4:
                    random.shuffle(options)
                    questions.append({
                        "question": f"Яка ціна страви '{dish_name}'?",
                        "options": options,
                        "answer": f"{price} ₴",
                        "category": "price",
                        "dish": dish_name
                    })
        
        # ПИТАННЯ ПРО ВАГУ
        other_weights = [info['weight'] for name, info in RESTAURANT_MENU.items() 
                        if name != dish_name and info['weight'] != weight and info['weight'] != "не вказано"]
        
        if len(other_weights) >= 3 and weight != "не вказано":
            unique_weights = list(set(other_weights))
            if len(unique_weights) >= 3:
                wrong_weights = random.sample(unique_weights, min(3, len(unique_weights)))
                options = [weight] + wrong_weights[:3]
                
                if len(options) == 4:
                    random.shuffle(options)
                    questions.append({
                        "question": f"Яка вага порції '{dish_name}'?",
                        "options": options,
                        "answer": weight,
                        "category": "weight",
                        "dish": dish_name
                    })
        
        # ПИТАННЯ ПРО СКЛАД (з тех.карток)
        if not techcard_products:
            continue
        
        techcard = find_dish_in_techcards(dish_name, techcard_products)
        
        if not techcard:
            continue
        
        matched_dishes += 1
        logging.info(f"✓ Matched: {dish_name} → {techcard.get('product_name')}")
        
        # Отримуємо інгредієнти
        ingredients_raw = techcard.get('ingredients', [])
        if not isinstance(ingredients_raw, list) or len(ingredients_raw) < 2:
            continue
        
        # Фільтруємо інгредієнти
        valid_ingredients = []
        dish_name_lower = dish_name.lower()
        
        for ing in ingredients_raw:
            ing_name = ing.get('ingredient_name', '').strip()
            
            if not ing_name or len(ing_name) < 3:
                continue
            
            # Пропускаємо інгредієнти схожі на назву страви
            if ing_name.lower() in dish_name_lower:
                continue
            
            valid_ingredients.append(ing_name)
        
        if len(valid_ingredients) < 2:
            continue
        
        # ПИТАННЯ: Що входить в склад?
        correct_ingredient = random.choice(valid_ingredients)
        
        # Збираємо неправильні варіанти з інших страв
        wrong_ingredients = []
        for other_product in techcard_products:
            if other_product['product_id'] == techcard['product_id']:
                continue
            
            other_ings = other_product.get('ingredients', [])
            if isinstance(other_ings, list):
                for ing in other_ings:
                    ing_name = ing.get('ingredient_name', '').strip()
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
    
    QUESTIONS_DB = questions
    logging.info(f"✅ Generated {len(questions)} questions")
    logging.info(f"📊 Matched {matched_dishes}/{len(RESTAURANT_MENU)} dishes with tech cards")
    
    # Статистика
    stats = {}
    for q in questions:
        cat = q['category']
        stats[cat] = stats.get(cat, 0) + 1
    
    for cat, count in stats.items():
        logging.info(f"   {cat}: {count} questions")

def get_random_questions(count=15):
    """Повертає випадкові питання"""
    if len(QUESTIONS_DB) < count:
        return QUESTIONS_DB.copy()
    return random.sample(QUESTIONS_DB, count)

# ==================== GOOGLE SHEETS ====================

def save_result_to_sheet(username, first_name, correct, total, percentage):
    """Зберігає результат в Google Sheets"""
    if not SPREADSHEET_ID:
        logging.warning("SPREADSHEET_ID not configured")
        return False
    
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds_data = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not creds_data:
            logging.error("No Google credentials")
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
        f"📚 У мене {len(RESTAURANT_MENU)} страв в базі\n\n"
        "Я допоможу тобі вивчити:\n"
        "• Склад страв (з технічних карток)\n"
        "• Ціни страв\n"
        "• Вагу порцій\n\n"
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
    
    result_text += "Щоб пройти тест знову, натисни /quiz"
    
    await message.answer(result_text, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "📚 Довідка\n\n"
        "Цей бот допоможе тобі вивчити меню ресторану.\n\n"
        "🎯 Типи питань:\n"
        "• Склад страв (з технічних карток Poster)\n"
        "• Ціни страв\n"
        "• Вага порцій\n\n"
        "📱 Команди:\n"
        "/start - Початок роботи\n"
        "/quiz - Почати тест (15 питань)\n"
        "/help - Показати цю довідку\n"
        "/cancel - Скасувати поточний тест\n"
        "/reload - Оновити питання з Poster\n"
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
    await message.answer("🔄 Оновлюю питання з Poster...")
    generate_questions_from_menu_and_techcards()
    
    stats = {}
    for q in QUESTIONS_DB:
        cat = q['category']
        stats[cat] = stats.get(cat, 0) + 1
    
    result = f"✅ Завантажено {len(QUESTIONS_DB)} питань!\n\n"
    result += "📊 Розподіл:\n"
    
    cat_names = {
        'ingredients': '🥘 Склад',
        'price': '💰 Ціна',
        'weight': '⚖️ Вага'
    }
    
    for cat, count in stats.items():
        cat_name = cat_names.get(cat, cat)
        result += f"{cat_name}: {count}\n"
    
    await message.answer(result)

@dp.message(Command("stats"))
async def stats_command(message: types.Message):
    if not QUESTIONS_DB:
        await message.answer("⚠️ База питань порожня")
        return
    
    stats = {}
    for q in QUESTIONS_DB:
        cat = q.get('category', 'unknown')
        stats[cat] = stats.get(cat, 0) + 1
    
    stats_text = f"📊 Статистика:\n\n"
    stats_text += f"📚 Меню: {len(RESTAURANT_MENU)} страв\n"
    stats_text += f"❓ Питань: {len(QUESTIONS_DB)}\n\n"
    
    cat_names = {
        'ingredients': '🥘 Склад страв',
        'price': '💰 Ціни',
        'weight': '⚖️ Вага'
    }
    
    for cat, count in stats.items():
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
        f"📚 У базі {len(RESTAURANT_MENU)} страв\n\n"
        "Натисни /quiz щоб почати тест\n"
        "Або /help для довідки"
    )

# ==================== ЗАПУСК ====================

async def main():
    logging.info("🚀 Starting bot...")
    logging.info(f"📚 Menu: {len(RESTAURANT_MENU)} dishes")
    logging.info("🔄 Loading questions from Poster...")
    
    generate_questions_from_menu_and_techcards()
    
    if not QUESTIONS_DB:
        logging.warning("⚠️ No questions generated!")
    
    bot = Bot(token=TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Bot started successfully!")
    logging.info(f"❓ Total questions: {len(QUESTIONS_DB)}")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
