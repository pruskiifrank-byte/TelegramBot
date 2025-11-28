# server.py
from flask import Flask, request
import hmac, hashlib, os, time, re
from dotenv import load_dotenv
from bot import bot, orders, give_product, process_update

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
MERCHANT_SECRET = os.getenv("MERCHANT_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TG_WEBHOOK_SECRET = os.getenv("TG_WEBHOOK_SECRET", "grinch_311")

if not API_TOKEN:
    raise RuntimeError("API_TOKEN not set")

app = Flask(__name__)

# ----------------------- Антифлуд -----------------------
user_last_message = {}
FLOOD_SECONDS = float(os.getenv("FLOOD_SECONDS", "0.6"))


def is_flood(chat_id):
    now = time.time()
    last = user_last_message.get(chat_id, 0)
    if now - last < FLOOD_SECONDS:
        return True
    user_last_message[chat_id] = now
    return False


# ----------------------- Лог -----------------------
def log_event(reason, data):
    with open("callbacks.log", "a", encoding="utf-8") as f:
        f.write(f"{time.time()} | {reason} | {data}\n")


# ----------------------- Подпись Global24 -----------------------
def verify_signature(string: str, signature: str) -> bool:
    calc = hmac.new(
        MERCHANT_SECRET.encode(), string.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calc, signature)


# ----------------------- Telegram webhook -----------------------
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


# ----------------------- Global24 CALLBACK -----------------------
@app.route("/payment_callback", methods=["POST"])
def payment_callback():
    data = request.form.to_dict()

    print("CALLBACK RECEIVED:", data)
    log_event("received", data)

    # поля от Global24
    amount = data.get("amount")
    desc = data.get("desc") or data.get("comment") or ""
    status = data.get("status", "")
    signature = data.get("signature", "")

    # подпись строится по amount+desc+status
    sign_string = f"{amount}{desc}{status}"
    if not verify_signature(sign_string, signature):
        log_event("bad_signature", data)
        return "Invalid signature", 400

    # ищем order_id в комментарии, например "оплата 54321"
    match = re.search(r"\b(\d{4,6})\b", desc)
    if not match:
        log_event("no_order_in_desc", data)
        return "Order not found in comment", 400

    order_id = match.group(1)

    # сверяем с существующим заказом
    if order_id not in orders:
        log_event("order_not_found", data)
        return "Not found", 404

    order = orders[order_id]
    chat_id = order["user_id"]
    product_name = order["product"]
    expected_amount = str(order["amount"])

    # сумма не совпала
    if str(amount) != expected_amount:
        log_event("wrong_amount", data)
        bot.send_message(
            chat_id,
            f"⚠ Сумма оплаты не совпадает! Ожидалось: {expected_amount}, пришло: {amount}",
        )
        return "Wrong amount", 400

    if status != "success":
        log_event("payment_failed", data)
        bot.send_message(chat_id, "❌ Платёж отклонён банком.")
        return "Not paid", 200

    # всё успешно
    order["status"] = "paid"
    bot.send_message(chat_id, "🎉 Оплата подтверждена!")
    give_product(chat_id, product_name)

    log_event("paid_success", data)
    return "OK", 200


# ----------------------- Установка webhook -----------------------
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
