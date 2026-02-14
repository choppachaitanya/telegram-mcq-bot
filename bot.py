import os
import json
import time
import hashlib
import logging
import requests

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from pypdf import PdfReader

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL = "mistralai/mistral-7b-instruct"
QUIZ_SIZE = 50

USED_FILE = "used_questions.json"
QUIZ_DIR = "quizzes"

os.makedirs(QUIZ_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)

# ---------------- UTILITIES ---------------- #

def load_used():
    if os.path.exists(USED_FILE):
        return set(json.load(open(USED_FILE)))
    return set()

def save_used(s):
    json.dump(list(s), open(USED_FILE, "w"))

def q_hash(text):
    return hashlib.sha256(text.lower().encode()).hexdigest()

# ---------------- PDF ---------------- #

def extract_pdf_text(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + "\n"
    return text

# ---------------- OPENROUTER ---------------- #

def generate_mcqs(text):
    prompt = f"""
Generate MEDIUM difficulty MCQs.

Rules:
- Competitive exam standard
- No trivial or one-line factual questions
- No very analytical questions
- Exactly 4 options
- One correct answer
- Skip anything related to "Aparchit"
- Clean English
- Output STRICT JSON only

Format:
[
 {{
  "question": "...",
  "options": ["A","B","C","D"],
  "answer": 0
 }}
]

TEXT:
{text[:6000]}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6
    }

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120
    )

    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]

    return json.loads(content)

# ---------------- HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will generate MEDIUM-level MCQ quiz bundles.\n"
        "Each quiz has 50 questions.\n\n"
        "Use /quiz 1, /quiz 2 later to attempt."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("📥 Downloading PDF...")

    file = await msg.document.get_file()
    path = "input.pdf"
    await file.download_to_drive(path)

    await msg.reply_text("📖 Extracting text...")
    text = extract_pdf_text(path)

    await msg.reply_text("🧠 Generating MCQs...")

    raw_mcqs = generate_mcqs(text)

    used = load_used()
    clean = []

    for m in raw_mcqs:
        h = q_hash(m["question"])
        if h in used:
            continue
        if "aparchit" in m["question"].lower():
            continue
        used.add(h)
        clean.append(m)

    save_used(used)

    if not clean:
        await msg.reply_text("❌ No valid MCQs generated.")
        return

    quizzes = [
        clean[i:i + QUIZ_SIZE]
        for i in range(0, len(clean), QUIZ_SIZE)
    ]

    for i, q in enumerate(quizzes, start=1):
        with open(f"{QUIZ_DIR}/quiz_{i}.json", "w") as f:
            json.dump(q, f, indent=2)

    await msg.reply_text(
        f"✅ Generated {len(clean)} MCQs.\n"
        f"📦 {len(quizzes)} quiz bundles created.\n\n"
        f"Use /quiz 1, /quiz 2 ..."
    )

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /quiz 1")
        return

    num = context.args[0]
    path = f"{QUIZ_DIR}/quiz_{num}.json"

    if not os.path.exists(path):
        await update.message.reply_text("❌ Quiz not found.")
        return

    quiz = json.load(open(path))

    await update.message.reply_text(f"📘 Starting Quiz {num}")

    for q in quiz:
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=q["question"],
            options=q["options"],
            type="quiz",
            correct_option_id=q["answer"],
            is_anonymous=True,
        )
        time.sleep(0.6)

# ---------------- MAIN ---------------- #

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logging.info("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
