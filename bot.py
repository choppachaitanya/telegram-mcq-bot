import os
import re
import httpx
import logging
from pypdf import PdfReader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ───────────────── CONFIG ─────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY missing")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

logging.basicConfig(level=logging.INFO)

# ───────────────── OPENROUTER CALL ─────────────────

async def call_openrouter(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram-bot",
        "X-Title": "PDF MCQ Bot",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are an exam MCQ generator."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]

# ───────────────── PDF HANDLING ─────────────────

def extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text[:12000]  # safety limit

# ───────────────── MCQ FORMATTING ─────────────────

def clean_mcqs(raw: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", raw)
    mcqs = []
    for b in blocks:
        lines = [l.strip("•- ") for l in b.splitlines() if l.strip()]
        if len(lines) >= 5:
            mcqs.append("\n".join(lines[:6]))
    return mcqs

# ───────────────── TELEGRAM HANDLERS ─────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will generate MCQs automatically.\n"
        "No waiting. All questions will be sent."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Please send a PDF file.")
        return

    await update.message.reply_text("📥 Downloading PDF...")
    file = await doc.get_file()
    path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(path)

    await update.message.reply_text("📖 Extracting text...")
    text = extract_pdf_text(path)

    await update.message.reply_text("🧠 Generating MCQs...")

    prompt = f"""
Generate exam-quality MCQs from the text below.

Rules:
- Each question must have 4 options
- Options must be complete sentences
- Do NOT repeat partial sentences
- Do NOT cut options
- Do NOT add explanations
- Output format:

Q1. Question text
A) Option
B) Option
C) Option
D) Option

TEXT:
{text}
"""

    raw = await call_openrouter(prompt)
    mcqs = clean_mcqs(raw)

    if not mcqs:
        await update.message.reply_text("❌ No MCQs generated.")
        return

    await update.message.reply_text(f"✅ Generated {len(mcqs)} MCQs\nSending now…")

    for i, q in enumerate(mcqs, 1):
        await update.message.reply_text(f"{i}. {q}")

# ───────────────── MAIN ─────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    logging.info("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
