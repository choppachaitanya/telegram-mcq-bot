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
    document = update.message.document

    if not document:
        return

    await update.message.reply_text(
        f"📘 PDF received: {document.file_name}\n"
        f"📊 Size: {round(document.file_size / 1024, 2)} KB\n\n"
        "⚙️ Processing will be added next."
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ I didn't understand that.\n\n"
        "Use /start or send a PDF."
    )

# ---------------- HEARTBEAT ----------------
async def heartbeat():
    while True:
        logger.info("Heartbeat: bot still alive")
        await asyncio.sleep(60)

# ---------------- MAIN ----------------
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # IMPORTANT: ensure no webhook conflict
    await app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.ALL, unknown))

    logger.info("MCQ Bot running")

    asyncio.create_task(heartbeat())

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
