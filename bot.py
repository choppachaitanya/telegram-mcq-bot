import os
import re
import asyncio
import requests
from PyPDF2 import PdfReader

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

MAX_TELEGRAM_CHARS = 3500
# ============================================


# ---------- PDF TEXT EXTRACTION ----------
def extract_pdf_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    full_text = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text.append(text)

    return "\n".join(full_text)


# ---------- MCQ EXTRACTION FROM PDF ----------
def extract_existing_mcqs(text: str) -> list[str]:
    mcqs = []
    blocks = re.split(r"\n\s*Q[\.\)]?\s*\d+", text, flags=re.IGNORECASE)

    for block in blocks:
        if "A)" in block and "B)" in block:
            cleaned = block.strip()
            if len(cleaned) > 40:
                mcqs.append(cleaned)

    return mcqs


# ---------- AI MCQ GENERATION ----------
def generate_mcqs_from_theory(theory_text: str, count: int = 10) -> str:
    prompt = f"""
Create {count} high-quality exam-oriented MCQs from the following content.
Format strictly as:

Q. Question?
A) option
B) option
C) option
D) option
Answer: X

Content:
{theory_text[:6000]}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://railway.app",
        "X-Title": "MCQ Bot"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4
    }

    r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()

    return r.json()["choices"][0]["message"]["content"]


# ---------- SAFE MESSAGE SENDER ----------
async def send_long_message(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE):
    for i in range(0, len(text), MAX_TELEGRAM_CHARS):
        await context.bot.send_message(chat_id, text[i:i + MAX_TELEGRAM_CHARS])
        await asyncio.sleep(0.4)


# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF.\n"
        "I will:\n"
        "1️⃣ Extract MCQs already in the PDF\n"
        "2️⃣ Generate MORE MCQs from theory\n"
        "3️⃣ Send everything in clean batches"
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    pdf_file = await update.message.document.get_file()
    pdf_path = "input.pdf"
    await pdf_file.download_to_drive(pdf_path)

    await update.message.reply_text("📖 Reading PDF...")

    text = extract_pdf_text(pdf_path)

    # Existing MCQs
    existing_mcqs = extract_existing_mcqs(text)
    await update.message.reply_text(f"📘 Found {len(existing_mcqs)} MCQs in PDF")

    for i, mcq in enumerate(existing_mcqs, start=1):
        await send_long_message(chat_id, f"📘 MCQ {i}\n{mcq}", context)

    # AI MCQs
    await update.message.reply_text("🤖 Generating additional MCQs from theory...")
    ai_mcqs = generate_mcqs_from_theory(text, count=20)

    await send_long_message(chat_id, "🤖 AI Generated MCQs\n\n" + ai_mcqs, context)

    await update.message.reply_text("✅ Done!")


# ---------- MAIN ----------
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("MCQ Bot running")
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
