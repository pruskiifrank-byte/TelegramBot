# bot.py
from telebot import TeleBot, types
import telebot
import os
import random
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
CALLBACK_URL = os.getenv("CALLBACK_URL")

if not API_TOKEN:
    raise RuntimeError("API_TOKEN is not set in env")

bot = TeleBot(API_TOKEN, parse_mode="HTML", threaded=False)

products = {
    "Товар 1": {
        "photo": "images/Огурец.jpg",
        "description": "Описание Товара 1",
        "price": 700,
        "delivery_photo": "delivery/adr1.jpg",
        "delivery_text": "📍 Бульвар 1, дом 7 (тайник возле дерева)",
    },
    "Товар 2": {
        "photo": "images/Огурец2.jpg",
        "description": "Описание Товара 2",
        "price": 700,
        "delivery_photo": "delivery/adr2.jpg",
        "delivery_text": "📍 Центральная 21 — под камнем справа",
    },
    "Товар 3": {
        "photo": "images/Огурец3.jpg",
        "description": "Описание Товара 3",
        "price": 700,
        "delivery_photo": "delivery/adr3.jpg",
        "delivery_text": "📍 Проспект Мира, 15 — под лавкой",
    },
    "Товар 4": {
        "photo": "images/Огурец4.jpg",
        "description": "Описание Товара 4",
        "price": 700,
        "delivery_photo": "delivery/adr4.jpg",
        "delivery_text": "📍 Сквер Гринча, куст №3",
    },
}

delivery_addresses = ["Бульвар Шевченко", "Улица Центральная", "Проспект Мира"]

user_data = {}
orders = {}
last_text_messages = {}


def send_temp_message(chat_id, text, reply_markup=None):
    msg = bot.send_message(chat_id, text, reply_markup=reply_markup)
    if chat_id in last_text_messages:
        try:
            bot.delete_message(chat_id, last_text_messages[chat_id])
        except Exception:
            pass
    last_text_messages[chat_id] = msg.message_id
    return msg


@bot.message_handler(commands=["start"])
def send_welcome(message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "друг"
    user_data[chat_id] = {}
    welcome_text = (
        f"🎄 Привет, {user_name}! 🎁\n"
        "Добро пожаловать к Гринчу!\n"
        "💰 Оплата — Global24\n"
        "Выберите город:"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Запорожье")
    send_temp_message(chat_id, welcome_text)
    bot.send_message(chat_id, "Выберите город:", reply_markup=markup)


@bot.message_handler(commands=["help"])
def help_command(message):
    text = (
        "❓ *Помощь*\n\n"
        "• Выберите товар и оплатите его через Global24\n"
        "• После оплаты получите фото и текст с местом подарка\n"
        "• В случае ошибки напиши в техподдержку\n\n"
        "Команды:\n"
        "/start — перезапустить бота\n"
        "/help — справка\n"
        "Кнопка 'Мои заказы' — показать активные заказы"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "Запорожье")
def city_choice(message):
    chat_id = message.chat.id
    user_data[chat_id]["city"] = message.text
    send_temp_message(chat_id, f"Город выбран: {message.text}")
    send_product_menu(message)


def send_product_menu(message):
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Товар 1", "Товар 2")
    markup.row("Товар 3", "Товар 4")
    markup.row("Мои заказы")  # ← добавили
    bot.send_message(chat_id, "Выберите товар:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text in products.keys())
def product_choice(message):
    chat_id = message.chat.id
    user_data[chat_id]["product"] = message.text
    product = products[message.text]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Выбрать адрес доставки", "Назад")

    try:
        with open(product["photo"], "rb") as p:
            bot.send_photo(
                chat_id,
                p,
                caption=f"{product['description']}\nЦена: {product['price']} грн.",
                reply_markup=markup,
            )
    except FileNotFoundError:
        bot.send_message(
            chat_id,
            f"{product['description']}\nЦена: {product['price']} грн.",
            reply_markup=markup,
        )


@bot.message_handler(func=lambda m: m.text in ["Назад", "Выбрать адрес доставки"])
def address_step(message):
    chat_id = message.chat.id

    if message.text == "Назад":
        send_product_menu(message)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for addr in delivery_addresses:
        markup.add(addr)
    markup.add("⬅️ Вернуться назад")

    send_temp_message(chat_id, "Выберите район доставки:")
    bot.send_message(chat_id, "Адреса:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "⬅️ Вернуться назад")
def back_from_address(message):
    send_product_menu(message)


@bot.message_handler(func=lambda m: m.text in delivery_addresses)
def confirm_order(message):
    chat_id = message.chat.id
    user_data[chat_id]["address"] = message.text

    order_number = random.randint(10000, 99999)
    user_data[chat_id]["order_number"] = order_number
    orders[str(order_number)] = chat_id

    product_name = user_data[chat_id]["product"]
    amount = products[product_name]["price"]
    city = user_data[chat_id]["city"]
    address = message.text

    text = (
        f"✅ Заказ №{order_number} создан!\n\n"
        f"Город: {city}\n"
        f"Район: {address}\n"
        f"Товар: {product_name}\n"
        f"Цена: {amount} грн.\n\n"
        "Нажмите кнопку ниже для оплаты:"
    )

    send_payment_button(chat_id, order_number, product_name, amount, text)


@bot.message_handler(func=lambda m: m.text == "Мои заказы")
def my_orders(message):
    chat_id = message.chat.id

    user_orders = [oid for oid, uid in orders.items() if uid == chat_id]

    if not user_orders:
        bot.send_message(chat_id, "📭 У вас нет активных заказов.")
        return

    text = "📦 Ваши активные заказы:\n\n"
    for oid in user_orders:
        product = user_data.get(chat_id, {}).get("product", "—")
        district = user_data.get(chat_id, {}).get("address", "—")
        text += f"• №{oid} — {product}, район: {district}\n"

    bot.send_message(chat_id, text)


def send_payment_button(chat_id, order_id, product_name, amount, text):
    description = urllib.parse.quote_plus(product_name)
    payment_url = (
        f"https://pay.global24.com.ua/payment?"
        f"amount={amount}&"
        f"order_id={order_id}&"
        f"currency=UAH&"
        f"description={description}&"
        f"callback_url={CALLBACK_URL}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Оплатить", url=payment_url))
    markup.add(
        types.InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}")
    )
    bot.send_message(chat_id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_order_callback(call):
    order_id = call.data.split("_")[1]
    chat_id = orders.get(order_id)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "Да, отменить", callback_data=f"confirm_cancel_{order_id}"
        )
    )
    markup.add(types.InlineKeyboardButton("Нет", callback_data="cancel_no"))

    bot.edit_message_text(
        f"Отменить заказ №{order_id}?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_cancel_"))
def cancel_confirm(call):
    order_id = call.data.split("_")[2]
    chat_id = orders.get(order_id)

    if chat_id:
        orders.pop(order_id, None)
        user_data.pop(chat_id, None)

    bot.edit_message_text(
        f"Заказ №{order_id} отменён.",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.callback_query_handler(func=lambda call: call.data == "cancel_no")
def cancel_no(call):
    bot.answer_callback_query(call.id, "Отмена отменена")


def give_product(chat_id, product_name):
    product = products[product_name]
    bot.send_message(chat_id, product["delivery_text"])
    try:
        with open(product["delivery_photo"], "rb") as photo:
            bot.send_photo(chat_id, photo)
    except FileNotFoundError:
        pass
    # --- АВТООЧИСТКА ЗАВЕРШЁННЫХ ЗАКАЗОВ ---
    order_id = user_data.get(chat_id, {}).get("order_number")

    if order_id:
        orders.pop(str(order_id), None)
        user_data.pop(chat_id, None)

        bot.send_message(
            chat_id,
            f"🧹 Почистим за тобой грязюку… \n" f"Заказ №{order_id} будет удалён!",
        )


def process_update(json_str: str):
    try:
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception:
        pass
