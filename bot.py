import asyncio
import json
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "YOUR_BOT_TOKEN"
DATA_FILE = "data.json"

# --- Load/save user data ---
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

# --- Start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in data:
        data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}
        save_data(data)

    text = (
        "Щоб запустити бота - /start.\n"
        "Писати лише +1;-10;+107;-2.\n"
        "Щоб скинути цифри — /reset.\n"
        "Цифри повинні бути зі знаком.\n\n"
        "Кожного дня о 20:00 UTC приходить нагадування «прокрути альфу». "
        "Пиши «прокрутив», якщо не написав — через годину прийде ще раз.\n\n"
        "Писати лише цифри або «прокрутив» — бот більше нічого не розуміє 😄"
    )
    await update.message.reply_text(text)

# --- Reset command ---
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}
    save_data(data)
    await update.message.reply_text("✅ Цифри скинуто! Починай спочатку 💪")

# --- Handle messages ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip().lower()

    # ensure user exists
    if user_id not in data:
        data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}

    # number input
    if text.startswith(("+", "-")):
        try:
            value = float(text)
            if value > 0:
                data[user_id]["plus"] += value
            else:
                data[user_id]["minus"] += abs(value)
            data[user_id]["balance"] = data[user_id]["plus"] - data[user_id]["minus"]

            plus = round(data[user_id]["plus"], 2)
            minus = round(data[user_id]["minus"], 2)
            balance = round(data[user_id]["balance"], 2)

            save_data(data)

            await update.message.reply_text(
                f"✅ Плюс: {plus}\n❌ Мінус: {minus}\n💰 Баланс: {balance}"
            )
        except ValueError:
            await update.message.reply_text("Пиши лише числа зі знаком! (+10 або -5)")

    elif "прокрутив" in text:
        data[user_id]["last_ack"] = datetime.now(timezone.utc).isoformat()
        save_data(data)
        await update.message.reply_text("🔥 Красава! Альфа прокручена 💪")

    else:
        await update.message.reply_text("Пиши лише числа або «прокрутив» 😉")

# --- Daily reminder ---
async def daily_reminder(app: Application):
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        wait_time = (target - now).total_seconds()
        await asyncio.sleep(wait_time)

        for user_id in data.keys():
            try:
                await app.bot.send_message(chat_id=int(user_id), text="🔔 Прокрути альфу!")
            except Exception as e:
                print(f"Error sending to {user_id}: {e}")

        await asyncio.sleep(3600)  # через годину нагадування ще раз

# --- Main ---
async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    asyncio.create_task(daily_reminder(app))

    print("🤖 Бот запущено на Railway Worker!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
