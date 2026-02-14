import os
import re
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from PyPDF2 import PdfReader

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-1.5-flash"

MAX_MSG_LEN = 3500
AI_CHUNK_WORDS = 1200
# ==========================


def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n".join(text)


def extract_mcqs_from_text(text: str):
    pattern = re.compile(
        r"Q\.\s*\d+.*?(?:Answer\s*[:\-]\s*[A-D])",
        re.DOTALL | re.IGNORECASE,
    )
    return pattern.findall(text)


def chunk_words(text: str, size: int):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i : i + size])


def generate_mcqs_ai(text: str, count: int = 10):
    if not OPENROUTER_API_KEY:
        return []

    prompt = f"""
Generate {count} high-quality MCQs from the content below.

Rules:
- 4 options (A-D)
- Clearly mention Answer
- Exam-oriented
- Avoid repetition

Content:
{text}
"""

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    r = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=60)
    r.raise_for_status()

    output = r.json()["choices"][0]["message"]["content"]
    return re.split(r"\n(?=Q\.)", output)


async def send_long(update: Update, text: str):
    for i in range(0, len(text), MAX_MSG_LEN):
        await update.message.reply_text(text[i : i + MAX_MSG_LEN])


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    pdf_path = "input.pdf"
    await file.download_to_drive(pdf_path)

    await update.message.reply_text("📄 PDF received. Processing...")

    text = extract_text_from_pdf(pdf_path)

    # 1️⃣ Extract MCQs already in PDF
    pdf_mcqs = extract_mcqs_from_text(text)

    if pdf_mcqs:
        await update.message.reply_text(
            f"📘 Found {len(pdf_mcqs)} MCQs in PDF. Sending..."
        )
        for mcq in pdf_mcqs:
            await send_long(update, mcq)

    # 2️⃣ Generate additional MCQs from theory
    ai_mcqs = []
    for chunk in chunk_words(text, AI_CHUNK_WORDS):
        ai_mcqs.extend(generate_mcqs_ai(chunk, count=5))

    if ai_mcqs:
        await update.message.reply_text(
            f"🤖 Generated {len(ai_mcqs)} additional MCQs from theory."
        )
        for mcq in ai_mcqs:
            await send_long(update, mcq)

    total = len(pdf_mcqs) + len(ai_mcqs)
    await update.message.reply_text(f"✅ Done. Generated {total} MCQs.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send a PDF.\nI will:\n"
        "• Extract existing MCQs\n"
        "• Generate new MCQs from theory\n"
        "• Send everything cleanly"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("MCQ Bot running")
    app.run_polling()


if __name__ == "__main__":
    main()
