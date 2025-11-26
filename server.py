# server.py
from flask import Flask, request
import hmac, hashlib, os
from dotenv import load_dotenv
from bot import bot, orders, give_product

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
MERCHANT_SECRET = os.getenv("SECRET_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not API_TOKEN:
    raise RuntimeError("API_TOKEN not set")

app = Flask(__name__)

from bot import process_update


# ————— ЛОГИРОВАНИЕ ПОВТОРНЫХ CALLBACK —————

def log_event(order_id, reason, data):
    with open("callbacks.log", "a", encoding="utf-8") as f:
        f.write(f"{order_id} | {reason} | {data}\n")


# ————— Проверка подписи —————

def verify_signature(string: str, signature: str) -> bool:
    if not MERCHANT_SECRET:
        return False

    calc = hmac.new(
        MERCHANT_SECRET.encode(),
        string.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(calc, signature)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data().decode("utf-8")
    process_update(raw)
    return "OK", 200


@app.route("/payment_callback", methods=["POST"])
def payment_callback():
    data = request.form

    order_id = data.get("order_id")
    amount = data.get("amount")
    status = data.get("status")
    signature = data.get("signature")

    if not order_id or not signature:
        return "Invalid", 400

    # ——— Проверка подписи ———
    string = f"{order_id}{amount}{status}"

    if not verify_signature(string, signature):
        log_event(order_id, "bad_signature", dict(data))
        return "Invalid signature", 400

    # ——— Проверка, что заказ существует ———
    if order_id not in orders:
        log_event(order_id, "order_not_found", dict(data))
        return "Not found", 404

    order = orders[order_id]

    # ——— Заказ уже оплачен ———
    if order["status"] == "paid":
        log_event(order_id, "duplicate_callback", dict(data))
        return "Duplicate", 200

    # ——— Проверка суммы ———
    if str(order["amount"]) != str(amount):
        log_event(order_id, "wrong_amount", dict(data))
        return "Wrong amount", 400

    chat_id = order["user_id"]
    product_name = order["product"]

    # ——— Успешная оплата ———
    if status == "success":
        order["status"] = "paid"

        bot.send_message(chat_id, "🎉 Оплата подтверждена!")
        give_product(chat_id, product_name)

    else:
        bot.send_message(chat_id, "❌ Оплата не прошла.")

    return "OK", 200


@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    ok = bot.set_webhook(url=WEBHOOK_URL + "/webhook")
    return f"Webhook set: {ok}", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
