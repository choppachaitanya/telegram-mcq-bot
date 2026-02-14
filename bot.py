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

if not BOT_TOKEN or not OPENROUTER_API_KEY:
    raise RuntimeError("BOT_TOKEN or OPENROUTER_API_KEY missing")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.1-8b-instruct"

MAX_QUESTION_LEN = 300
MAX_OPTION_LEN = 100
QUIZ_BATCH = 50
SEND_DELAY = 0.8

BLOCKED_KEYWORDS = ["aparchit"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- PDF ----------------

def extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return pages  # page-wise list


def clean_text(text: str) -> str:
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
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract_json_array(raw: str):
    match = re.search(r"\[\s*{.*?}\s*\]", raw, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except Exception:
        return []


def generate_mcqs(text: str):
    prompt = f"""
Generate at least 8 MCQs from the text below.

STRICT RULES:
- EXACTLY 4 options
- Options < 90 characters
- One correct answer (0–3)
- Output ONLY JSON array
- No explanations

FORMAT:
[
  {{
    "question": "...",
    "options": ["A","B","C","D"],
    "answer": 1
  }}
]

TEXT:
{text[:4000]}
"""

    raw = call_openrouter(prompt)
    mcqs = extract_json_array(raw)

    cleaned = []
    for m in mcqs:
        try:
            q = m["question"][:MAX_QUESTION_LEN]
            opts = [o[:MAX_OPTION_LEN] for o in m["options"]]
            ans = int(m["answer"])
            if len(opts) == 4 and len(set(opts)) == 4 and 0 <= ans < 4:
                cleaned.append({
                    "question": q,
                    "options": opts,
                    "answer": ans
                })
        except Exception:
            continue

    return cleaned

# ---------------- TELEGRAM ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "MCQs will be generated page-wise and sent as Quiz polls."
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    await update.message.reply_text("📥 Downloading PDF...")
    file = await doc.get_file()
    path = f"/tmp/{doc.file_unique_id}.pdf"
    await file.download_to_drive(path)

    await update.message.reply_text("📖 Extracting text...")
    pages = extract_pdf_text(path)

    await update.message.reply_text("🧠 Generating MCQs page-wise...")

    all_mcqs = []

    for idx, page_text in enumerate(pages, start=1):
        page_text = clean_text(page_text)
        if len(page_text.strip()) < 300:
            continue

        mcqs = generate_mcqs(page_text)
        all_mcqs.extend(mcqs)

        await update.message.reply_text(
            f"✅ Page {idx}: Generated {len(mcqs)} MCQs"
        )

    if not all_mcqs:
        await update.message.reply_text("❌ No MCQs generated.")
        return

    await update.message.reply_text(
        f"🎯 Total MCQs generated: {len(all_mcqs)}\nSending quizzes..."
    )

    quiz_no = 1
    sent = 0

    for m in all_mcqs:
        if sent % QUIZ_BATCH == 0:
            await update.message.reply_text(f"📘 Quiz {quiz_no}")
            quiz_no += 1

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
