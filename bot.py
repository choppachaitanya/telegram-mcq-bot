import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ MCQ Bot is running successfully.\nSend /test to verify."
    )

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧪 Test OK. Bot is alive.")

def main():
    print("MCQ Bot running")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))

    # 🔴 THIS LINE IS THE KEY (keeps container alive)
    app.run_polling()

if __name__ == "__main__":
    main()
