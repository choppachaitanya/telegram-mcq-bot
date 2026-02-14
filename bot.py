import os
import re
import json
import time
import logging
import requests
from pypdf import PdfReader
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is missing")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.1-8b-instruct"

# Telegram hard limits
MAX_QUESTION_LEN = 300
MAX_OPTION_LEN = 100
OPTIONS_COUNT = 4
QUIZ_BATCH = 50
SEND_DELAY = 0.8  # seconds

BLOCKED_KEYWORDS = ["aparchit"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- PDF ----------------

def extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    text_parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text_parts.append(t)
    return "\n".join(text_parts)

def remove_blocked_content(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(
        line for line in lines
        if not any(b in line.lower() for b in BLOCKED_KEYWORDS)
    )

# ---------------- OPENROUTER ----------------

def call_openrouter(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram-mcq-bot",
        "X-Title": "Telegram MCQ Bot",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You generate exam-quality MCQs."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    r = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def extract_json_array(raw: str):
    """
    Safely extract JSON array even if wrapped in text or markdown.
    """
    match = re.search(r"\[\s*{.*?}\s*\]", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except Exception as e:
        logger.error(f"JSON parsing failed: {e}")
        return None

def generate_mcqs(text: str):
    prompt = f"""
Generate MCQs from the text below.

STRICT RULES:
- EXACTLY 4 options per question
- Options must be short, complete sentences (under 90 characters)
- One correct answer (0-based index)
- NO explanations
- OUTPUT JSON ARRAY ONLY

FORMAT:
[
  {{
    "question": "Question text",
    "options": ["A", "B", "C", "D"],
    "answer": 2
  }}
]

TEXT:
{text[:10000]}
"""

    raw = call_openrouter(prompt)
    logger.info("RAW MODEL RESPONSE (first 800 chars):")
    logger.info(raw[:800])

    mcqs = extract_json_array(raw)
    if not mcqs:
        return []

    cleaned = []
    for m in mcqs:
        try:
            q = m["question"].strip()[:MAX_QUESTION_LEN]
            opts = [o.strip()[:MAX_OPTION_LEN] for o in m["options"]]
            ans = int(m["answer"])

            if (
                len(opts) == OPTIONS_COUNT
                and len(set(opts)) == OPTIONS_COUNT
                and 0 <= ans < OPTIONS_COUNT
            ):
                cleaned.append({
                    "question": q,
                    "options": opts,
                    "answer": ans,
                })
        except Exception:
            continue

    return cleaned

# ---------------- TELEGRAM HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will generate Telegram QUIZ MCQs automatically.\n"
        "All questions will be sent (no waiting)."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Please send a PDF file.")
        return

    await update.message.reply_text("📥 Downloading PDF...")
    file = await doc.get_file()
    path = f"/tmp/{doc.file_unique_id}.pdf"
    await file.download_to_drive(path)

    await update.message.reply_text("📖 Extracting text...")
    text = extract_pdf_text(path)
    text = remove_blocked_content(text)

    if len(text.strip()) < 500:
        await update.message.reply_text("❌ PDF text too short or unreadable.")
        return

    await update.message.reply_text("🧠 Generating MCQs...")
    mcqs = generate_mcqs(text)

    if not mcqs:
        await update.message.reply_text(
            "❌ MCQ generation failed.\n"
            "The model did not return valid questions.\n"
            "Try a smaller or clearer PDF."
        )
        return

    await update.message.reply_text(f"✅ Generated {len(mcqs)} MCQs.\nSending quizzes...")

    quiz_no = 1
    sent = 0

    for i, m in enumerate(mcqs, start=1):
        if sent % QUIZ_BATCH == 0:
            await update.message.reply_text(f"📘 Quiz {quiz_no}")
            quiz_no += 1

        try:
            await context.bot.send_poll(
                chat_id=update.effective_chat.id,
                question=m["question"],
                options=m["options"],
                type="quiz",
                correct_option_id=m["answer"],
                is_anonymous=True,
            )
            sent += 1
            time.sleep(SEND_DELAY)
        except Exception as e:
            logger.error(f"Failed to send poll: {e}")

    await update.message.reply_text("🎉 All quizzes sent.")

# ---------------- MAIN ----------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logger.info("MCQ Quiz Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
