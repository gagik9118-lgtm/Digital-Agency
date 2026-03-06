import telebot
from telebot import types
import sqlite3
import time
from datetime import datetime, timedelta
import random
import string
from functools import wraps
import os
import flask

# Конфигурация - ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
TOKEN = os.environ.get('BOT_TOKEN')
OWNER_ID = 8396445302
ADMIN_IDS = [8396445302]

if not TOKEN:
    raise ValueError("Токен бота не найден! Установи переменную окружения BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

# Flask приложение для вебхука
app = flask.Flask(__name__)

# Удаляем вебхук при старте (важно!)
bot.remove_webhook()
time.sleep(1)

user_message_times = {}
FLOOD_LIMIT = 5
FLOOD_BAN_TIME = 30

# Весь твой существующий код функций (init_db, save_user, main_menu и т.д.)
# ОСТАВЛЯЕМ БЕЗ ИЗМЕНЕНИЙ до самого конца

def flood_control(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        if user_id in user_message_times:
            if isinstance(user_message_times[user_id], dict) and 'ban_until' in user_message_times[user_id]:
                if datetime.now() < user_message_times[user_id]['ban_until']:
                    bot.send_message(message.chat.id, "⏳ Вы заблокированы за флуд. Подождите 30 секунд.")
                    return
                else:
                    del user_message_times[user_id]
        now = datetime.now()
        if user_id not in user_message_times or not isinstance(user_message_times[user_id], dict):
            user_message_times[user_id] = {'count': 1, 'first_message': now}
        else:
            time_diff = (now - user_message_times[user_id]['first_message']).total_seconds()
            if time_diff <= 1:
                user_message_times[user_id]['count'] += 1
                if user_message_times[user_id]['count'] > FLOOD_LIMIT:
                    user_message_times[user_id]['ban_until'] = now + timedelta(seconds=FLOOD_BAN_TIME)
                    bot.send_message(message.chat.id, f"🚫 Вы заблокированы на {FLOOD_BAN_TIME} секунд за флуд.")
                    return
            else:
                user_message_times[user_id] = {'count': 1, 'first_message': now}
        return func(message, *args, **kwargs)
    return wrapper

def check_ban(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
        banned = c.fetchone()
        conn.close()
        if banned:
            bot.send_message(message.chat.id, "🚫 Вы были заблокированы администрацией Golden House.")
            return
        return func(message, *args, **kwargs)
    return wrapper

def init_db():
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS requests')
    c.execute('DROP TABLE IF EXISTS referrals')
    c.execute('DROP TABLE IF EXISTS transactions')
    c.execute('DROP TABLE IF EXISTS banned_users')
    c.execute('''CREATE TABLE users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  is_admin INTEGER DEFAULT 0,
                  joined_date TEXT,
                  referrer_id INTEGER DEFAULT NULL,
                  referral_code TEXT UNIQUE,
                  balance INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  service TEXT,
                  sub_service TEXT,
                  description TEXT,
                  deadline TEXT,
                  budget TEXT,
                  business_type TEXT,
                  status TEXT DEFAULT 'new',
                  created_at TEXT)''')
    c.execute('''CREATE TABLE referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER,
                  referral_id INTEGER,
                  date TEXT,
                  bonus_amount INTEGER DEFAULT 0,
                  bonus_paid INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount INTEGER,
                  type TEXT,
                  description TEXT,
                  date TEXT)''')
    c.execute('''CREATE TABLE banned_users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  banned_by INTEGER,
                  ban_date TEXT,
                  reason TEXT DEFAULT "Нарушение правил")''')
    conn.commit()
    conn.close()
    print("✅ База данных создана заново!")

def generate_referral_code(user_id):
    return f"GOLD{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

def save_user(message, referrer_code=None):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    user_id = message.from_user.id
    username = message.from_user.username or "Нет username"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    referral_code = generate_referral_code(user_id)
    referrer_id = None
    if referrer_code:
        c.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
        result = c.fetchone()
        if result:
            referrer_id = result[0]
            c.execute("INSERT INTO referrals (referrer_id, referral_id, date) VALUES (?, ?, ?)",
                     (referrer_id, user_id, joined_date))
    c.execute("""INSERT INTO users 
                 (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name, is_admin, balance, referral_code FROM users")
    users = c.fetchall()
    conn.close()
    return users

def get_user_stats(user_id):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("""SELECT user_id, username, first_name, last_name, joined_date, 
                        referrer_id, referral_code, balance, is_admin
                 FROM users WHERE user_id = ?""", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return None
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    c.execute("SELECT SUM(bonus_amount) FROM referrals WHERE referrer_id = ?", (user_id,))
    total_bonus = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM requests WHERE user_id = ?", (user_id,))
    requests_count = c.fetchone()[0]
    c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
    banned = c.fetchone() is not None
    conn.close()
    return {
        'user_id': user[0],
        'username': user[1],
        'first_name': user[2],
        'last_name': user[3],
        'joined_date': user[4],
        'referrer_id': user[5],
        'referral_code': user[6],
        'balance': user[7],
        'is_admin': user[8],
        'referrals_count': referrals_count,
        'total_bonus': total_bonus,
        'requests_count': requests_count,
        'banned': banned
    }

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    services = [
        "💻 Web-разработка",
        "📈 SEO-продвижение",
        "🎯 Таргет-реклама",
        "🤖 Telegram боты",
        "🔍 Аудит сайта",
        "🎨 Дизайн",
        "💼 Консультация (2.000₽/час)",
        "👥 Реферальная система",
        "⭐ Оставить отзыв"
    ]
    buttons = [types.KeyboardButton(service) for service in services]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start'])
@check_ban
@flood_control
def start(message):
    args = message.text.split()
    referrer_code = args[1] if len(args) > 1 else None
    save_user(message, referrer_code)
    welcome_text = """
🌟 Добро пожаловать в <b>Golden House</b>! 🌟

Золотой стандарт digital-услуг для вашего бизнеса. Мы превращаем идеи в прибыльные проекты.

<b>Наши контакты:</b>
📞 Телефон: +79509991605
💬 Telegram: @Goldenhouse911
📧 Email: digitalofficialgoldenhouse@gmail.com
👨‍💻 Владелец: @Opps911

Выберите интересующую вас услугу в меню ниже 👇
    """
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "⭐ Оставить отзыв")
@check_ban
@flood_control
def leave_review(message):
    bot.send_message(
        message.chat.id,
        "⭐ Хотите оставить отзыв о нашей работе?\n\n"
        "Перейдите в бот для отзывов: @GoldenHouseOtzovBot\n\n"
        "Нам важно ваше мнение! ✨",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "👥 Реферальная система")
@check_ban
@flood_control
def referral_system(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("SELECT referral_code, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if not result:
        bot.send_message(message.chat.id, "❌ Ошибка: реферальный код не найден. Напишите /start заново.")
        conn.close()
        return
    referral_code, balance = result
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    c.execute("SELECT SUM(bonus_amount) FROM referrals WHERE referrer_id = ?", (user_id,))
    total_earned = c.fetchone()[0] or 0
    c.execute("SELECT amount, description, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT 5", (user_id,))
    transactions = c.fetchall()
    conn.close()
    referral_link = f"https://t.me/{bot.get_me().username}?start={referral_code}"
    text = f"""
👥 <b>РЕФЕРАЛЬНАЯ СИСТЕМА GOLDEN HOUSE</b>

💰 <b>Текущий баланс:</b> {balance} ₽
💵 <b>Всего заработано:</b> {total_earned} ₽
👤 <b>Приглашено друзей:</b> {referrals_count}

🔗 <b>Ваша реферальная ссылка:</b>
<code>{referral_link}</code>

📌 <b>Как это работает:</b>
• За каждого друга, который перейдёт по вашей ссылке и закажет услугу, вы получаете 10% от суммы заказа
• Выплаты раз в неделю (по запросу админу)
• Чем больше друзей, тем больше доход!
"""
    if transactions:
        text += "\n📋 <b>Последние начисления:</b>\n"
        for amount, desc, date in transactions:
            text += f"  • +{amount}₽ - {desc} ({date[:16]})\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "🎨 Дизайн")
@check_ban
@flood_control
def design_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = [
        types.InlineKeyboardButton("🏠 Дизайн интерьера (800₽/м²)", callback_data="design_interior"),
        types.InlineKeyboardButton("👕 Дизайн одежды", callback_data="design_clothing"),
        types.InlineKeyboardButton("📊 Инфографика", callback_data="design_infographic"),
        types.InlineKeyboardButton("💻 Веб-дизайн", callback_data="design_web"),
        types.InlineKeyboardButton("« Отмена", callback_data="cancel_design")
    ]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "🎨 <b>Выберите какой Вам нужен дизайн:</b>", parse_mode='HTML', reply_markup=markup)

user_data = {}

@bot.message_handler(func=lambda message: message.text in [
    "💻 Web-разработка",
    "📈 SEO-продвижение",
    "🎯 Таргет-реклама",
    "🤖 Telegram боты",
    "🔍 Аудит сайта"
])
@check_ban
@flood_control
def handle_service(message):
    user_id = message.from_user.id
    service = message.text
    user_data[user_id] = {'service': service, 'step': 'business'}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    msg = bot.send_message(message.chat.id, "📋 Расскажите о вашем бизнесе:\nЧем занимаетесь? Какая у вас ниша?", reply_markup=markup)
    bot.register_next_step_handler(msg, process_business)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_order(call):
    user_id = int(call.data.split("_")[1])
    if user_id in user_data:
        del user_data[user_id]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Заказ отменён. Возвращайтесь, когда будете готовы!", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "cancel_design")
def cancel_design(call):
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Выбор дизайна отменён.", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith("design_") and call.data != "cancel_design")
def handle_design(call):
    user_id = call.from_user.id
    design_type = {
        "design_interior": "Дизайн интерьера (800₽/м²)",
        "design_clothing": "Дизайн одежды",
        "design_infographic": "Инфографика",
        "design_web": "Веб-дизайн"
    }.get(call.data, "Дизайн")
    user_data[user_id] = {'service': 'Дизайн', 'sub_service': design_type, 'step': 'business'}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    bot.edit_message_text("📋 Расскажите о вашем бизнесе:\nЧем занимаетесь? Какая у вас ниша?",
                         call.message.chat.id, call.message.message_id, reply_markup=markup)
    msg = bot.send_message(call.message.chat.id, "Введите описание:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_business)

@bot.message_handler(func=lambda message: message.text == "💼 Консультация (2.000₽/час)")
@check_ban
@flood_control
def handle_consultation(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
    user_data_db = c.fetchone()
    conn.close()
    username = user_data_db[0] if user_data_db else "Нет username"
    first_name = user_data_db[1] if user_data_db else ""
    last_name = user_data_db[2] if user_data_db else ""
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""
🔔 <b>ЗАПРОС НА КОНСУЛЬТАЦИЮ (2.000₽/час)</b>

👤 <b>Клиент:</b> {first_name} {last_name}
🆔 <b>ID:</b> <code>{user_id}</code>
📱 <b>Username:</b> @{username}

💰 <b>Услуга:</b> Консультация (2.000₽/час)

⏰ <b>Время:</b> {datetime.now().strftime("%H:%M %d.%m.%Y")}
            """
            bot.send_message(admin_id, admin_text, parse_mode='HTML')
        except:
            pass
    bot.send_message(message.chat.id, "✅ Запрос на консультацию отправлен! Мы свяжемся с вами в ближайшее время.\nСпасибо за обращение в Golden House! 🌟", reply_markup=main_menu())

@check_ban
@flood_control
def process_business(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    user_data[user_id]['business'] = message.text
    user_data[user_id]['step'] = 'description'
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    msg = bot.send_message(message.chat.id, "💡 Что вы хотите получить?\nОпишите задачу максимально подробно:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_description)

@check_ban
@flood_control
def process_description(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    user_data[user_id]['description'] = message.text
    user_data[user_id]['step'] = 'deadline'
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    msg = bot.send_message(message.chat.id, "⏰ Какой дедлайн?\nНапример: 3 дня, неделя, срочно за 4 часа", reply_markup=markup)
    bot.register_next_step_handler(msg, process_deadline)

@check_ban
@flood_control
def process_deadline(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    user_data[user_id]['deadline'] = message.text
    user_data[user_id]['step'] = 'budget'
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    msg = bot.send_message(message.chat.id, "💰 Какой бюджет?\nУкажите сумму в рублях:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_budget)

@check_ban
@flood_control
def process_budget(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    user_data[user_id]['budget'] = message.text
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    user_info = bot.get_chat(user_id)
    username = user_info.username or "Нет username"
    c.execute("""INSERT INTO requests 
                 (user_id, username, service, sub_service, business_type, description, deadline, budget, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, user_data[user_id]['service'], user_data[user_id].get('sub_service', ''),
               user_data[user_id]['business'], user_data[user_id]['description'],
               user_data[user_id]['deadline'], user_data[user_id]['budget'],
               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    try:
        budget_amount = int(''.join(filter(str.isdigit, user_data[user_id]['budget'])))
        bonus = int(budget_amount * 0.1)
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer = c.fetchone()
        if referrer and referrer[0]:
            referrer_id = referrer[0]
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, referrer_id))
            c.execute("""UPDATE referrals SET bonus_amount = ? 
                        WHERE referrer_id = ? AND referral_id = ?""", (bonus, referrer_id, user_id))
            c.execute("INSERT INTO transactions (user_id, amount, type, description, date) VALUES (?, ?, ?, ?, ?)",
                      (referrer_id, bonus, 'bonus', f"Бонус за заказ #{request_id} от @{username}", 
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        conn.close()
    except:
        pass
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""
🔔 <b>НОВАЯ ЗАЯВКА #{request_id}</b>

👤 <b>Клиент:</b> @{username}
🆔 <b>ID:</b> <code>{user_id}</code>

📋 <b>Услуга:</b> {user_data[user_id]['service']}
"""
            if user_data[user_id].get('sub_service'):
                admin_text += f"📌 <b>Подкатегория:
