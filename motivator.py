import telebot
from telebot import types
import threading
from google import genai
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io
from flask import Flask
from threading import Thread
import os

# Маленький сервер для обмана Koyeb
app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    # Koyeb сам назначит порт, обычно это 8000
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === ТОКЕНЫ И НАСТРОЙКИ ===
TG_TOKEN = '8644997797:AAGDkOSKxeViIFdMhi-FkFObd-AAzTPw33E'
GEMINI_API_KEY = 'AIzaSyCGwXbm6Mzlb_28hefN3JQdI_uKKpIsfIE'
ADMIN_ID = 531078672 

QUIT_DATE = datetime(2026, 4, 5) # Дата отказа от курения
DAILY_COST = 142.5 
CIGARETTES_PER_DAY = 10 

bot = telebot.TeleBot(TG_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# База данных
user_stats = {
    'skincare_am': False,
    'skincare_pm': False,
    'vitamins': False,
    'sos_survived': 0, 
    'last_reset': datetime.now().date()
}

def is_admin(message):
    if hasattr(message, 'chat'): return message.chat.id == ADMIN_ID
    return message.message.chat.id == ADMIN_ID

def check_daily_reset():
    global user_stats
    if user_stats['last_reset'] != datetime.now().date():
        user_stats['skincare_am'] = False
        user_stats['skincare_pm'] = False
        user_stats['vitamins'] = False
        user_stats['last_reset'] = datetime.now().date()

# --- ГЕНЕРАТОР КАРТОЧКИ ---
def generate_prime_card(days_clean, saved_money, avoided_cigs, sos_count):
    W, H = 800, 350
    bg_color = (15, 15, 17)
    accent_color = (0, 212, 255) 
    
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)
    
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

    draw.text((480, 280), f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}", font=font_small, fill=(80, 80, 80))

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
    return markup

def ask_gemini(prompt_text, is_vision=False, image_data=None, system_context=""):
    base_instruction = (
        "Ты персональный ассистент. Парень бросает курить и лечит акне. "
        "Стиль: жесткий, прямолинейный, без воды, профессиональный. Никаких звездочек (*)."
    )
    full_instruction = f"{base_instruction} {system_context}"
    
    models_to_try = ['gemini-3.1-pro-preview', 'gemini-3-flash-preview', 'gemini-3.1-flash-lite-preview', 'gemini-flash-latest', 'gemini-2.0-flash', 'gemini-1.5-flash']
    last_error = ""

    img = Image.open(io.BytesIO(image_data)) if (is_vision and image_data) else None

    for model_name in models_to_try:
        try:
            if is_vision:
                response = client.models.generate_content(model=model_name, contents=[full_instruction + "\n" + prompt_text, img])
            else:
                response = client.models.generate_content(model=model_name, contents=full_instruction + "\n" + prompt_text)
            return f"{response.text.replace('*', '')}\n\n⚙️ [Модель: {model_name}]"
        except Exception as e:
            last_error = e
            continue
    return f"Сбой ИИ: {last_error}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_admin(message): return
    bot.send_message(message.chat.id, "Бот запущен. Вывозим акне и никотин.", reply_markup=main_keyboard())

# === ЛОГИКА ===
@bot.message_handler(content_types=['text'])
def handle_text(message):
    if not is_admin(message): return
    check_daily_reset()
    chat_id = message.chat.id
    text = message.text

    if text == '🆘 ХОЧУ КУРИТЬ (SOS)':
        # Моментально даем понять, что бот принял команду
        msg = bot.send_message(chat_id, "⚠️ **ТЯГА ЗАФИКСИРОВАНА.**\nИИ генерирует контр-задачу...", parse_mode="Markdown")
        bot.send_chat_action(chat_id, 'typing')
        
        # Запрашиваем у ИИ уникальное задание
        prompt = (
            "У меня прямо сейчас острая тяга покурить. Сгенерируй ОДНО нестандартное, короткое задание на 1-2 минуты, "
            "чтобы резко переключить мой мозг и сбить импульс. "
            "Используй разные подходы каждый раз: задержка дыхания, микро-физическая нагрузка, воздействие холодом, "
            "или ментальный фокус на чем-то вокруг. "
            "В конце жестко напомни, как одна затяжка прямо сейчас вызовет спазм капилляров и отбросит лечение акне назад. "
            "Пиши как приказ. Коротко и по делу."
        )
        task_text = ask_gemini(prompt)
        
        # Редактируем сообщение, вставляя ответ от ИИ и кнопку
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Я подавил тягу (Выполнил)", callback_data="sos_done"))
        bot.edit_message_text(
            chat_id=chat_id, 
            message_id=msg.message_id, 
            text=f"🚨 **ВЫПОЛНЯТЬ ПРЯМО СЕЙЧАС:**\n\n{task_text}", 
            parse_mode="Markdown", 
            reply_markup=markup
        )

    elif text == '📊 Прогресс':
        days_clean = (datetime.now() - QUIT_DATE).days
        photo = generate_prime_card(days_clean, int(days_clean * DAILY_COST), days_clean * CIGARETTES_PER_DAY, user_stats['sos_survived'])
        bot.send_photo(chat_id, photo)

    elif text == '🧪 Анализ состава':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton('❌ Отмена'))
        msg = bot.send_message(chat_id, "Скопируй и отправь сюда состав косметики текстом (ingredients). Я проверю, забивает ли он поры:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_ingredient_check)

    elif text == '🧠 ИИ-Ассистент':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton('❌ Отмена'))
        msg = bot.send_message(chat_id, "Опиши проблему или отправь фото для анализа:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_ai_query)

    elif text == '💊 Уход на день':
        bot.send_message(chat_id, "Твои чек-поинты:", reply_markup=get_routine_keyboard())

    elif text == '⏳ Таймеры':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⏱ 5 мин (Маска)", callback_data="timer_5"),
            types.InlineKeyboardButton("⏱ 15 мин (Кислоты)", callback_data="timer_15"),
            types.InlineKeyboardButton("⏱ 20 мин (Ретинол)", callback_data="timer_20")
        )
        bot.send_message(chat_id, "Выбери таймер выдержки ухода:", reply_markup=markup)

    elif text == '❌ Отмена':
        bot.send_message(chat_id, "Меню.", reply_markup=main_keyboard())

def process_ai_query(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_keyboard()); return
    bot.send_chat_action(message.chat.id, 'typing')
    bot.send_message(message.chat.id, ask_gemini(message.text), reply_markup=main_keyboard())

def process_ingredient_check(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_keyboard()); return
    bot.send_chat_action(message.chat.id, 'typing')
    context = "Твоя задача ТОЛЬКО проанализировать состав косметики на комедогенность. Выпиши опасные ингредиенты, если они есть, и дай вердикт: можно мазать на кожу с акне или выкинуть."
    bot.send_message(message.chat.id, ask_gemini(f"Состав: {message.text}", system_context=context), reply_markup=main_keyboard())

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not is_admin(message): return
    bot.send_chat_action(message.chat.id, 'typing')
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.path)
    prompt = "Оцени постакне/воспаления на фото или состав на банке. Дай короткий совет."
    bot.send_message(message.chat.id, ask_gemini(prompt, is_vision=True, image_data=downloaded_file), reply_markup=main_keyboard())

# --- INLINE ОБРАБОТЧИКИ ---
@bot.callback_query_handler(func=lambda call: call.data == "sos_done")
def sos_done_callback(call):
    if not is_admin(call): return
    user_stats['sos_survived'] += 1
    
    # Чтобы убрать звездочки и прочий мусор из ответа ИИ, если он вдруг проскочил
    clean_text = call.message.text.replace('*', '')
    
    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id, 
        text=clean_text + f"\n\n✅ **ТЯГА ПОДАВЛЕНА (+1 в стату).**", 
        parse_mode="Markdown"
    )
    bot.send_message(call.message.chat.id, "Хорош. Сосуды спасены, кровь поступает к лицу нормально. Идем дальше.", reply_markup=main_keyboard())

def get_routine_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    am_text = "✅ Утро (умылся/крем)" if user_stats['skincare_am'] else "❌ Утро (умылся/крем)"
    pm_text = "✅ Вечер (уход перед сном)" if user_stats['skincare_pm'] else "❌ Вечер (уход перед сном)"
    vit_text = "✅ Витамины/Таблетки" if user_stats['vitamins'] else "❌ Витамины/Таблетки"
    markup.add(
        types.InlineKeyboardButton(am_text, callback_data="rout_am"),
        types.InlineKeyboardButton(pm_text, callback_data="rout_pm"),
        types.InlineKeyboardButton(vit_text, callback_data="rout_vit")
    )
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('rout_'))
def routine_callback(call):
    if not is_admin(call): return
    if call.data == "rout_am": user_stats['skincare_am'] = not user_stats['skincare_am']
    elif call.data == "rout_pm": user_stats['skincare_pm'] = not user_stats['skincare_pm']
    elif call.data == "rout_vit": user_stats['vitamins'] = not user_stats['vitamins']
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_routine_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('timer_'))
def timer_callback(call):
    if not is_admin(call): return
    minutes = int(call.data.split('_')[1])
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"⏳ Таймер на {minutes} минут запущен. Можно закрывать чат.")
    threading.Timer(minutes * 60, lambda: bot.send_message(call.message.chat.id, f"🔔 **Время вышло!** ({minutes} мин.) Иди смывай/наноси следующий этап.", parse_mode="Markdown")).start()

if __name__ == '__main__':
    print("Запуск веб-сервера...")
    keep_alive() 
    print("Бот запущен...")
    bot.polling(none_stop=True)