import asyncio
import os
import json
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# -------------------- Налаштування --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Токен не встановлений!")
    exit(1)

ADMIN_ID = 868931721  # <- твій Telegram ID
DATA_FILE = "data.json"

# -------------------- Збереження даних --------------------
data_lock = asyncio.Lock()

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

data = load_data()

async def save_data():
    async with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# -------------------- Команди --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in data:
        data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}
        await save_data()
    await update.message.reply_text(
        "👋 Привіт, Я бот для фіксації плюсів і мінусів на альфі.\n\n"
        "Пиши типу +5 або -3, щоб оновити баланс.\n"
        "Команда /reset — скинути баланс.\n\n"
        "Коли рестартаю бот, числа не запам'ятовуються.\n"
        "Щодня о 23:00 за Києвом приходить нагадування 🔔 «прокрути альфу».\n"
        "Напиши «прокрутив», щоб підтвердити.\n\n"
        "Якщо будуть можливі перезапуски - я вам повідомлю і щоб отримувати нагадування знову - вам потрібно буде натиснути /start знову. (25$ на сервер це дохуя)\n\n"
        "Знайшли помилку? - @l1oxsha"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}
    await save_data()
    await update.message.reply_text("✅ Баланс скинуто!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip().lower()

    if user_id not in data:
        data[user_id] = {"plus": 0.0, "minus": 0.0, "balance": 0.0, "last_ack": None}

    if text.startswith(("+", "-")):
        try:
            value = float(text.replace(" ", ""))
            if value > 0:
                data[user_id]["plus"] += value
            else:
                data[user_id]["minus"] += abs(value)

            data[user_id]["balance"] = round(data[user_id]["plus"] - data[user_id]["minus"], 2)
            await save_data()

            await update.message.reply_text(
                f"✅ Плюс: {round(data[user_id]['plus'], 2)}\n"
                f"❌ Мінус: {round(data[user_id]['minus'], 2)}\n"
                f"💰 Баланс: {round(data[user_id]['balance'], 2)}"
            )
        except ValueError:
            await update.message.reply_text("Пиши лише числа зі знаком (+5 або -3).")
    elif "прокрутив" in text:
        data[user_id]["last_ack"] = datetime.now(timezone.utc).isoformat()
        await save_data()
        await update.message.reply_text("🔥 Красава, альфа прокручена")
    else:
        await update.message.reply_text("Пиши лише числа або «прокрутив» 😉")

# -------------------- Адмін-розсилка --------------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Тільки адміністратор може використовувати цю команду.")
        return

    if not context.args:
        await update.message.reply_text("❌ Вкажи повідомлення для розсилки: /broadcast Текст")
        return

    message = " ".join(context.args)
    success, fail = 0, 0

    for uid in data.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            success += 1
        except Exception as e:
            print(f"⚠️ Не вдалося надіслати {uid}: {e}")
            fail += 1

    await update.message.reply_text(f"✅ Розсилка завершена! Успішно: {success}, Не вдалося: {fail}")

# -------------------- Щоденні нагадування --------------------
async def daily_reminder(app: Application):
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)  # 23:00 Київ
        if now > target:
            target += timedelta(days=1)

        await asyncio.sleep((target - now).total_seconds())

        for user_id in data.keys():
            try:
                await app.bot.send_message(chat_id=int(user_id), text="🔔 Прокрути альфу!")
            except Exception as e:
                print(f"⚠️ Не вдалося надіслати {user_id}: {e}")

        # Друге нагадування через годину
        await asyncio.sleep(3600)
        for user_id in data.keys():
            try:
                await app.bot.send_message(chat_id=int(user_id), text="⏰ Якщо ще не прокрутив — саме час!")
            except Exception as e:
                print(f"⚠️ Не вдалося надіслати (2) {user_id}: {e}")

# -------------------- Основна функція --------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def start_reminder(app: Application):
        asyncio.create_task(daily_reminder(app))

    app.post_init = start_reminder

    print("🤖 Бот запущено!")
    app.run_polling()

if __name__ == "__main__":
    main()


