import asyncio
import os
from datetime import datetime, timedelta, timezone
import asyncpg
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "868931721"))

if not BOT_TOKEN or not DATABASE_URL:
    print("❌ Не встановлені BOT_TOKEN або DATABASE_URL!")
    exit(1)

# --- Ініціалізація БД ---
async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            plus DOUBLE PRECISION DEFAULT 0,
            minus DOUBLE PRECISION DEFAULT 0,
            balance DOUBLE PRECISION DEFAULT 0,
            last_ack TIMESTAMP
        )
    """)
    await conn.close()

# --- Команди ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
    if not user:
        await conn.execute("INSERT INTO users(user_id) VALUES($1)", user_id)
    await conn.close()
    await update.message.reply_text(
        "👋 Привіт! Я бот для фіксації плюсів і мінусів.\n\n"
        "Пиши +5 або -3, щоб оновити баланс.\n"
        "Команда /reset — скинути баланс.\n\n"
        "Щодня о 23:00 за Києвом приходить нагадування 🔔 «прокрути альфу».\n"
        "Напиши «прокрутив», щоб підтвердити."
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        UPDATE users
        SET plus=0, minus=0, balance=0, last_ack=NULL
        WHERE user_id=$1
    """, user_id)
    await conn.close()
    await update.message.reply_text("✅ Баланс скинуто!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
    if not user:
        await conn.execute("INSERT INTO users(user_id) VALUES($1)", user_id)
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

    if text.startswith(("+", "-")):
        try:
            value = float(text)
            plus = user["plus"]
            minus = user["minus"]
            if value > 0:
                plus += value
            else:
                minus += abs(value)
            balance = round(plus - minus, 2)
            await conn.execute("""
                UPDATE users
                SET plus=$1, minus=$2, balance=$3
                WHERE user_id=$4
            """, plus, minus, balance, user_id)
            await update.message.reply_text(
                f"✅ Плюс: {plus}\n❌ Мінус: {minus}\n💰 Баланс: {balance}"
            )
        except ValueError:
            await update.message.reply_text("Пиши лише числа зі знаком (+5 або -3).")
    elif "прокрутив" in text:
        last_ack = datetime.now(timezone.utc)
        await conn.execute("""
            UPDATE users
            SET last_ack=$1
            WHERE user_id=$2
        """, last_ack, user_id)
        await update.message.reply_text("🔥 Красава, альфа прокручена!")
    else:
        await update.message.reply_text("Пиши лише числа або «прокрутив» 😉")
    await conn.close()

# --- Broadcast ---
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Тільки адміністратор може використовувати цю команду.")
        return
    if not context.args:
        await update.message.reply_text("❌ Вкажи повідомлення: /broadcast Текст")
        return
    message = " ".join(context.args)
    conn = await asyncpg.connect(DATABASE_URL)
    users = await conn.fetch("SELECT user_id FROM users")
    success, fail = 0, 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["user_id"], text=message)
            success += 1
        except:
            fail += 1
    await update.message.reply_text(f"✅ Розсилка завершена! Успішно: {success}, Не вдалося: {fail}")
    await conn.close()

# --- Daily reminder ---
async def daily_reminder(app: Application):
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=20, minute=0, second=0, microsecond=0)  # 23:00 Київ
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        conn = await asyncpg.connect(DATABASE_URL)
        users = await conn.fetch("SELECT user_id FROM users")
        for u in users:
            try:
                await app.bot.send_message(chat_id=u["user_id"], text="🔔 Прокрути альфу!")
            except:
                pass
        await asyncio.sleep(3600)
        for u in users:
            try:
                await app.bot.send_message(chat_id=u["user_id"], text="⏰ Якщо ще не прокрутив — саме час!")
            except:
                pass
        await conn.close()

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def start_tasks(app: Application):
        await init_db()
        asyncio.create_task(daily_reminder(app))

    app.post_init = start_tasks
    print("🤖 Бот з PostgreSQL запущено на Railway!")
    app.run_polling()

if __name__ == "__main__":
    main()

