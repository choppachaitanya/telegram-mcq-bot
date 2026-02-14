import os
import re
import json
import time
import hashlib
import logging
import requests
from pypdf import PdfReader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL = "mistralai/mistral-7b-instruct"
QUIZ_SIZE = 50
CHUNK_SIZE = 1800

QUIZ_DIR = "quizzes"
USED_FILE = "used_questions.json"

os.makedirs(QUIZ_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

# ---------------- UTIL ---------------- #

def load_used():
    if os.path.exists(USED_FILE):
        return set(json.load(open(USED_FILE)))
    return set()

def save_used(s):
    json.dump(list(s), open(USED_FILE, "w"))

def qhash(q):
    return hashlib.sha256(q.lower().encode()).hexdigest()

# ---------------- PDF ---------------- #

def extract_text(path):
    reader = PdfReader(path)
    text = ""
    for p in reader.pages:
        t = p.extract_text()
        if t:
            text += t + "\n"
    return text

def chunk_text(text):
    return [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

# ---------------- OPENROUTER ---------------- #

def call_openrouter(chunk):
    prompt = (
        "You are a JSON generator.\n"
        "Convert the content below into MEDIUM-difficulty MCQs.\n"
        "Rules:\n"
        "- Exactly 4 options\n"
        "- One correct answer\n"
        "- No Aparchit\n"
        "- No explanations\n\n"
        "Return ONLY valid JSON array:\n"
        "[{\"question\":\"Q\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"answer\":0}]\n\n"
        "CONTENT:\n"
        f"{chunk}"
    )

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        },
        timeout=120
    )

    logging.info("OPENROUTER RESPONSE ↓")
    logging.info(r.text[:1200])

    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def extract_mcqs(raw):
    try:
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            return json.loads(m.group())
    except:
        pass
    return []

# ---------------- BOT HANDLERS ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will create MODEL TEST quiz bundles.\n\n"
        "Each quiz = 50 questions.\n"
        "Use /quiz 1, /quiz 2 anytime."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("📥 Downloading PDF...")

    file = await msg.document.get_file()
    path = "input.pdf"
    await file.download_to_drive(path)

    await msg.reply_text("📖 Extracting text...")
    text = extract_text(path)

    await msg.reply_text(f"📊 Extracted {len(text)} characters")

    if len(text) < 1000:
        await msg.reply_text("❌ PDF has no readable text.")
        return

    await msg.reply_text("🧠 Generating MCQs (medium difficulty)...")

    used = load_used()
    all_mcqs = []

    for chunk in chunk_text(text):
        raw = call_openrouter(chunk)
        mcqs = extract_mcqs(raw)

        for m in mcqs:
            q = m.get("question", "").strip()
            if not q:
                continue
            if "aparchit" in q.lower():
                continue

            h = qhash(q)
            if h in used:
                continue

            if len(m.get("options", [])) != 4:
                continue

            used.add(h)
            all_mcqs.append(m)

        time.sleep(1)

    save_used(used)

    if not all_mcqs:
        await msg.reply_text("❌ No quizzes generated.")
        return

    quizzes = [
        all_mcqs[i:i+QUIZ_SIZE]
        for i in range(0, len(all_mcqs), QUIZ_SIZE)
    ]

    for i, quiz in enumerate(quizzes, start=1):
        with open(f"{QUIZ_DIR}/quiz_{i}.json", "w") as f:
            json.dump(quiz, f, indent=2)

    await msg.reply_text(
        f"✅ Generated {len(all_mcqs)} MCQs\n"
        f"📦 {len(quizzes)} quiz bundles created\n\n"
        f"Start anytime using:\n"
        f"/quiz 1\n/quiz 2\n..."
    )

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /quiz 1")
        return

    qn = context.args[0]
    path = f"{QUIZ_DIR}/quiz_{qn}.json"

    if not os.path.exists(path):
        await update.message.reply_text("❌ Quiz not found.")
        return

    quiz = json.load(open(path))
    await update.message.reply_text(f"📘 Starting Quiz {qn}")

    for q in quiz:
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=q["question"][:300],
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
    logging.info("MCQ Bot running (SAVE MODE)")
    app.run_polling()

if __name__ == "__main__":
    main()
