import os
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

# ---------------- TOKEN ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF containing MCQs.\nI will extract the content."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ Please send a PDF file only.")
        return

    file = await document.get_file()
    file_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(file_path)

    try:
        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"

        if not text.strip():
            await update.message.reply_text("❌ No readable text found in PDF.")
            return

        # Telegram limit-safe chunks
        for i in range(0, len(text), 3500):
            await update.message.reply_text(text[i:i+3500])

    except Exception as e:
        logger.exception("PDF read failed")
        await update.message.reply_text("❌ Failed to read PDF.")

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logger.info("MCQ PDF Bot running")

    # 🔥 THIS is the key fix
    app.run_polling(drop_pending_updates=True)

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    main()
