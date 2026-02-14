import logging
import os
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ MCQ Bot is alive.\n\n📄 Send me a PDF to begin."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    await update.message.reply_text(
        f"📘 PDF received: {doc.file_name}\n"
        f"📊 Size: {round(doc.file_size / 1024, 2)} KB\n\n"
        "⚙️ Processing will be added next."
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Unknown command.")

# ---------------- HEARTBEAT ----------------
async def heartbeat():
    while True:
        logger.info("Heartbeat: bot still alive")
        await asyncio.sleep(60)

# ---------------- MAIN (NO asyncio.run) ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # VERY IMPORTANT for polling
    app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.ALL, unknown))

    # heartbeat task
    app.create_task(heartbeat())

    logger.info("MCQ Bot running")

    # 🚨 CRITICAL FIX
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
