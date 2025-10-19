import asyncio
import logging
import random
import gspread
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

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not found!")
if not SPREADSHEET_ID:
    raise ValueError("SHEET_ID not found!")

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# БАЗА ПИТАНЬ З МЕНЮ РЕСТОРАНУ
QUESTIONS_DB = [
    # САЛАТИ - ціни
    {"question": "Скільки коштує салат Цезар?", "options": ["199₴", "239₴", "269₴"], "answer": "239₴", "category": "salad"},
    {"question": "Скільки коштує Грецький салат?", "options": ["169₴", "199₴", "229₴"], "answer": "199₴", "category": "salad"},
    {"question": "Скільки коштує Теплий салат з телятиною?", "options": ["199₴", "229₴", "259₴"], "answer": "229₴", "category": "salad"},
    {"question": "Скільки коштує салат з хамоном та карамелізованою грушею?", "options": ["229₴", "259₴", "289₴"], "answer": "259₴", "category": "salad"},
    
    # САЛАТИ - вага
    {"question": "Яка вага салату Цезар?", "options": ["250г", "300г", "350г"], "answer": "300г", "category": "salad"},
    {"question": "Яка вага Грецького салату?", "options": ["250г", "300г", "350г"], "answer": "300г", "category": "salad"},
    {"question": "Яка вага Овочевого салату з горіховою заправкою?", "options": ["250г", "300г", "350г"], "answer": "300г", "category": "salad"},
    {"question": "Яка вага салату з хамоном?", "options": ["150г", "200г", "250г"], "answer": "200г", "category": "salad"},
    
    # САЛАТИ - інгредієнти
    {"question": "Що входить в салат Цезар?", "options": ["Курка, бекон, пармезан", "Телятина, руккола, томати", "Хамон, груша, горіхи"], "answer": "Курка, бекон, пармезан", "category": "salad"},
    {"question": "Який сир в Грецькому салаті?", "options": ["Фета", "Моцарела", "Пармезан"], "answer": "Фета", "category": "salad"},
    {"question": "З чим подається Овочевий салат?", "options": ["Соусом цезар", "Горіховою заправкою", "Песто"], "answer": "Горіховою заправкою", "category": "salad"},
    {"question": "Який сир в салаті з хамоном?", "options": ["Фета", "Дор Блю", "Чедер"], "answer": "Дор Блю", "category": "salad"},
    
    # ПІДЕ - ціни
    {"question": "Скільки коштує Піде з моцарелою та томатами?", "options": ["259₴", "289₴", "319₴"], "answer": "289₴", "category": "pide"},
    {"question": "Скільки коштує Сирне піде з інжиром?", "options": ["259₴", "289₴", "319₴"], "answer": "289₴", "category": "pide"},
    {"question": "Скільки коштує Піде з грушею і чотирма сирами?", "options": ["299₴", "329₴", "359₴"], "answer": "329₴", "category": "pide"},
    {"question": "Скільки коштує Піде з телятиною?", "options": ["249₴", "279₴", "309₴"], "answer": "279₴", "category": "pide"},
    {"question": "Скільки коштує Піде з куркою?", "options": ["229₴", "259₴", "289₴"], "answer": "259₴", "category": "pide"},
    
    # ПІДЕ - вага та інгредієнти
    {"question": "Яка вага Піде з моцарелою?", "options": ["500г", "600г", "700г"], "answer": "600г", "category": "pide"},
    {"question": "Яка вага Сирного піде з інжиром?", "options": ["400г", "450г", "500г"], "answer": "450г", "category": "pide"},
    {"question": "Які сири в Піде з чотирма сирами?", "options": ["Моцарела, чедер, фета, пармезан", "Моцарела, сулугуні, чедер, дорблю", "Брі, горгонзола, фета, моцарела"], "answer": "Моцарела, сулугуні, чедер, дорблю", "category": "pide"},
    {"question": "З чим Піде з інжиром?", "options": ["З фісташкою", "З мигдалем", "З волоським горіхом"], "answer": "З фісташкою", "category": "pide"},
    
    # СУПИ - ціни
    {"question": "Скільки коштує Гарячий борщ?", "options": ["149₴", "179₴", "209₴"], "answer": "179₴", "category": "soup"},
    {"question": "Скільки коштує борщ з сальцем?", "options": ["239₴", "269₴", "299₴"], "answer": "269₴", "category": "soup"},
    {"question": "Скільки коштує Суп Вушка?", "options": ["99₴", "119₴", "139₴"], "answer": "119₴", "category": "soup"},
    {"question": "Скільки коштує Вершковий грибний крем-суп?", "options": ["139₴", "159₴", "179₴"], "answer": "159₴", "category": "soup"},
    {"question": "Скільки коштує М'ясна солянка?", "options": ["149₴", "169₴", "189₴"], "answer": "169₴", "category": "soup"},
    
    # СУПИ - вага та інгредієнти
    {"question": "Яка вага Гарячого борщу?", "options": ["410г", "460г", "510г"], "answer": "460г", "category": "soup"},
    {"question": "З чим подається борщ?", "options": ["З хлібом", "З пампушками", "З грінками"], "answer": "З пампушками", "category": "soup"},
    {"question": "Що в Супі Вушка?", "options": ["Пельмені зі свининою", "Пельмені з яловичиною", "Пельмені з куркою"], "answer": "Пельмені зі свининою", "category": "soup"},
    
    # ЗАКУСКИ - ціни
    {"question": "Скільки коштує Картопля Фрі?", "options": ["59₴", "79₴", "99₴"], "answer": "79₴", "category": "snack"},
    {"question": "Скільки коштує Батат фрі?", "options": ["119₴", "139₴", "159₴"], "answer": "139₴", "category": "snack"},
    {"question": "Скільки коштують Стріпси?", "options": ["109₴", "129₴", "149₴"], "answer": "129₴", "category": "snack"},
    {"question": "Скільки коштують Сирні палички?", "options": ["179₴", "199₴", "219₴"], "answer": "199₴", "category": "snack"},
    {"question": "Скільки коштує Сирна тарілка?", "options": ["245₴", "265₴", "285₴"], "answer": "265₴", "category": "snack"},
    {"question": "Скільки коштує Жульєн?", "options": ["119₴", "139₴", "159₴"], "answer": "139₴", "category": "snack"},
    
    # ЗАКУСКИ - вага та інгредієнти
    {"question": "Яка вага Картоплі Фрі?", "options": ["120г", "140г", "160г"], "answer": "140г", "category": "snack"},
    {"question": "З чим подається Батат фрі?", "options": ["З кетчупом", "З соусом цезар та пармезаном", "З часниковим соусом"], "answer": "З соусом цезар та пармезаном", "category": "snack"},
    {"question": "Скільки видів сиру в Сирній тарілці?", "options": ["2 види", "3 види", "4 види"], "answer": "3 види", "category": "snack"},
    {"question": "Які сири в Сирній тарілці?", "options": ["Пармезан, Горгонзола, Брі", "Чедер, Моцарела, Фета", "Сулугуні, Дорблю, Брі"], "answer": "Пармезан, Горгонзола, Брі", "category": "snack"},
    
    # МАНТИ - ціни та інгредієнти
    {"question": "Скільки коштує 1 манта?", "options": ["29₴", "34₴", "39₴"], "answer": "34₴", "category": "manti"},
    {"question": "З чого Манти з сиром?", "options": ["Фермерський сир з зеленню", "Моцарела з томатами", "Крем сир з часником"], "answer": "Фермерський сир з зеленню", "category": "manti"},
    {"question": "Як готують манти?", "options": ["Варять", "Смажать", "На пару"], "answer": "На пару", "category": "manti"},
    {"question": "Що в класичних мантах?", "options": ["Рублена яловичина", "Свинина з курою", "Телятина"], "answer": "Рублена яловичина", "category": "manti"},
    
    # ДЕРУНИ
    {"question": "Скільки коштують Деруни зі сметаною?", "options": ["79₴", "99₴", "119₴"], "answer": "99₴", "category": "deruni"},
    {"question": "Скільки коштують Деруни з грибами?", "options": ["99₴", "119₴", "139₴"], "answer": "119₴", "category": "deruni"},
    {"question": "Яка вага Дерунів зі сметаною?", "options": ["200г", "240г", "280г"], "answer": "240г", "category": "deruni"},
    {"question": "З чим Деруни з грибами?", "options": ["З томатним соусом", "З вершковим соусом та пармезаном", "З часниковим соусом"], "answer": "З вершковим соусом та пармезаном", "category": "deruni"},
    
    # ГРИЛЬ - ціни
    {"question": "Скільки коштує Люля-кебаб з трьома видами м'яса?", "options": ["169₴", "189₴", "209₴"], "answer": "189₴", "category": "grill"},
    {"question": "Скільки коштують Реберця?", "options": ["229₴", "249₴", "269₴"], "answer": "249₴", "category": "grill"},
    {"question": "Скільки коштує Куряче стегно гриль?", "options": ["219₴", "239₴", "259₴"], "answer": "239₴", "category": "grill"},
    {"question": "Скільки коштує Філе молодої курки?", "options": ["229₴", "249₴", "269₴"], "answer": "249₴", "category": "grill"},
    {"question": "Скільки коштує Телятина на грилі?", "options": ["319₴", "339₴", "359₴"], "answer": "339₴", "category": "grill"},
    {"question": "Скільки коштує Шийна частина свинини?", "options": ["309₴", "329₴", "349₴"], "answer": "329₴", "category": "grill"},
    
    # ГРИЛЬ - вага та інгредієнти
    {"question": "Яка вага Люля-кебабу?", "options": ["220г", "260г", "300г"], "answer": "260г", "category": "grill"},
    {"question": "З яких видів м'яса люля-кебаб?", "options": ["Яловичина, свинина, курка", "Яловичина, баранина, курка", "Свинина, курка, індичка"], "answer": "Яловичина, свинина, курка", "category": "grill"},
    {"question": "Яка вага Філе курки?", "options": ["320г", "360г", "400г"], "answer": "360г", "category": "grill"},
    {"question": "Який прожарок Телятини на грилі?", "options": ["Rare", "Medium", "Well done"], "answer": "Medium", "category": "grill"},
    {"question": "Яка вага Шийної частини свинини?", "options": ["360г", "410г", "460г"], "answer": "410г", "category": "grill"},
    
    # ОСНОВНІ СТРАВИ - ціни
    {"question": "Скільки коштує Плов?", "options": ["149₴", "169₴", "189₴"], "answer": "169₴", "category": "main"},
    {"question": "Скільки коштують Пельмені з телятиною?", "options": ["149₴", "169₴", "189₴"], "answer": "169₴", "category": "main"},
    {"question": "Скільки коштують Пельмені з куркою?", "options": ["149₴", "169₴", "189₴"], "answer": "169₴", "category": "main"},
    {"question": "Скільки коштують Телячі щічки?", "options": ["349₴", "369₴", "389₴"], "answer": "369₴", "category": "main"},
    
    # ОСНОВНІ СТРАВИ - вага та інгредієнти
    {"question": "Яка вага Плову?", "options": ["280г", "310г", "340г"], "answer": "310г", "category": "main"},
    {"question": "З якого м'яса Плов?", "options": ["Яловичина", "Яловичина та баранина", "Свинина"], "answer": "Яловичина та баранина", "category": "main"},
    {"question": "Яка вага Пельменів з телятиною?", "options": ["280г", "310г", "340г"], "answer": "310г", "category": "main"},
    {"question": "Яка вага Пельменів з куркою?", "options": ["235г", "265г", "295г"], "answer": "265г", "category": "main"},
    {"question": "Скільки годин томились Телячі щічки?", "options": ["12 годин", "24 години", "36 годин"], "answer": "24 години", "category": "main"},
    
    # МЛИНЦІ ТА СИРНИКИ
    {"question": "Скільки коштують Млинці з куркою та грибами?", "options": ["109₴", "129₴", "149₴"], "answer": "129₴", "category": "pancakes"},
    {"question": "Скільки коштують Млинці з куркою?", "options": ["109₴", "129₴", "149₴"], "answer": "129₴", "category": "pancakes"},
    {"question": "Скільки коштують Солодкі млинці?", "options": ["109₴", "129₴", "149₴"], "answer": "129₴", "category": "pancakes"},
    {"question": "Скільки коштують Сирники?", "options": ["99₴", "119₴", "139₴"], "answer": "119₴", "category": "pancakes"},
    
    # СНІДАНКИ - ціни
    {"question": "Скільки коштує сніданок Фрітата?", "options": ["149₴", "169₴", "189₴"], "answer": "169₴", "category": "breakfast"},
    {"question": "Скільки коштує сніданок Бюргер?", "options": ["169₴", "189₴", "209₴"], "answer": "189₴", "category": "breakfast"},
    {"question": "Скільки коштує сніданок Субмарина?", "options": ["189₴", "209₴", "229₴"], "answer": "209₴", "category": "breakfast"},
    {"question": "Скільки коштує Шакшука?", "options": ["139₴", "159₴", "179₴"], "answer": "159₴", "category": "breakfast"},
    {"question": "Скільки коштує сніданок Як вдома?", "options": ["159₴", "179₴", "199₴"], "answer": "179₴", "category": "breakfast"},
    {"question": "Скільки коштує Гарбузовий тост з лисичками?", "options": ["189₴", "209₴", "229₴"], "answer": "209₴", "category": "breakfast"},
    
    # ДЕСЕРТИ - ціни
    {"question": "Скільки коштує Крем-брюле?", "options": ["109₴", "129₴", "149₴"], "answer": "129₴", "category": "dessert"},
    {"question": "Скільки коштує Шоколадний фондан?", "options": ["149₴", "169₴", "189₴"], "answer": "169₴", "category": "dessert"},
    {"question": "Скільки коштує Чизкейк LA?", "options": ["119₴", "139₴", "159₴"], "answer": "139₴", "category": "dessert"},
    {"question": "Скільки коштує Вафельний десерт?", "options": ["79₴", "99₴", "119₴"], "answer": "99₴", "category": "dessert"},
    
    # ДЕСЕРТИ - інгредієнти
    {"question": "З чим подається Шоколадний фондан?", "options": ["З вершками", "З білим морозивом", "З ягодами"], "answer": "З білим морозивом", "category": "dessert"},
    {"question": "Яка особливість Чизкейку LA?", "options": ["Холодний чизкейк", "Гарячого приготування", "З желе"], "answer": "Гарячого приготування", "category": "dessert"},
    {"question": "Яка вага Крем-брюле?", "options": ["140г", "160г", "180г"], "answer": "160г", "category": "dessert"},
    
    # ДИТЯЧЕ МЕНЮ
    {"question": "Скільки коштують Фрикадельки з індички?", "options": ["199₴", "219₴", "239₴"], "answer": "219₴", "category": "kids"},
    {"question": "З чим Фрикадельки з індички?", "options": ["З рисом", "З картопляним пюре", "З пастою"], "answer": "З картопляним пюре", "category": "kids"},
]

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
    
    creds_path = "/etc/secrets/project-telegram-bot-475412-704fc4e68815.json"
    if not os.path.exists(creds_path):
        creds_path = "creds.json"
    
    logging.info(f"Reading credentials from: {creds_path}")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    logging.info("Successfully connected to Google Sheets!")
    return sheet

# Запис результату в Google Sheets
def save_result_to_sheet(username, first_name, correct, total, percentage):
    try:
        sheet = get_google_sheet()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display_name = f"{first_name} (@{username})" if username else first_name
        
        # Додаємо рядок: Дата | Ім'я | Результат | Відсоток
        sheet.append_row([now, display_name, f"{correct}/{total}", f"{percentage:.1f}%"])
        logging.info(f"Result saved for {display_name}: {correct}/{total} ({percentage:.1f}%)")
        return True
    except Exception as e:
        logging.error(f"Error saving to sheet: {e}")
        return False

# Отримання випадкових питань
def get_random_questions(count=15):
    if len(QUESTIONS_DB) < count:
        count = len(QUESTIONS_DB)
    return random.sample(QUESTIONS_DB, count)

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(
        "🍽 Вітаю! Почнемо тест по меню ресторану!\n\n"
        "📋 Умови тесту:\n"
        "• 15 випадкових питань\n"
        "• 10 секунд на відповідь\n"
        "• Вибирай відповідь з варіантів\n\n"
        "Готовий? Натисни /quiz щоб почати!",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Команда /quiz - початок тесту
@dp.message(Command("quiz"))
async def quiz_command(message: types.Message, state: FSMContext):
    # Генеруємо випадкові питання
    questions = get_random_questions(15)
    
    # Зберігаємо дані квізу в state
    await state.update_data(
        questions=questions,
        current_question=0,
        correct_answers=0,
        username=message.from_user.username or "Unknown",
        first_name=message.from_user.first_name or "User"
    )
    
    await message.answer("🚀 Починаємо тест! Удачі!")
    await asyncio.sleep(1)
    
    # Запускаємо квіз
    await send_question(message, state)

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
    
    # Клавіатура з варіантами
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=opt)] for opt in q['options']],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(question_text, reply_markup=keyboard)
    await message.answer("⏱ У тебе 10 секунд!")
    
    # Зберігаємо час початку питання
    await state.update_data(question_start_time=asyncio.get_event_loop().time())
    await state.set_state(QuizStates.waiting_for_answer)
    
    # Запускаємо таймер на 10 секунд
    asyncio.create_task(question_timer(message, state, current))

# Таймер для питання (10 секунд)
async def question_timer(message: types.Message, state: FSMContext, question_number: int):
    await asyncio.sleep(10)
    
    # Перевіряємо чи користувач ще на тому ж питанні
    data = await state.get_data()
    current_state = await state.get_state()
    
    if (current_state == QuizStates.waiting_for_answer and 
        data.get('current_question') == question_number):
        
        # Час вийшов!
        await message.answer(
            "⏰ Час вийшов!\n"
            f"Правильна відповідь: {data['questions'][question_number]['answer']}",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # Переходимо до наступного питання
        await state.update_data(current_question=question_number + 1)
        await asyncio.sleep(1.5)
        await send_question(message, state)

# Обробка відповіді
@dp.message(QuizStates.waiting_for_answer, F.text)
async def process_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    questions = data['questions']
    current = data['current_question']
    correct_count = data['correct_answers']
    
    # Перевіряємо чи не вийшов час (користувач відповів вчасно)
    question_start = data.get('question_start_time', 0)
    elapsed_time = asyncio.get_event_loop().time() - question_start
    
    if elapsed_time > 10:
        # Користувач запізнився - ігноруємо відповідь
        return
    
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
    await asyncio.sleep(1.5)
    
    # Наступне питання
    await send_question(message, state)

# Завершення квізу
async def finish_quiz(message: types.Message, state: FSMContext):
    data = await state.get_data()
    correct = data['correct_answers']
    total = len(data['questions'])
    username = data['username']
    first_name = data['first_name']
    
    percentage = (correct / total) * 100
    
    # Визначаємо оцінку
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
    
    # Зберігаємо результат в Google Sheets
    saved = save_result_to_sheet(username, first_name, correct, total, percentage)
    
    if saved:
        result_text += "✅ Результат збережено!\n\n"
    else:
        result_text += "⚠️ Помилка збереження результату\n\n"
    
    result_text += "Щоб пройти тест знову, натисни /quiz"
    
    await message.answer(result_text, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

# Команда /help
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
        "/stats - Статистика (скоро)\n\n"
        "⏱ Умови тесту:\n"
        "• 15 випадкових питань\n"
        "• 10 секунд на кожну відповідь\n"
        "• Результати зберігаються автоматично\n\n"
        "Удачі! 🍀"
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
        "❌ Тест скасовано.\n\nЩоб почати знову, натисни /quiz",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обробка невідомих повідомлень під час квізу
@dp.message(QuizStates.waiting_for_answer)
async def unknown_answer(message: types.Message):
    await message.answer(
        "⚠️ Будь ласка, вибери відповідь з варіантів на клавіатурі."
    )

# Обробка всіх інших повідомлень
@dp.message()
async def echo(message: types.Message):
    await message.answer(
        "👋 Привіт! Я бот для тестування знань меню.\n\n"
        "Натисни /quiz щоб почати тест\n"
        "Або /help для довідки"
    )

# Головна функція запуску
async def main():
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
