# server.py
from flask import Flask, request
import os, time
from dotenv import load_dotenv
from bot import bot, orders, give_product, process_update

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TG_WEBHOOK_SECRET = os.getenv("TG_WEBHOOK_SECRET", "grinch_311")

# это секрет, который ты указал в Global24 → HTTPS-уведомления → secret_key
G24_SECRET_KEY = os.getenv("G24_SECRET_KEY")

if not API_TOKEN:
    raise RuntimeError("API_TOKEN not set")

app = Flask(__name__)

# -----------------------------
#           FLOOD
# -----------------------------
user_last_message = {}
FLOOD_SECONDS = float(os.getenv("FLOOD_SECONDS", "0.6"))


def is_flood(chat_id):
    now = time.time()
    last = user_last_message.get(chat_id, 0)
    if now - last < FLOOD_SECONDS:
        return True
    user_last_message[chat_id] = now
    return False


# -----------------------------
#        HOME PAGE
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"


# -----------------------------
#     TELEGRAM WEBHOOK
# -----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != TG_WEBHOOK_SECRET:
        return "Forbidden", 403

    raw_json = request.get_json(force=True, silent=True)

    if raw_json and "message" in raw_json:
        try:
            chat_id = raw_json["message"]["chat"]["id"]
            if is_flood(chat_id):
                return "OK", 200
        except:
            pass

    raw_text = request.get_data().decode("utf-8")
    process_update(raw_text)
    return "OK", 200


# -----------------------------
#   GLOBAL24 PAYMENT CALLBACK
# -----------------------------
@app.route("/payment_callback", methods=["POST"])
def payment_callback():
    print("CALLBACK RECEIVED:", request.form)

    data = request.form

    txID = data.get("txID")
    amount = data.get("amount")
    secret_key = data.get("secret_key")

    # проверяем наличие всех полей
    if not txID or not amount or not secret_key:
        return "Invalid", 400

    # проверка secret_key (единственная защита Global24)
    if secret_key != G24_SECRET_KEY:
        return "Invalid secret", 403

    # ищем заказ по txID
    order_id = None
    for oid, info in orders.items():
        if info.get("txID") == txID:
            order_id = oid
            break

    if not order_id:
        return "Order not found", 404

    order = orders[order_id]

    # проверка суммы
    if str(order.get("amount")) != str(amount):
        return "Wrong amount", 400

    # защита от дублирования
    if order.get("status") == "paid":
        return "Duplicate", 200

    # успешная оплата
    order["status"] = "paid"

    chat_id = order["user_id"]
    product_name = order["product"]

    try:
        bot.send_message(chat_id, "🎉 Оплата подтверждена!")
        give_product(chat_id, product_name)
    except:
        pass

    return "OK", 200


# -----------------------------
#      SET WEBHOOK
# -----------------------------
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    if not WEBHOOK_URL:
        return "WEBHOOK_URL not set", 400

    bot.remove_webhook()

    try:
        ok = bot.set_webhook(
            url=WEBHOOK_URL + "/webhook", secret_token=TG_WEBHOOK_SECRET
        )
    except:
        ok = bot.set_webhook(url=WEBHOOK_URL + "/webhook")

    return f"Webhook set: {ok}", 200


# -----------------------------
#       START SERVER
# -----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
