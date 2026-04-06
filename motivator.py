import telebot
from telebot import types
import threading
import random
import os
import io
from google import genai
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# === ИНИЦИАЛИЗАЦИЯ ВЕБ-СЕРВЕРА ДЛЯ RENDER ===
app = Flask('')

@app.route('/')
def home():
    return "Бот работает. Московское время активно."

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# === ТОКЕНЫ И НАСТРОЙКИ ===
TG_TOKEN = os.environ.get('TG_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 531078672))

# Функция для получения точного московского времени (UTC + 3)
def get_now():
    return datetime.utcnow() + timedelta(hours=3)

# Дата отказа от курения (сделана глобальной переменной для возможности сброса)
QUIT_DATE = datetime(2025, 4, 5) 
DAILY_COST = 142.5 
CIGARETTES_PER_DAY = 10 

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# База данных сессии
user_stats = {
    'skincare_am': False,
    'skincare_pm': False,
    'vitamins': False,
    'sos_survived': 0, 
    'last_reset': get_now().date()
}

def is_admin(message):
    chat_id = message.chat.id if hasattr(message, 'chat') else message.message.chat.id
    return chat_id == ADMIN_ID

def check_daily_reset():
    global user_stats
    now_date = get_now().date()
    if user_stats['last_reset'] != now_date:
        user_stats['skincare_am'] = False
        user_stats['skincare_pm'] = False
        user_stats['vitamins'] = False
        user_stats['last_reset'] = now_date

# --- ГЕНЕРАТОР КАРТОЧКИ ---
def generate_prime_card(days_clean, saved_money, avoided_cigs, sos_count):
    W, H = 800, 350
    bg_color = (15, 15, 17)
    accent_color = (0, 212, 255) 
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)
    from PIL import Image, ImageDraw, ImageFont
    try:
        font_title = ImageFont.truetype("Montserrat-Bold.ttf", 45)
        font_med = ImageFont.truetype("Montserrat-Bold.ttf", 35)
        font_small = ImageFont.truetype("Montserrat-Bold.ttf", 20)
    except:
        font_title = font_med = font_small = ImageFont.load_default()

    draw.rectangle([0, 0, 10, H], fill=accent_color)
    draw.text((40, 40), "СТАТИСТИКА ПРОГРЕССА", font=font_title, fill=(255, 255, 255))
    draw.line((40, 110, 760, 110), fill=(40, 40, 45), width=2)
    draw.text((40, 140), "БЕЗ СИГАРЕТ", font=font_small, fill=(150, 150, 150))
    draw.text((40, 170), f"{days_clean} ДНЕЙ", font=font_med, fill=(255, 255, 255))
    draw.text((320, 140), "СЭКОНОМЛЕНО", font=font_small, fill=(150, 150, 150))
    draw.text((320, 170), f"{saved_money} ₽", font=font_med, fill=(46, 204, 113))
    draw.text((580, 140), "НЕ ВЫКУРЕНО", font=font_small, fill=(150, 150, 150))
    draw.text((580, 170), f"{avoided_cigs} ШТ", font=font_med, fill=(255, 255, 255))
    draw.text((40, 240), "ПОДАВЛЕНО СРЫВОВ (SOS)", font=font_small, fill=(150, 150, 150))
    draw.text((40, 270), f"{sos_count} РАЗ", font=font_med, fill=accent_color)
    draw.text((430, 280), f"Обновлено: {get_now().strftime('%d.%m.%Y %H:%M')}", font=font_small, fill=(80, 80, 80))
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('🆘 ХОЧУ КУРИТЬ (SOS)'))
    markup.add(
        types.KeyboardButton('📊 Прогресс'),
        types.KeyboardButton('🧠 ИИ-Ассистент'),
        types.KeyboardButton('🧪 Анализ состава'),
        types.KeyboardButton('💊 Уход на день'),
        types.KeyboardButton('⏳ Таймеры')
    )
    markup.add(types.KeyboardButton('⚠️ Я сорвался...'))
    return markup

def ask_gemini(prompt_text, is_vision=False, image_data=None, system_context=""):
    base_instruction = (
        "Ты персональный ассистент. Парень бросает курить и лечит акне. "
        "Стиль: жесткий, прямолинейный, холодный. Никаких звездочек (*)."
    )
    full_instruction = f"{base_instruction} {system_context}"
    models_to_try = ['gemini-3.1-pro-preview', 'gemini-3-flash-preview', 'gemini-3.1-flash-lite-preview', 'gemini-flash-latest', 'gemini-2.0-flash', 'gemini-1.5-flash']
    img = Image.open(io.BytesIO(image_data)) if (is_vision and image_data) else None
    from PIL import Image
    for model_name in models_to_try:
        try:
            if is_vision:
                response = client.models.generate_content(model=model_name, contents=[full_instruction + "\n" + prompt_text, img])
            else:
                response = client.models.generate_content(model=model_name, contents=full_instruction + "\n" + prompt_text)
            return response.text.replace('*', '')
        except: continue
    return "Ошибка ИИ."

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_admin(message): return
    bot.send_message(message.chat.id, "Система запущена. Время МСК.", reply_markup=main_keyboard())

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if not is_admin(message): return
    check_daily_reset()
    chat_id = message.chat.id
    text = message.text

    if text == '🆘 ХОЧУ КУРИТЬ (SOS)':
        msg = bot.send_message(chat_id, "⚠️ **ТЯГА ЗАФИКСИРОВАНА.**\nГенерация...")
        bot.send_chat_action(chat_id, 'typing')
        prompt = "У меня тяга. Дай ОДНО короткое задание и напомни жестко, как никотин прямо сейчас убивает питание кожи лица."
        task_text = ask_gemini(prompt)
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Выполнил", callback_data="sos_done"))
        bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"🚨 **ЗАДАНИЕ:**\n\n{task_text}", reply_markup=markup)

    elif text == '📊 Прогресс':
        days_clean = (get_now() - QUIT_DATE).days
        photo = generate_prime_card(days_clean, int(days_clean * DAILY_COST), days_clean * CIGARETTES_PER_DAY, user_stats['sos_survived'])
        bot.send_photo(chat_id, photo)

    elif text == '⚠️ Я сорвался...':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Да, я покурил", callback_data="confirm_relapse"))
        markup.add(types.InlineKeyboardButton("Нет, ошибка", callback_data="cancel_relapse"))
        bot.send_message(chat_id, "‼️ **ВНИМАНИЕ**\n\nТы действительно хочешь признать срыв и обнулить статистику?", reply_markup=markup)

    elif text == '🧪 Анализ состава':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton('❌ Отмена'))
        msg = bot.send_message(chat_id, "Кидай состав текстом:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_ingredient_check)

    elif text == '🧠 ИИ-Ассистент':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton('❌ Отмена'))
        msg = bot.send_message(chat_id, "Пиши или шли фото:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_ai_query)

    elif text == '💊 Уход на день':
        bot.send_message(chat_id, "Твоя рутина:", reply_markup=get_routine_keyboard())

    elif text == '⏳ Таймеры':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("⏱ 5 мин", callback_data="timer_5"),
                   types.InlineKeyboardButton("⏱ 15 мин", callback_data="timer_15"),
                   types.InlineKeyboardButton("⏱ 20 мин", callback_data="timer_20"))
        bot.send_message(chat_id, "Таймеры:", reply_markup=markup)

    elif text == '❌ Отмена':
        bot.send_message(chat_id, "Меню.", reply_markup=main_keyboard())

# --- ОБРАБОТЧИКИ ---
@bot.callback_query_handler(func=lambda call: call.data == "confirm_relapse")
def confirm_relapse(call):
    global QUIT_DATE
    if not is_admin(call): return
    days_lost = (get_now() - QUIT_DATE).days
    # Запрашиваем у ИИ жесткий комментарий
    prompt = f"Я сорвался и покурил после {days_lost} дней чистоты. Напиши ОЧЕНЬ ЖЕСТКИЙ и прямой разнос. Объясни, что сейчас произошло с сосудами моего лица и почему мои прыщи теперь будут заживать вечно. Никакой жалости."
    insult = ask_gemini(prompt)
    
    QUIT_DATE = get_now() # Обнуляем дату
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                          text=f"🔴 **СТАТИСТИКА ОБНУЛЕНА.**\n\nТы потерял {days_lost} дней прогресса.\n\n{insult}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_relapse")
def cancel_relapse(call):
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Правильное решение. Продолжаем идти в завязке.")

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
    if not is_admin(message): return
    bot.send_chat_action(message.chat.id, 'typing')
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.path)
    bot.send_message(message.chat.id, ask_gemini("Оцени лицо/состав.", is_vision=True, image_data=downloaded_file))

@bot.callback_query_handler(func=lambda call: call.data == "sos_done")
def sos_done_callback(call):
    user_stats['sos_survived'] += 1
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n✅ ТЯГА ПОДАВЛЕНА!")

def get_routine_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    am = "✅ Утро" if user_stats['skincare_am'] else "❌ Утро"
    pm = "✅ Вечер" if user_stats['skincare_pm'] else "❌ Вечер"
    vit = "✅ Витамины" if user_stats['vitamins'] else "❌ Витамины"
    markup.add(types.InlineKeyboardButton(am, callback_data="rout_am"),
               types.InlineKeyboardButton(pm, callback_data="rout_pm"),
               types.InlineKeyboardButton(vit, callback_data="rout_vit"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('rout_'))
def routine_callback(call):
    if call.data == "rout_am": user_stats['skincare_am'] = not user_stats['skincare_am']
    elif call.data == "rout_pm": user_stats['skincare_pm'] = not user_stats['skincare_pm']
    elif call.data == "rout_vit": user_stats['vitamins'] = not user_stats['vitamins']
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_routine_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('timer_'))
def timer_callback(call):
    minutes = int(call.data.split('_')[1])
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"⏳ Таймер {minutes} мин запущен.")
    threading.Timer(minutes * 60, lambda: bot.send_message(call.message.chat.id, f"🔔 Время вышло ({minutes} мин)! Пора смывать/наносить.")).start()

if __name__ == '__main__':
    keep_alive()
    bot.polling(none_stop=True)
