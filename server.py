# server.py
from flask import Flask, request
import hmac
import hashlib
import os
from dotenv import load_dotenv
import telebot
import logging

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
MERCHANT_SECRET = os.getenv("SECRET_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com
CALLBACK_URL = os.getenv(
    "CALLBACK_URL"
)  # https://your-app.onrender.com/payment_callback

if not API_TOKEN:
    raise RuntimeError("API_TOKEN not set")

app = Flask(__name__)

# импортируем bot и функции
from bot import process_update, bot, orders, user_data, give_product  # noqa: E402


# Проверка подписи Global24
def verify_signature(string: str, signature: str) -> bool:
    if not MERCHANT_SECRET:
        return False
    key = MERCHANT_SECRET.encode()
    calc = hmac.new(key, string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, signature)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


# Telegram webhook receiver
@app.route("/webhook", methods=["POST"])
def webhook():
    # получаем сырый JSON в виде строки и передаём в bot.process
    raw = request.get_data().decode("utf-8")
    process_update(raw)
    return "OK", 200


# Global24 payment callback
@app.route("/payment_callback", methods=["POST"])
def payment_callback():
    data = request.form
    order_id = data.get("order_id")
    amount = data.get("amount")
    status = data.get("status")
    signature = data.get("signature")

    if not order_id or not signature:
        return "Invalid", 400

    string = f"{order_id}{amount}{status}"

    if not verify_signature(string, signature):
        return "Invalid signature", 400

    chat_id = orders.get(order_id)
    if not chat_id:
        return "Not found", 404

    product_name = user_data[chat_id]["product"]

    if status == "success":
        bot.send_message(chat_id, "🎉 Оплата подтверждена! Готовлю выдачу...")
        give_product(chat_id, product_name)
    else:
        bot.send_message(chat_id, "❌ Оплата не прошла. Попробуйте снова.")

    return "OK", 200


# Optional helper to set webhook manually via browser (one-shot)
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    if not WEBHOOK_URL:
        return "WEBHOOK_URL not set", 400
    bot.remove_webhook()
    ok = bot.set_webhook(url=WEBHOOK_URL + "/webhook")
    return f"Webhook set: {ok}", 200


if __name__ == "__main__":
    # local run
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
