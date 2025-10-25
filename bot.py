import asyncio
import os
import json
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters


# 🔹 Отримує токен із середовища Railway (через Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing! Set it in Railway Variables.")
# 🔹 Файл для збереження даних

DATA_FILE = "data.json"

# --- Load/save data ---
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

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in data:
        data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}
        save_data(data)

    await update.message.reply_text(
        "👋 Привіт! Я бот для фіксації плюсів і мінусів.\n\n"
        "Пиши +5 або -3 щоб оновити баланс.\n"
        "Команда /reset — скинути.\n\n"
        "Кожного дня о 23:00 за Києвом приходить нагадування 🔔 «прокрути альфу».\n"
        "Напиши «прокрутив», щоб підтвердити."
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}
    save_data(data)
    await update.message.reply_text("✅ Баланс скинуто!")

# --- Handle messages ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip().lower()

    # ensure user exists
    if user_id not in data:
        data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}

    if text.startswith(("+", "-")):
        try:
            value = float(text)
            if value > 0:
                data[user_id]["plus"] += value
            else:
                data[user_id]["minus"] += abs(value)

            data[user_id]["balance"] = round(data[user_id]["plus"] - data[user_id]["minus"], 2)
            save_data(data)

            await update.message.reply_text(
                f"✅ Плюс: {round(data[user_id]['plus'], 2)}\n"
                f"❌ Мінус: {round(data[user_id]['minus'], 2)}\n"
                f"💰 Баланс: {round(data[user_id]['balance'], 2)}"
            )
        except ValueError:
            await update.message.reply_text("Пиши лише числа зі знаком (+5 або -3).")

    elif "прокрутив" in text:
        data[user_id]["last_ack"] = datetime.now(timezone.utc).isoformat()
        save_data(data)
        await update.message.reply_text("🔥 Красава, альфа прокручена!")

    else:
        await update.message.reply_text("Пиши лише числа або «прокрутив» 😉")

# --- Daily reminder ---
async def daily_reminder(app: Application):
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)  # 23:00 Kyiv
        if now > target:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        for user_id in list(data.keys()):
            try:
                await app.bot.send_message(chat_id=int(user_id), text="🔔 Прокрути альфу!")
            except Exception as e:
                print(f"⚠️ Не вдалося надіслати {user_id}: {e}")

        # через годину повторне нагадування
        await asyncio.sleep(3600)
        for user_id in list(data.keys()):
            try:
                await app.bot.send_message(chat_id=int(user_id), text="⏰ Якщо ще не прокрутив — саме час!")
            except Exception as e:
                print(f"⚠️ Не вдалося надіслати (2): {e}")

# --- Main ---
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # запуск фонової задачі
    asyncio.create_task(daily_reminder(app))

    print("🤖 Бот запущено на Railway Worker!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()  # тримає процес активним

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 Зупинено вручну.")


