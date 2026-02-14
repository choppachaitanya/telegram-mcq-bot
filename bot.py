import os
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from PyPDF2 import PdfReader

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------- ENV ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send a PDF containing MCQs.\nI will extract and show them."
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Bot is alive.")

# ---------------- PDF HANDLER ----------------
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ Please send a PDF file.")
        return

    file = await document.get_file()
    file_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(file_path)

    try:
        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text.strip():
            await update.message.reply_text("❌ No text found in PDF.")
            return

        # Send extracted text in chunks
        chunk_size = 3500
        for i in range(0, len(text), chunk_size):
            await update.message.reply_text(text[i:i+chunk_size])

    except Exception as e:
        logger.exception("PDF error")
        await update.message.reply_text("❌ Failed to read PDF.")

# ---------------- HEARTBEAT ----------------
async def heartbeat():
    while True:
        logger.info("Heartbeat: bot still alive")
        await asyncio.sleep(20)

# ---------------- MAIN ----------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    asyncio.create_task(heartbeat())

    logger.info("MCQ PDF Bot running")
    await app.run_polling(drop_pending_updates=True, close_loop=False)

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    asyncio.run(main())
