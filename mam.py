import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
from datetime import datetime
import sqlite3
import json
import uuid

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота (замените на ваш)
TOKEN = "8235089289:AAFdXJwC8Inr9cFR3BrKjvVLSAmNjtOMmHc"
# Токен CryptoBot (замените на ваш)
CRYPTOBOT_TOKEN = "452823:AAk7KK2bsZnOKRVaBqpTVbeNrlBPXJKQJHJ"

# База данных товаров
PRODUCTS_DB = {
    'split': {
        1: ("Яндекс Сплит - 30.000р", 4),
        2: ("Яндекс Сплит - 50.000р", 5),
        3: ("Яндекс Сплит - 60.000р", 6),
        4: ("Яндекс Сплит - 70.000р", 7),
        5: ("Яндекс Сплит - 100.000р", 10),
        6: ("Яндекс Сплит - 75.000р улучшенный", 15),
        7: ("Яндекс Сплит - 150.000р улучшенный", 30),
        8: ("Яндекс Сплит - 200.000р улучшенный", 40)
    },
    'manuals': {
        1: ("80к р на сером арбитраже трафика", 5),
        2: ("Легкие 100к р в месяц на трафике", 6),
        3: ("300к р в месяц на собственное нейросети", 7)
    },
    'abuse': {
        1: ("Абуз партнерки на звонках", 3),
        2: ("Покупаем поды за 0р", 6),
        3: ("Абуз OZON - бесплатные товары", 9),
        4: ("18к р за круг на промохантинге", 6)
    },
    'business': {
        1: ("🔥ТОП🔥 OpenCase CSgo - игровое казино", 10),
        2: ("Топ dr@iner", 15),
        3: ("SMS BOT", 3),
        4: ("Бот скачивания видео с YouTube", 0.3)
    }
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('dark_shop.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        balance REAL DEFAULT 0,
        total_earned REAL DEFAULT 0,
        purchases_count INTEGER DEFAULT 0,
        referral_id INTEGER,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица покупок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_name TEXT,
        price REAL,
        purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'completed'
    )
    ''')
    
    # Таблица платежей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        currency TEXT DEFAULT 'USD',
        cryptobot_invoice_id TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# Функция для получения или создания пользователя
def get_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('dark_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        conn.commit()
    
    conn.close()
    return user

# Получить баланс пользователя
def get_user_balance(user_id):
    conn = sqlite3.connect('dark_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 0

# Списать средства с баланса
def deduct_from_balance(user_id, amount):
    conn = sqlite3.connect('dark_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    current_balance = cursor.fetchone()[0]
    
    if current_balance >= amount:
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

# Добавить покупку
def add_purchase(user_id, product_name, price):
    conn = sqlite3.connect('dark_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO purchases (user_id, product_name, price)
    VALUES (?, ?, ?)
    ''', (user_id, product_name, price))
    
    cursor.execute('UPDATE users SET purchases_count = purchases_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# Создание инвойса в CryptoBot
async def create_cryptobot_invoice(user_id, amount):
    url = "https://pay.crypt.bot/api/createInvoice"
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Пополнение баланса для пользователя {user_id}",
        "hidden_message": f"Пополнение баланса на {amount}$",
        "paid_btn_name": "callback",
        "paid_btn_url": f"https://t.me/your_bot?start=payment_{user_id}",
        "payload": str(user_id),
        "allow_comments": False,
        "allow_anonymous": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        if response_data.get("ok"):
            return response_data["result"]
        else:
            print(f"Ошибка CryptoBot: {response_data}")
            return None
    except Exception as e:
        print(f"Ошибка при создании инвойса: {e}")
        return None

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username, user.first_name, user.last_name)
    
    # Главное меню с клавиатурой - ПЕРВАЯ СТРОЧКА: Профиль, Товары; ВТОРАЯ СТРОЧКА: Информация
    keyboard = [
        [KeyboardButton("👤 Профиль"), KeyboardButton("🛒 Товары")],
        [KeyboardButton("ℹ️ Информация")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        "🎉 Добро пожаловать в DARK SHOP!\n\n"
        "⚡ Твой надежный партнер в мире эксклюзивных решений\n"
        "🔒 Анонимность • Безопасность • Качество\n\n"
        "👇 Выберите раздел в меню ниже:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )

# Обработчик кнопки "Профиль"
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('dark_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT balance, purchases_count, total_earned, registration_date 
    FROM users WHERE user_id = ?
    ''', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        balance, purchases_count, total_earned, reg_date = user_data
        
        # Клавиатура для профиля
        keyboard = [
            [InlineKeyboardButton("💳 Пополнить баланс", callback_data='deposit')],
            [InlineKeyboardButton("📦 Мои покупки", callback_data='my_purchases')],
            [InlineKeyboardButton("👥 Реферальная система", callback_data='referral')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        profile_text = (
            "👤 ВАШ ПРОФИЛЬ\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📅 Регистрация: {reg_date.split()[0]}\n"
            f"💰 Баланс: <b>{balance}$</b>\n"
            f"🛒 Покупок: <b>{purchases_count}</b>\n"
            f"👥 Заработано с рефералов: <b>{total_earned}$</b>\n\n"
            "💡 Используйте кнопки ниже для управления профилем"
        )
        
        await update.message.reply_text(
            profile_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# Обработчик кнопки "Товары"
async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products_keyboard = [
        [InlineKeyboardButton("🔵 Яндекс Сплит", callback_data='category_split')],
        [InlineKeyboardButton("📄 Мануалы", callback_data='category_manuals')],
        [InlineKeyboardButton("⚡ Абузы", callback_data='category_abuse')],
        [InlineKeyboardButton("🚀 Готовый бизнес", callback_data='category_business')]
    ]
    reply_markup = InlineKeyboardMarkup(products_keyboard)
    
    products_text = (
        "🛒 КАТАЛОГ ТОВАРОВ\n\n"
        "🎯 Выберите категорию:\n\n"
        "• 🔵 Яндекс Сплит - премиум аккаунты\n"
        "• 📄 Мануалы - обучающие материалы\n"
        "• ⚡ Абузы - специальные методы\n"
        "• 🚀 Готовый бизнес - готовые решения\n\n"
        "💡 Нажмите на интересующую категорию"
    )
    
    await update.message.reply_text(
        products_text,
        reply_markup=reply_markup
    )

# Обработчик кнопки "Информация"
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_text = (
        "ℹ️ О DARK SHOP\n\n"
        "🖤 ТВОЙ ТЕЛЕГРАМ-ЧЕРНЫЙ РЫНОК БЕЗ ПРАВИЛ\n\n"
        "🎯 Чем торгуем?\n"
        "• 🔵 Яндекс Сплит - эксклюзивные аккаунты\n"
        "• 📄 Мануалы - проверенные методики\n"
        "• ⚡ Абузы - специальные решения\n"
        "• 🚀 Готовый бизнес - готовые проекты\n\n"
        "🔒 Почему мы?\n"
        "• 🕶️ Полная анонимность\n"
        "• 💰 Криптовалютные платежи (USDT, BTC, ETH)\n"
        "• ⚡ Мгновенная доставка\n"
        "• 🛡️ Гарантия качества\n\n"
        "🤝 Поддержка: @dark_shop_support_bot\n\n"
        "💡 Мы ценим каждого клиента!"
    )
    
    await update.message.reply_text(info_text)

# Обработчик ввода суммы для пополнения
async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        amount = float(text)
        if amount < 1:
            await update.message.reply_text(
                "❌ Минимальная сумма пополнения - 1$\n"
                "Введите сумму еще раз:"
            )
            return
        
        if amount > 1000:
            await update.message.reply_text(
                "❌ Максимальная сумма пополнения - 1000$\n"
                "Введите сумму еще раз:"
            )
            return
        
        # Создаем инвойс в CryptoBot
        invoice = await create_cryptobot_invoice(user_id, amount)
        
        if invoice:
            payment_url = invoice["pay_url"]
            invoice_id = invoice["invoice_id"]
            
            # Сохраняем информацию о платеже в БД
            conn = sqlite3.connect('dark_shop.db')
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (user_id, amount, cryptobot_invoice_id)
            VALUES (?, ?, ?)
            ''', (user_id, amount, invoice_id))
            conn.commit()
            conn.close()
            
            payment_text = (
                f"💳 ОПЛАТА {amount}$\n\n"
                f"🔗 Ссылка для оплаты:\n{payment_url}\n\n"
                "📋 Инструкция:\n"
                "1. Нажмите на ссылку выше\n"
                "2. Оплатите через CryptoBot\n"
                "3. Баланс зачислится автоматически\n\n"
                "⏱️ Обычно зачисление занимает 2-5 минут\n"
                "🔄 Для проверки статуса нажмите кнопку ниже\n\n"
                "❓ Проблемы? Пишите: @dark_shop_support_bot"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f'check_payment_{invoice_id}')],
                [InlineKeyboardButton("💳 Пополнить еще", callback_data='deposit')],
                [InlineKeyboardButton("🔙 В профиль", callback_data='back_to_profile')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                payment_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при создании платежа\n"
                "Попробуйте позже или обратитесь в поддержку: @dark_shop_support_bot"
            )
            
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат суммы\n"
            "Введите число (например: 10 или 10.5):"
        )

# Обработчик покупки товара
async def handle_product_purchase(query, product_type, product_id, price, product_name):
    user_id = query.from_user.id
    user_balance = get_user_balance(user_id)
    
    if user_balance >= price:
        # Списание средств
        if deduct_from_balance(user_id, price):
            # Добавление покупки
            add_purchase(user_id, product_name, price)
            
            purchase_text = (
                f"✅ ПОКУПКА УСПЕШНА!\n\n"
                f"🎁 Товар: {product_name}\n"
                f"💵 Стоимость: {price}$\n"
                f"💰 Остаток на балансе: {user_balance - price}$\n\n"
                f"📦 Ваш товар:\n"
                f"Данные будут отправлены в течение 5 минут\n\n"
                f"❓ Вопросы? @dark_shop_support_bot"
            )
            
            await query.message.edit_text(
                purchase_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 К товарам", callback_data='back_to_products')],
                    [InlineKeyboardButton("👤 В профиль", callback_data='back_to_profile')]
                ])
            )
        else:
            await query.message.edit_text(
                "❌ Ошибка при списании средств\n"
                "Обратитесь в поддержку: @dark_shop_support_bot",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data=f'category_{product_type}')]
                ])
            )
    else:
        await query.message.edit_text(
            f"❌ НЕДОСТАТОЧНО СРЕДСТВ\n\n"
            f"💵 Стоимость товара: {price}$\n"
            f"💰 Ваш баланс: {user_balance}$\n\n"
            f"Пополните баланс и повторите попытку",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Пополнить баланс", callback_data='deposit')],
                [InlineKeyboardButton("🔙 Назад", callback_data=f'category_{product_type}')]
            ])
        )

# Обработчик callback queries
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'deposit':
        # Пополнение баланса через CryptoBot
        user_id = query.from_user.id
        
        deposit_text = (
            "💳 ПОПОЛНЕНИЕ БАЛАНСА\n\n"
            "💰 Выберите сумму или введите свою:\n"
            "• Минимальная сумма: 1$\n"
            "• Максимальная сумма: 1000$\n\n"
            "⚡ Быстрые кнопки:\n"
            "Или просто напишите боту нужную сумму"
        )
        
        deposit_keyboard = [
            [InlineKeyboardButton("5$", callback_data='deposit_5'),
             InlineKeyboardButton("10$", callback_data='deposit_10'),
             InlineKeyboardButton("20$", callback_data='deposit_20')],
            [InlineKeyboardButton("50$", callback_data='deposit_50'),
             InlineKeyboardButton("100$", callback_data='deposit_100'),
             InlineKeyboardButton("200$", callback_data='deposit_200')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_profile')]
        ]
        reply_markup = InlineKeyboardMarkup(deposit_keyboard)
        
        await query.message.edit_text(
            deposit_text,
            reply_markup=reply_markup
        )
    
    elif data.startswith('deposit_'):
        amount = float(data.split('_')[1])
        user_id = query.from_user.id
        
        # Создаем инвойс в CryptoBot
        invoice = await create_cryptobot_invoice(user_id, amount)
        
        if invoice:
            payment_url = invoice["pay_url"]
            invoice_id = invoice["invoice_id"]
            
            # Сохраняем информацию о платеже в БД
            conn = sqlite3.connect('dark_shop.db')
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (user_id, amount, cryptobot_invoice_id)
            VALUES (?, ?, ?)
            ''', (user_id, amount, invoice_id))
            conn.commit()
            conn.close()
            
            payment_text = (
                f"💳 ОПЛАТА {amount}$\n\n"
                f"🔗 Ссылка для оплаты:\n<code>{payment_url}</code>\n\n"
                "📋 Инструкция:\n"
                "1. Нажмите на ссылку выше\n"
                "2. Оплатите через CryptoBot\n"
                "3. Баланс зачислится автоматически\n\n"
                "⏱️ Обычно зачисление занимает 2-5 минут\n"
                "🔄 Для проверки статуса нажмите кнопку ниже\n\n"
                "❓ Проблемы? Пишите: @dark_shop_support_bot"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f'check_payment_{invoice_id}')],
                [InlineKeyboardButton("💳 Пополнить еще", callback_data='deposit')],
                [InlineKeyboardButton("🔙 Назад", callback_data='back_to_profile')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                payment_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.message.edit_text(
                "❌ Ошибка при создании платежа\n"
                "Попробуйте позже или обратитесь в поддержку: @dark_shop_support_bot",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data='deposit')]
                ])
            )
    
    elif data == 'category_split':
        # Товары Яндекс Сплит
        split_keyboard = [
            [InlineKeyboardButton("Яндекс Сплит - 30.000р (4$)", callback_data='buy_split_1')],
            [InlineKeyboardButton("Яндекс Сплит - 50.000р (5$)", callback_data='buy_split_2')],
            [InlineKeyboardButton("Яндекс Сплит - 60.000р (6$)", callback_data='buy_split_3')],
            [InlineKeyboardButton("Яндекс Сплит - 70.000р (7$)", callback_data='buy_split_4')],
            [InlineKeyboardButton("Яндекс Сплит - 100.000р (10$)", callback_data='buy_split_5')],
            [InlineKeyboardButton("Яндекс Сплит - 75.000р улучшенный (15$)", callback_data='buy_split_6')],
            [InlineKeyboardButton("Яндекс Сплит - 150.000р улучшенный (30$)", callback_data='buy_split_7')],
            [InlineKeyboardButton("Яндекс Сплит - 200.000р улучшенный (40$)", callback_data='buy_split_8')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_products')]
        ]
        reply_markup = InlineKeyboardMarkup(split_keyboard)
        
        await query.message.edit_text(
            "🔵 Яндекс Сплит - аккаунты\n\n"
            "Выберите товар для покупки:",
            reply_markup=reply_markup
        )
    
    elif data == 'category_manuals':
        # Мануалы
        manuals_keyboard = [
            [InlineKeyboardButton("80к р на сером арбитраже трафика (5$)", callback_data='buy_manuals_1')],
            [InlineKeyboardButton("Легкие 100к р в месяц на трафике (6$)", callback_data='buy_manuals_2')],
            [InlineKeyboardButton("300к р в месяц на собственное нейросети (7$)", callback_data='buy_manuals_3')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_products')]
        ]
        reply_markup = InlineKeyboardMarkup(manuals_keyboard)
        
        await query.message.edit_text(
            "📄 Мануалы - обучающие материалы\n\n"
            "Выберите мануал для покупки:",
            reply_markup=reply_markup
        )
    
    elif data == 'category_abuse':
        # Абузы
        abuse_keyboard = [
            [InlineKeyboardButton("Абуз партнерки на звонках (3$)", callback_data='buy_abuse_1')],
            [InlineKeyboardButton("Покупаем поды за 0р (6$)", callback_data='buy_abuse_2')],
            [InlineKeyboardButton("Абуз OZON - бесплатные товары (9$)", callback_data='buy_abuse_3')],
            [InlineKeyboardButton("18к р за круг на промохантинге (6$)", callback_data='buy_abuse_4')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_products')]
        ]
        reply_markup = InlineKeyboardMarkup(abuse_keyboard)
        
        await query.message.edit_text(
            "⚡ Абузы - специальные методы\n\n"
            "Выберите абуз для покупки:",
            reply_markup=reply_markup
        )
    
    elif data == 'category_business':
        # Готовый бизнес
        business_keyboard = [
            [InlineKeyboardButton("🔥ТОП🔥 OpenCase CSgo - игровое казино (10$)", callback_data='buy_business_1')],
            [InlineKeyboardButton("Топ dr@iner (15$)", callback_data='buy_business_2')],
            [InlineKeyboardButton("SMS BOT (3$)", callback_data='buy_business_3')],
            [InlineKeyboardButton("Бот скачивания видео с YouTube (0.3$)", callback_data='buy_business_4')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_products')]
        ]
        reply_markup = InlineKeyboardMarkup(business_keyboard)
        
        await query.message.edit_text(
            "🚀 Готовый бизнес - готовые решения\n\n"
            "Выберите товар для покупки:",
            reply_markup=reply_markup
        )
    
    elif data.startswith('buy_'):
        # Обработка покупки товара
        parts = data.split('_')
        if len(parts) == 3:
            product_type = parts[1]
            product_id = int(parts[2])
            
            if product_type in PRODUCTS_DB and product_id in PRODUCTS_DB[product_type]:
                product_name, price = PRODUCTS_DB[product_type][product_id]
                await handle_product_purchase(query, product_type, product_id, price, product_name)
    
    elif data == 'back_to_products':
        # Возврат к категориям товаров
        products_keyboard = [
            [InlineKeyboardButton("🔵 Яндекс Сплит", callback_data='category_split')],
            [InlineKeyboardButton("📄 Мануалы", callback_data='category_manuals')],
            [InlineKeyboardButton("⚡ Абузы", callback_data='category_abuse')],
            [InlineKeyboardButton("🚀 Готовый бизнес", callback_data='category_business')]
        ]
        reply_markup = InlineKeyboardMarkup(products_keyboard)
        
        await query.message.edit_text(
            "🛒 КАТАЛОГ ТОВАРОВ\n\n"
            "🎯 Выберите категорию:",
            reply_markup=reply_markup
        )
    
    elif data == 'back_to_profile':
        # Возврат к профилю
        user_id = query.from_user.id
        conn = sqlite3.connect('dark_shop.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT balance, purchases_count, total_earned, registration_date 
        FROM users WHERE user_id = ?
        ''', (user_id,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            balance, purchases_count, total_earned, reg_date = user_data
            
            keyboard = [
                [InlineKeyboardButton("💳 Пополнить баланс", callback_data='deposit')],
                [InlineKeyboardButton("📦 Мои покупки", callback_data='my_purchases')],
                [InlineKeyboardButton("👥 Реферальная система", callback_data='referral')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            profile_text = (
                "👤 ВАШ ПРОФИЛЬ\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📅 Регистрация: {reg_date.split()[0]}\n"
                f"💰 Баланс: <b>{balance}$</b>\n"
                f"🛒 Покупок: <b>{purchases_count}</b>\n"
                f"👥 Заработано с рефералов: <b>{total_earned}$</b>"
            )
            
            await query.message.edit_text(profile_text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif data == 'my_purchases':
        user_id = query.from_user.id
        conn = sqlite3.connect('dark_shop.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT product_name, price, purchase_date FROM purchases WHERE user_id = ?', (user_id,))
        purchases = cursor.fetchall()
        conn.close()
        
        if purchases:
            purchases_text = "📦 Ваши покупки:\n\n"
            for purchase in purchases:
                purchases_text += f"🛒 {purchase[0]} - {purchase[1]}$ ({purchase[2]})\n"
        else:
            purchases_text = "У вас еще нет покупок."
        
        await query.message.reply_text(purchases_text)
    
    elif data == 'referral':
        user_id = query.from_user.id
        referral_link = f"https://t.me/your_bot?start=ref_{user_id}"
        
        await query.message.reply_text(
            f"👥 Реферальная система\n\n"
            f"Приводи друзей и получай 30% от их покупок!\n\n"
            f"Ваша реферальная ссылка:\n{referral_link}\n\n"
            f"Ваш ID для рефералов: {user_id}"
        )

# Основная функция
def main():
    # Инициализация базы данных
    init_db()
    
    # Создание Application
    application = Application.builder().token(TOKEN).build()
    
    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Text(["👤 Профиль"]), profile))
    application.add_handler(MessageHandler(filters.Text(["🛒 Товары"]), products))
    application.add_handler(MessageHandler(filters.Text(["ℹ️ Информация"]), info))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount_input))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запуск бота
    print("🤖 Бот запущен и готов к работе!")
    print("💡 Ожидаю сообщения...")
    application.run_polling()

if __name__ == '__main__':
    main()