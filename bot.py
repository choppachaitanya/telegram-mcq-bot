import os
import re
import time
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from PyPDF2 import PdfReader

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # set in Railway Variables
MAX_TELEGRAM_MSG = 3500
logging.basicConfig(level=logging.INFO)

# ---------------- HELPERS ----------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    full_text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            full_text.append(clean_text(t))
    return "\n".join(full_text)

def extract_existing_mcqs(text: str):
    pattern = re.compile(
        r"Q\.?\s*\d+.*?Answer\s*[:\-]?\s*[A-D]",
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.findall(text)

def generate_mcqs_from_theory(text: str, limit=50):
    sentences = re.split(r"[.?!]", text)
    mcqs = []
    count = 1

    for s in sentences:
        s = s.strip()
        if len(s) < 80:
            continue
        mcq = (
            f"Q{count}. {s[:120]}?\n"
            f"A) Option 1\nB) Option 2\nC) Option 3\nD) Option 4\n"
            f"Answer: A"
        )
        mcqs.append(mcq)
        count += 1
        if count > limit:
            break

    return mcqs

def send_long_message(chat_id, text, context):
    for i in range(0, len(text), MAX_TELEGRAM_MSG):
        context.bot.send_message(chat_id=chat_id, text=text[i:i+MAX_TELEGRAM_MSG])

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF.\n"
        "I will:\n"
        "1️⃣ Extract MCQs already in the PDF\n"
        "2️⃣ Generate NEW MCQs from theory\n"
        "3️⃣ Send everything cleanly"
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    pdf_path = "input.pdf"
    await file.download_to_drive(pdf_path)

    await update.message.reply_text("📄 PDF received. Processing…")

    text = extract_text_from_pdf(pdf_path)

    existing_mcqs = extract_existing_mcqs(text)
    ai_mcqs = generate_mcqs_from_theory(text, limit=50)

    if existing_mcqs:
        await update.message.reply_text(
            f"📘 Found {len(existing_mcqs)} MCQs in PDF. Sending…"
        )
        send_long_message(update.effective_chat.id, "\n\n".join(existing_mcqs), context)
    else:
        await update.message.reply_text("⚠️ No MCQs found in PDF.")

    if ai_mcqs:
        await update.message.reply_text(
            f"🤖 Generated {len(ai_mcqs)} NEW MCQs from theory."
        )
        send_long_message(update.effective_chat.id, "\n\n".join(ai_mcqs), context)

    os.remove(pdf_path)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logging.info("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
