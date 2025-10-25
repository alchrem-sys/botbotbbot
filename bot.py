import json
import asyncio
from datetime import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import nest_asyncio

nest_asyncio.apply()

TOKEN = "8353609125:AAGzwKe0bWujPfrNWGo7T7VnEsixo3NSyFc"
DATA_FILE = "data.json"


def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {"plus": 0, "minus": 0, "balance": 0, "rolled": False}

    save_data(data)

    await update.message.reply_text(
        "Щоб запустити бота — /start.\n"
        "Пиши лише +1; -10; +107; -2.\n"
        "Щоб скинути цифри — /reset.\n\n"
        "Цифри повинні бути зі знаком.\n"
        "Кожного дня о 23:00 за Києвом буде приходити нагадування «Прокрути Альфу 🔁».\n"
        "Пиши «прокрутив», якщо зробив. Якщо ні — через годину нагадаю знову.\n\n"
        "‼️ Писати тільки цифри або «прокрутив», цей бот більше нічого не розуміє 🙂"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()

    if user_id in data:
        data[user_id] = {"plus": 0, "minus": 0, "balance": 0, "rolled": False}
        save_data(data)
        await update.message.reply_text("🔄 Усі дані скинуто!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {"plus": 0, "minus": 0, "balance": 0, "rolled": False}

    text = update.message.text.lower().strip()

    if text.startswith("+") or text.startswith("-"):
        try:
            value = float(text)
            if value > 0:
                data[user_id]["plus"] += value
            else:
                data[user_id]["minus"] += abs(value)

            data[user_id]["balance"] += value
            save_data(data)

            await update.message.reply_text(
                f"✅ Плюс: {round(data[user_id]['plus'], 2)}\n"
                f"❌ Мінус: {round(data[user_id]['minus'], 2)}\n"
                f"💰 Баланс: {round(data[user_id]['balance'], 2)}"
            )

        except ValueError:
            await update.message.reply_text("⚠️ Введи число зі знаком, наприклад: +5 або -2.")

    elif "прокрутив" in text:
        data[user_id]["rolled"] = True
        save_data(data)
        await update.message.reply_text("✅ Зафіксовано — ти прокрутив сьогодні!")

    else:
        await update.message.reply_text("⚠️ Пиши тільки числа або «прокрутив»!")


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    for user_id, user_data in data.items():
        user_data["rolled"] = False  # скидаємо статус щодня
        try:
            await context.bot.send_message(chat_id=int(user_id), text="🌀 Прокрути Альфу 🔁")
        except Exception as e:
            print(f"Не вдалось відправити повідомлення {user_id}: {e}")

    save_data(data)


async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # щоденне нагадування о 23:00 за Києвом
    kyiv_time = time(hour=23, minute=49)
    app.job_queue.run_daily(send_daily_reminders, time=kyiv_time)

    print("🤖 Бот запущено на Railway Worker!")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
