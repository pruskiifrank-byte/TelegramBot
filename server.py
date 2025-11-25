from flask import Flask, request
import hmac
import hashlib
import os
from dotenv import load_dotenv
import telebot

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
MERCHANT_SECRET = os.getenv("SECRET_KEY")

bot = telebot.TeleBot(API_TOKEN, threaded=False)

# Импортируем общие данные и функции из bot.py
from bot import orders, user_data, give_product

app = Flask(__name__)


# ----------------------------- Проверка подписи Global24 -----------------------------
def verify_signature(string, signature):
    key = MERCHANT_SECRET.encode()
    calc = hmac.new(key, string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, signature)


# ----------------------------- Callback от Global24 -----------------------------
@app.route("/payment_callback", methods=["POST"])
def payment_callback():
    data = request.form

    order_id = data.get("order_id")
    amount = data.get("amount")
    status = data.get("status")
    signature = data.get("signature")

    if not order_id or not signature:
        return "Invalid", 400

    # Формируем строку строго в правильном порядке
    string = f"{order_id}{amount}{status}"

    # Проверяем подпись
    if not verify_signature(string, signature):
        return "Invalid signature", 400

    # Ищем пользователя
    chat_id = orders.get(order_id)
    if not chat_id:
        return "Not found", 404

    product_name = user_data[chat_id]["product"]

    # Оплата успешна
    if status == "success":
        bot.send_message(chat_id, "🎉 Оплата подтверждена! Готовлю выдачу...")
        give_product(chat_id, product_name)
    else:
        bot.send_message(chat_id, "❌ Оплата не прошла. Попробуйте снова.")

    return "OK"


# ----------------------------- Установка Webhook -----------------------------
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    webhook_url = os.getenv("WEBHOOK_URL")
    bot.remove_webhook()
    ok = bot.set_webhook(url=webhook_url + "/webhook")
    return f"Webhook set: {ok}"


# ----------------------------- Обработчик Telegram Webhook -----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK"


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


# ----------------------------- Запуск локально -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
