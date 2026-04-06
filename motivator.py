import telebot
from telebot import types
import threading
import random
import os
import io
import json
from google import genai
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from PIL import Image, ImageDraw, ImageFont

# === ИНИЦИАЛИЗАЦИЯ ВЕБ-СЕРВЕРА ===
app = Flask('')
@app.route('/')
def home(): return "Бот PRIME CORE активен."

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# === СИСТЕМА СОХРАНЕНИЯ ДАННЫХ ===
DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                data['quit_date'] = datetime.fromisoformat(data['quit_date'])
                return data
        except: pass
    return {
        'quit_date': datetime(2026, 4, 6, 0, 0), # Дефолт
        'sos_survived': 0,
        'skincare_am': False,
        'skincare_pm': False,
        'vitamins': False,
        'last_reset': str(datetime.utcnow().date())
    }

def save_data(data):
    copy_data = data.copy()
    copy_data['quit_date'] = copy_data['quit_date'].isoformat()
    with open(DATA_FILE, 'w') as f:
        json.dump(copy_data, f)

# === КОНФИГУРАЦИЯ ===
TG_TOKEN = os.environ.get('TG_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 531078672))

DAILY_COST = 142.5 
CIGS_PER_DAY = 10 

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)
user_stats = load_data()

def get_now():
    return datetime.utcnow() + timedelta(hours=3)

def check_daily_reset():
    global user_stats
    now_date = get_now().date()
    if str(user_stats['last_reset']) != str(now_date):
        user_stats['skincare_am'] = False
        user_stats['skincare_pm'] = False
        user_stats['vitamins'] = False
        user_stats['last_reset'] = str(now_date)
        save_data(user_stats)

def get_clean_time():
    diff = get_now() - user_stats['quit_date']
    days = diff.days
    hours = diff.seconds // 3600
    return days, hours

# --- ГЕНЕРАТОР КАРТОЧКИ ---
def generate_prime_card(days, hours, saved_money, avoided_cigs, sos_count):
    W, H = 800, 400 # Увеличили высоту для комфортного размещения
    bg_color = (15, 15, 17)
    accent_color = (0, 212, 255) 
    
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("Montserrat-Bold.ttf", 45)
        font_med = ImageFont.truetype("Montserrat-Bold.ttf", 36)
        font_small = ImageFont.truetype("Montserrat-Bold.ttf", 20)
    except:
        font_title = font_med = font_small = ImageFont.load_default()

    draw.rectangle([0, 0, 12, H], fill=accent_color)
    draw.text((45, 40), "СТАТИСТИКА ПРОГРЕССА", font=font_title, fill=(255, 255, 255))
    draw.line((45, 110, 755, 110), fill=(45, 45, 45), width=2)

    # Первый ряд
    draw.text((45, 140), "БЕЗ НИКОТИНА", font=font_small, fill=(150, 150, 150))
    draw.text((45, 175), f"{days}д. {hours}ч.", font=font_med, fill=(255, 255, 255))
    
    draw.text((340, 140), "СЭКОНОМЛЕНО", font=font_small, fill=(150, 150, 150))
    draw.text((340, 175), f"{saved_money} ₽", font=font_med, fill=(46, 204, 113))
    
    draw.text((600, 140), "НЕ ВЫКУРЕНО", font=font_small, fill=(150, 150, 150))
    draw.text((600, 175), f"{avoided_cigs} ШТ", font=font_med, fill=(255, 255, 255))

    # Второй ряд
    draw.text((45, 250), "ПОДАВЛЕНО СРЫВОВ (SOS)", font=font_small, fill=(150, 150, 150))
    draw.text((45, 285), f"{sos_count} РАЗ(А)", font=font_med, fill=accent_color)

    # Таймштамп снизу
    draw.text((45, 360), f"Обновлено: {get_now().strftime('%d.%m.%Y %H:%M')}", font=font_small, fill=(70, 70, 70))

    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🆘 ХОЧУ КУРИТЬ (SOS)'))
    markup.add(types.KeyboardButton('📊 Прогресс'), types.KeyboardButton('🧠 ИИ-Ассистент'))
    markup.add(types.KeyboardButton('🧪 Анализ состава'), types.KeyboardButton('💊 Уход на день'))
    markup.add(types.KeyboardButton('⏳ Таймеры'))
    markup.add(types.KeyboardButton('⚠️ Я сорвался...'))
    return markup

def ask_gemini(prompt_text, is_vision=False, image_data=None):
    instruction = "Ты эксперт по акне и отказу от курения. Стиль: лаконичный, жесткий. Без звездочек."
    models = ['gemini-3.1-pro-preview', 'gemini-3-flash-preview', 'gemini-3.1-flash-lite-preview', 'gemini-flash-latest', 'gemini-2.0-flash', 'gemini-1.5-flash']
    img = Image.open(io.BytesIO(image_data)) if is_vision else None
    for m in models:
        try:
            res = client.models.generate_content(model=m, contents=[instruction + "\n" + prompt_text, img] if img else instruction + "\n" + prompt_text)
            return res.text.replace('*', '')
        except: continue
    return "Ошибка ИИ."

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.id != ADMIN_ID: return
    bot.send_message(message.chat.id, "Система запущена. Время МСК. Данные сохранены.", reply_markup=main_keyboard())

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.chat.id != ADMIN_ID: return
    check_daily_reset()
    chat_id = message.chat.id
    text = message.text

    if text == '📊 Прогресс':
        days, hours = get_clean_time()
        # Считаем десятичные дни для денег и сигарет
        total_days_decimal = (get_now() - user_stats['quit_date']).total_seconds() / 86400
        photo = generate_prime_card(days, hours, int(total_days_decimal * DAILY_COST), int(total_days_decimal * CIGS_PER_DAY), user_stats['sos_survived'])
        bot.send_photo(chat_id, photo)

    elif text == '🆘 ХОЧУ КУРИТЬ (SOS)':
        bot.send_chat_action(chat_id, 'typing')
        task = ask_gemini("Дай короткое задание на 1 мин и жестко напомни, как никотин убивает сосуды лица.")
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Выполнил", callback_data="sos_done"))
        bot.send_message(chat_id, f"🚨 **ЗАДАНИЕ:**\n\n{task}", reply_markup=markup, parse_mode="Markdown")

    elif text == '⚠️ Я сорвался...':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Да, я покурил", callback_data="confirm_relapse"))
        markup.add(types.InlineKeyboardButton("Нет, я держусь", callback_data="cancel_relapse"))
        bot.send_message(chat_id, "‼️ Сбросить прогресс и обнулить счетчик?", reply_markup=markup)

    elif text == '🧪 Анализ состава':
        msg = bot.send_message(chat_id, "Кидай ингредиенты текстом:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Отмена"))
        bot.register_next_step_handler(msg, process_ingredient_check)

    elif text == '🧠 ИИ-Ассистент':
        msg = bot.send_message(chat_id, "Пиши вопрос или шли фото:", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Отмена"))
        bot.register_next_step_handler(msg, process_ai_query)

    elif text == '💊 Уход на день':
        bot.send_message(chat_id, "Твоя рутина:", reply_markup=get_routine_keyboard())

    elif text == '⏳ Таймеры':
        markup = types.InlineKeyboardMarkup(row_width=2).add(
            types.InlineKeyboardButton("5 мин", callback_data="timer_5"),
            types.InlineKeyboardButton("15 мин", callback_data="timer_15"),
            types.InlineKeyboardButton("20 мин", callback_data="timer_20"))
        bot.send_message(chat_id, "Запустить таймер:", reply_markup=markup)

    elif text == '❌ Отмена':
        bot.send_message(chat_id, "Меню.", reply_markup=main_keyboard())

# --- ОБРАБОТЧИКИ ---
@bot.callback_query_handler(func=lambda call: call.data == "confirm_relapse")
def confirm_relapse(call):
    global user_stats
    days, hours = get_clean_time()
    msg = ask_gemini(f"Я сорвался после {days} дней. Напиши жесткий разнос про мои сосуды и лицо.")
    user_stats['quit_date'] = get_now()
    save_data(user_stats)
    bot.edit_message_text(f"🔴 СТАТИСТИКА ОБНУЛЕНА.\n\n{msg}", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "sos_done")
def sos_done_callback(call):
    user_stats['sos_survived'] += 1
    save_data(user_stats)
    bot.edit_message_text("✅ Тяга подавлена. Кровь приливает к лицу.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_relapse")
def cancel_relapse(call):
    bot.edit_message_text("Срыв отменен. Продолжаем.", call.message.chat.id, call.message.message_id)

def process_ai_query(message):
    if message.text == '❌ Отмена': bot.send_message(message.chat.id, "Отмена.", reply_markup=main_keyboard()); return
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, ask_gemini(message.text), reply_markup=main_keyboard())

def process_ingredient_check(message):
    if message.text == '❌ Отмена': bot.send_message(message.chat.id, "Отмена.", reply_markup=main_keyboard()); return
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, ask_gemini(f"Проверь на комедогенность: {message.text}"), reply_markup=main_keyboard())

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.chat.id != ADMIN_ID: return
    bot.send_chat_action(message.chat.id, 'typing')
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.path)
    bot.send_message(message.chat.id, ask_gemini("Оцени лицо/состав.", is_vision=True, image_data=downloaded_file))

def get_routine_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    am = "✅ Утро" if user_stats['skincare_am'] else "❌ Утро"
    pm = "✅ Вечер" if user_stats['skincare_pm'] else "❌ Вечер"
    vit = "✅ Витамины" if user_stats['vitamins'] else "❌ Витамины"
    markup.add(types.InlineKeyboardButton(am, callback_data="rout_skincare_am"),
               types.InlineKeyboardButton(pm, callback_data="rout_skincare_pm"),
               types.InlineKeyboardButton(vit, callback_data="rout_vitamins"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('rout_'))
def routine_callback(call):
    key = call.data.replace("rout_", "")
    user_stats[key] = not user_stats[key]
    save_data(user_stats)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_routine_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('timer_'))
def timer_callback(call):
    m = int(call.data.split('_')[1])
    bot.edit_message_text(f"⏳ Таймер {m} мин запущен.", call.message.chat.id, call.message.message_id)
    threading.Timer(m*60, lambda: bot.send_message(call.message.chat.id, f"🔔 Время вышло ({m} мин)! Пора умываться.")).start()

if __name__ == '__main__':
    keep_alive()
    bot.infinity_polling()
