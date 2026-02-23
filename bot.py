import telebot
from telebot import types
import sqlite3
import time
import threading
from datetime import datetime, timedelta
import random
import string
import os

# Конфигурация - БЕЗОПАСНО (токен из окружения)
TOKEN = os.environ.get('BOT_TOKEN')
OWNER_ID = int(os.environ.get('OWNER_ID', 0))
ADMIN_IDS = [int(id) for id in os.environ.get('ADMIN_IDS', '').split(',') if id]

# Проверка что токен загружен
if not TOKEN:
    raise ValueError("❌ НЕТ ТОКЕНА! Добавь BOT_TOKEN в переменные окружения на хостинге!")

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    # Удаляем старую таблицу если есть
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS requests')
    c.execute('DROP TABLE IF EXISTS referrals')
    c.execute('DROP TABLE IF EXISTS transactions')
    
    # Таблица пользователей
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
    
    # Таблица заявок
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
    
    # Таблица рефералов
    c.execute('''CREATE TABLE referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER,
                  referral_id INTEGER,
                  date TEXT,
                  bonus_amount INTEGER DEFAULT 0,
                  bonus_paid INTEGER DEFAULT 0)''')
    
    # Таблица транзакций (для истории начислений)
    c.execute('''CREATE TABLE transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount INTEGER,
                  type TEXT,
                  description TEXT,
                  date TEXT)''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана заново!")

# Генерация реферального кода
def generate_referral_code(user_id):
    return f"GOLD{user_id}{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"

# Начисление бонуса рефереру
def add_bonus_to_referrer(referrer_id, amount, description):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    # Обновляем баланс пользователя
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, referrer_id))
    
    # Записываем транзакцию
    c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                 VALUES (?, ?, ?, ?, ?)""",
              (referrer_id, amount, 'bonus', description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

# Сохраняем пользователя
def save_user(message, referrer_code=None):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    user_id = message.from_user.id
    username = message.from_user.username or "Нет username"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Проверяем, есть ли уже пользователь
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    
    referral_code = generate_referral_code(user_id)
    referrer_id = None
    
    # Если есть реферальный код
    if referrer_code:
        c.execute("SELECT user_id FROM users WHERE referral_code = ?", (referrer_code,))
        result = c.fetchone()
        if result:
            referrer_id = result[0]
            # Записываем реферала
            c.execute("INSERT INTO referrals (referrer_id, referral_id, date) VALUES (?, ?, ?)",
                     (referrer_id, user_id, joined_date))
    
    c.execute("""INSERT INTO users 
                 (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, first_name, last_name, joined_date, referrer_id, referral_code))
    
    conn.commit()
    conn.close()

# Получаем всех пользователей
def get_all_users():
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name, is_admin, balance, referral_code FROM users")
    users = c.fetchall()
    conn.close()
    return users

# Главное меню
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
        "👥 Реферальная система"
    ]
    buttons = [types.KeyboardButton(service) for service in services]
    markup.add(*buttons)
    return markup

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    # Проверяем реферальный код
    args = message.text.split()
    referrer_code = args[1] if len(args) > 1 else None
    
    save_user(message, referrer_code)
    
    # Красивое приветствие
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

# Реферальная система
@bot.message_handler(func=lambda message: message.text == "👥 Реферальная система")
def referral_system(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    # Получаем реферальный код пользователя
    c.execute("SELECT referral_code, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result:
        bot.send_message(message.chat.id, "❌ Ошибка: реферальный код не найден. Напишите /start заново.")
        conn.close()
        return
    
    referral_code, balance = result
    
    # Считаем рефералов
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    
    # Считаем заработок (сумму всех бонусов)
    c.execute("SELECT SUM(bonus_amount) FROM referrals WHERE referrer_id = ?", (user_id,))
    total_earned = c.fetchone()[0] or 0
    
    # Получаем историю транзакций
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

# Обработка дизайна
@bot.message_handler(func=lambda message: message.text == "🎨 Дизайн")
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
    
    bot.send_message(message.chat.id, 
                    "🎨 <b>Выберите какой Вам нужен дизайн:</b>", 
                    parse_mode='HTML', reply_markup=markup)

# Обработка остальных услуг
user_data = {}

@bot.message_handler(func=lambda message: message.text in [
    "💻 Web-разработка",
    "📈 SEO-продвижение",
    "🎯 Таргет-реклама",
    "🤖 Telegram боты",
    "🔍 Аудит сайта"
])
def handle_service(message):
    user_id = message.from_user.id
    service = message.text
    
    user_data[user_id] = {'service': service, 'step': 'business'}
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "📋 Расскажите о вашем бизнесе:\n"
                          "Чем занимаетесь? Какая у вас ниша?",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_business)

# Обработка кнопок отмены
@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_order(call):
    user_id = int(call.data.split("_")[1])
    
    # Очищаем данные пользователя
    if user_id in user_data:
        del user_data[user_id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Заказ отменён. Возвращайтесь, когда будете готовы!", 
                    reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "cancel_design")
def cancel_design(call):
    # Очищаем данные пользователя
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ Выбор дизайна отменён.", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    # Очищаем данные пользователя
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=main_menu())

# Обработка выбора дизайна
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

# Обработка консультации
@bot.message_handler(func=lambda message: message.text == "💼 Консультация (2.000₽/час)")
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
    
    # Отправляем админам
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
    
    bot.send_message(message.chat.id, 
                    "✅ Запрос на консультацию отправлен! Мы свяжемся с вами в ближайшее время.\n"
                    "Спасибо за обращение в Golden House! 🌟",
                    reply_markup=main_menu())

# Остальные функции обработки заявок
def process_business(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['business'] = message.text
    user_data[user_id]['step'] = 'description'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "💡 Что вы хотите получить?\n"
                          "Опишите задачу максимально подробно:",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_description)

def process_description(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['description'] = message.text
    user_data[user_id]['step'] = 'deadline'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "⏰ Какой дедлайн?\n"
                          "Например: 3 дня, неделя, срочно за 4 часа",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_deadline)

def process_deadline(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['deadline'] = message.text
    user_data[user_id]['step'] = 'budget'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("« Отмена", callback_data=f"cancel_{user_id}"))
    
    msg = bot.send_message(message.chat.id, 
                          "💰 Какой бюджет?\n"
                          "Укажите сумму в рублях:",
                          reply_markup=markup)
    bot.register_next_step_handler(msg, process_budget)

def process_budget(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "❌ Время сессии истекло. Начните заново.", reply_markup=main_menu())
        return
    
    user_data[user_id]['budget'] = message.text
    
    # Сохраняем заявку
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    user_info = bot.get_chat(user_id)
    username = user_info.username or "Нет username"
    
    c.execute("""INSERT INTO requests 
                 (user_id, username, service, sub_service, business_type, description, deadline, budget, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, 
               user_data[user_id]['service'],
               user_data[user_id].get('sub_service', ''),
               user_data[user_id]['business'],
               user_data[user_id]['description'],
               user_data[user_id]['deadline'],
               user_data[user_id]['budget'],
               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Начисляем бонус рефереру (10% от бюджета)
    try:
        budget_amount = int(''.join(filter(str.isdigit, user_data[user_id]['budget'])))
        bonus = int(budget_amount * 0.1)
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer = c.fetchone()
        
        if referrer and referrer[0]:
            referrer_id = referrer[0]
            # Обновляем баланс реферера
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, referrer_id))
            
            # Обновляем запись в рефералах
            c.execute("""UPDATE referrals SET bonus_amount = ? 
                        WHERE referrer_id = ? AND referral_id = ?""", 
                     (bonus, referrer_id, user_id))
            
            # Записываем транзакцию
            c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                         VALUES (?, ?, ?, ?, ?)""",
                      (referrer_id, bonus, 'bonus', 
                       f"Бонус за заказ #{request_id} от @{username}", 
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            conn.commit()
    except:
        pass  # Если не удалось начислить бонус (например, бюджет не число)
    
    # Отправляем админам
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""
🔔 <b>НОВАЯ ЗАЯВКА #{request_id}</b>

👤 <b>Клиент:</b> @{username}
🆔 <b>ID:</b> <code>{user_id}</code>

📋 <b>Услуга:</b> {user_data[user_id]['service']}
"""
            if user_data[user_id].get('sub_service'):
                admin_text += f"📌 <b>Подкатегория:</b> {user_data[user_id]['sub_service']}\n"
            
            admin_text += f"""
💼 <b>О бизнесе:</b> {user_data[user_id]['business']}
📝 <b>Описание:</b> {user_data[user_id]['description']}
⏰ <b>Дедлайн:</b> {user_data[user_id]['deadline']}
💰 <b>Бюджет:</b> {user_data[user_id]['budget']}

⏱ <b>Время:</b> {datetime.now().strftime("%H:%M %d.%m.%Y")}
            """
            bot.send_message(admin_id, admin_text, parse_mode='HTML')
        except:
            pass
    
    bot.send_message(message.chat.id, 
                    "✅ Ваш отклик отправлен администрации на проверку!\n"
                    "Мы свяжемся с вами в ближайшее время.\n\n"
                    "Спасибо, что выбрали Golden House! 🌟",
                    reply_markup=main_menu())
    
    del user_data[user_id]

# АДМИН-ПАНЕЛЬ
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ-панели.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("👑 Назначить админа", callback_data="make_admin"),
        types.InlineKeyboardButton("❌ Разжаловать админа", callback_data="remove_admin"),
        types.InlineKeyboardButton("💰 Начислить баланс", callback_data="add_balance"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        types.InlineKeyboardButton("📨 Заявки", callback_data="requests"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="broadcast"),
        types.InlineKeyboardButton("👥 Все пользователи", callback_data="all_users"),
        types.InlineKeyboardButton("📈 Рефералы (топ)", callback_data="referral_stats"),
        types.InlineKeyboardButton("🔗 Детали рефералов", callback_data="referral_details")
    ]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                    "⚙️ <b>Панель управления Golden House</b>\n\n"
                    "Выберите действие:",
                    parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_admin_callback(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Нет доступа")
        return
    
    if call.data == "make_admin":
        msg = bot.send_message(call.message.chat.id, 
                              "🔑 Напишите ID пользователя, чтобы назначить его администратором:")
        bot.register_next_step_handler(msg, process_make_admin)
    
    elif call.data == "remove_admin":
        if call.from_user.id != OWNER_ID:
            bot.answer_callback_query(call.id, "❌ Только владелец может разжаловать админов")
            return
        
        # Показываем список админов
        admins_list = []
        for admin_id in ADMIN_IDS:
            if admin_id != OWNER_ID:
                try:
                    user = bot.get_chat(admin_id)
                    admins_list.append(f"🆔 <code>{admin_id}</code> - @{user.username or 'Нет username'}")
                except:
                    admins_list.append(f"🆔 <code>{admin_id}</code>")
        
        if not admins_list:
            bot.send_message(call.message.chat.id, "❌ Нет других администраторов")
            return
        
        text = "📋 <b>Администраторы (кроме владельца):</b>\n\n" + "\n".join(admins_list) + \
               "\n\n🔑 Введите ID пользователя, которого нужно разжаловать:"
        
        msg = bot.send_message(call.message.chat.id, text, parse_mode='HTML')
        bot.register_next_step_handler(msg, process_remove_admin)
    
    elif call.data == "add_balance":
        msg = bot.send_message(call.message.chat.id, 
                              "💰 Введите ID пользователя и сумму через пробел\n"
                              "Например: 123456789 1000")
        bot.register_next_step_handler(msg, process_add_balance)
    
    elif call.data == "stats":
        show_stats(call.message)
    
    elif call.data == "requests":
        show_requests(call.message)
    
    elif call.data == "broadcast":
        msg = bot.send_message(call.message.chat.id, 
                              "📢 Введите сообщение для рассылки всем пользователям:")
        bot.register_next_step_handler(msg, process_broadcast)
    
    elif call.data == "all_users":
        show_all_users(call.message)
    
    elif call.data == "referral_stats":
        show_referral_stats(call.message)
    
    elif call.data == "referral_details":
        show_referral_details(call.message)
    
    bot.answer_callback_query(call.id)

def process_make_admin(message):
    try:
        new_admin_id = int(message.text)
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (new_admin_id,))
        conn.commit()
        conn.close()
        
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
        
        bot.send_message(message.chat.id, 
                        f"✅ Пользователь с ID <code>{new_admin_id}</code> назначен администратором!",
                        parse_mode='HTML')
        
        try:
            bot.send_message(new_admin_id, 
                           "👑 Вас назначили администратором Golden House!\n"
                           "Используйте /admin для доступа к панели управления.")
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID (только цифры)")

def process_remove_admin(message):
    try:
        remove_id = int(message.text)
        
        if remove_id == OWNER_ID:
            bot.send_message(message.chat.id, "❌ Нельзя разжаловать владельца!")
            return
        
        if remove_id in ADMIN_IDS:
            ADMIN_IDS.remove(remove_id)
            
            conn = sqlite3.connect('golden_house.db')
            c = conn.cursor()
            c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (remove_id,))
            conn.commit()
            conn.close()
            
            bot.send_message(message.chat.id, 
                            f"✅ Пользователь с ID <code>{remove_id}</code> разжалован!",
                            parse_mode='HTML')
            
            try:
                bot.send_message(remove_id, "❌ Ваши права администратора были отозваны.")
            except:
                pass
        else:
            bot.send_message(message.chat.id, "❌ Этот пользователь не является администратором")
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID")

def process_add_balance(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Неправильный формат. Используйте: ID СУММА")
            return
        
        user_id = int(parts[0])
        amount = int(parts[1])
        
        conn = sqlite3.connect('golden_house.db')
        c = conn.cursor()
        
        # Проверяем, есть ли пользователь
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден")
            conn.close()
            return
        
        # Начисляем баланс
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        
        # Записываем транзакцию
        c.execute("""INSERT INTO transactions (user_id, amount, type, description, date)
                     VALUES (?, ?, ?, ?, ?)""",
                  (user_id, amount, 'admin', f"Начислено администратором", 
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, 
                        f"✅ Пользователю @{user[0]} начислено {amount}₽")
        
        # Уведомляем пользователя
        try:
            bot.send_message(user_id, 
                           f"💰 Вам начислено {amount}₽ на баланс!\n"
                           "Проверьте в разделе 👥 Реферальная система")
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректные числа")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

def show_stats(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    # Общая статистика
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM requests")
    total_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM requests WHERE status = 'new'")
    new_requests = c.fetchone()[0]
    
    # Статистика по рефералам
    c.execute("SELECT COUNT(*) FROM referrals")
    total_refs = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT referrer_id) FROM referrals")
    active_refs = c.fetchone()[0]
    
    c.execute("SELECT SUM(bonus_amount) FROM referrals")
    total_bonus = c.fetchone()[0] or 0
    
    conn.close()
    
    stats_text = f"""
📊 <b>СТАТИСТИКА GOLDEN HOUSE</b>

👥 <b>Всего пользователей:</b> {total_users}
📨 <b>Всего заявок:</b> {total_requests}
🆕 <b>Новых заявок:</b> {new_requests}

👥 <b>Реферальная система:</b>
   • Всего рефералов: {total_refs}
   • Активных рефереров: {active_refs}
   • Всего начислено бонусов: {total_bonus}₽
"""
    
    bot.send_message(message.chat.id, stats_text, parse_mode='HTML')

def show_referral_stats(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    c.execute("""SELECT u.user_id, u.username, u.first_name, 
                        COUNT(r.id) as ref_count, SUM(r.bonus_amount) as total_bonus, u.balance
                 FROM users u
                 LEFT JOIN referrals r ON u.user_id = r.referrer_id
                 GROUP BY u.user_id
                 HAVING ref_count > 0
                 ORDER BY total_bonus DESC
                 LIMIT 20""")
    
    top_referrers = c.fetchall()
    conn.close()
    
    if not top_referrers:
        bot.send_message(message.chat.id, "📊 Пока нет рефералов")
        return
    
    text = "🏆 <b>ТОП РЕФЕРЕРОВ ПО БОНУСАМ</b>\n\n"
    for i, (user_id, username, first_name, ref_count, total_bonus, balance) in enumerate(top_referrers, 1):
        name = first_name or username or f"ID{user_id}"
        text += f"{i}. {name}\n"
        text += f"   👥 Рефералов: {ref_count} | 💰 Бонусов: {total_bonus or 0}₽ | 💵 Баланс: {balance}₽\n"
        text += f"   🆔 <code>{user_id}</code>\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# НОВАЯ ФУНКЦИЯ: Детальная информация о рефералах
def show_referral_details(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    
    # Получаем всех рефереров и их рефералов
    c.execute("""SELECT 
                    r.referrer_id, 
                    u1.username as referrer_username,
                    u1.first_name as referrer_name,
                    r.referral_id,
                    u2.username as referral_username,
                    u2.first_name as referral_name,
                    r.date,
                    r.bonus_amount
                 FROM referrals r
                 JOIN users u1 ON r.referrer_id = u1.user_id
                 JOIN users u2 ON r.referral_id = u2.user_id
                 ORDER BY r.date DESC""")
    
    referrals = c.fetchall()
    conn.close()
    
    if not referrals:
        bot.send_message(message.chat.id, "🔗 Пока нет реферальных связей")
        return
    
    text = "🔗 <b>ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О РЕФЕРАЛАХ</b>\n\n"
    
    current_referrer = None
    for ref in referrals:
        referrer_id, ref_user, ref_name, referral_id, ref_link, ref_link_name, date, bonus = ref
        
        if current_referrer != referrer_id:
            current_referrer = referrer_id
            text += f"\n👤 <b>Реферер:</b> @{ref_user or 'Нет username'} | {ref_name or ''} | ID: <code>{referrer_id}</code>\n"
            text += "└───────────\n"
        
        text += f"   👤 Реферал: @{ref_link or 'Нет username'} | {ref_link_name or ''} | ID: <code>{referral_id}</code>\n"
        text += f"   📅 Дата: {date[:16]}\n"
        text += f"   💰 Бонус: {bonus or 0}₽\n\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')

def show_requests(message):
    conn = sqlite3.connect('golden_house.db')
    c = conn.cursor()
    c.execute("""SELECT id, username, service, sub_service, created_at, status 
                 FROM requests ORDER BY created_at DESC LIMIT 20""")
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        bot.send_message(message.chat.id, "📭 Пока нет заявок")
        return
    
    text = "📨 <b>ПОСЛЕДНИЕ ЗАЯВКИ</b>\n\n"
    for req in requests:
        status_emoji = "🆕" if req[5] == 'new' else "✅"
        sub = f" ({req[3]})" if req[3] else ""
        text += f"{status_emoji} <b>Заявка #{req[0]}</b>\n"
        text += f"👤 @{req[1]}\n"
        text += f"📋 {req[2]}{sub}\n"
        text += f"⏰ {req[4]}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def show_all_users(message):
    users = get_all_users()
    
    if not users:
        bot.send_message(message.chat.id, "👥 Пользователей пока нет")
        return
    
    text = "👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b>\n\n"
    for user in users:
        user_id, username, first_name, last_name, is_admin, balance, ref_code = user
        admin_star = "👑 " if is_admin else ""
        text += f"{admin_star}🆔 <code>{user_id}</code>\n"
        text += f"📱 @{username}\n"
        text += f"👤 {first_name} {last_name or ''}\n"
        text += f"🔗 Реф. код: <code>{ref_code}</code>\n"
        text += f"💰 Баланс: {balance}₽\n"
        text += "—" * 20 + "\n"
    
    # Разбиваем на части
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000], parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, text, parse_mode='HTML')

def process_broadcast(message):
    broadcast_text = message.text
    
    users = get_all_users()
    success = 0
    failed = 0
    
    status_msg = bot.send_message(message.chat.id, 
                                 "📢 Начинаю рассылку... Это может занять некоторое время.")
    
    for user in users:
        user_id = user[0]
        try:
            bot.send_message(user_id, 
                           f"📢 <b>РАССЫЛКА ОТ GOLDEN HOUSE</b>\n\n{broadcast_text}", 
                           parse_mode='HTML')
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    
    bot.edit_message_text(f"✅ Рассылка завершена!\n\n"
                         f"📨 Отправлено: {success}\n"
                         f"❌ Не доставлено: {failed}",
                         message.chat.id,
                         status_msg.message_id)

# Запуск бота
if __name__ == '__main__':
    print("🚀 Запуск бота Golden House...")
    init_db()
    print("✅ Бот Golden House запущен!")
    print(f"👑 Владелец: {OWNER_ID}")
    print(f"👥 Админы: {ADMIN_IDS}")
    print("⏰ Ждём сообщения...")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(3)
