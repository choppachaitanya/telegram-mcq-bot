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

# ================= CONFIG ================= #

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL = "mistralai/mistral-7b-instruct"

CHUNK_SIZE = 1800
QUIZ_MAX = 50
QUIZ_MIN = 20
SLEEP = 1

QUIZ_DIR = "quizzes"
USED_FILE = "used_questions.json"

os.makedirs(QUIZ_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

# ================= UTIL ================= #

def load_used():
    if os.path.exists(USED_FILE):
        return set(json.load(open(USED_FILE)))
    return set()

def save_used(s):
    json.dump(list(s), open(USED_FILE, "w"))

def qhash(q):
    return hashlib.sha256(q.lower().encode()).hexdigest()

# ================= PDF ================= #

def extract_text(path):
    reader = PdfReader(path)
    text = ""
    for p in reader.pages:
        t = p.extract_text()
        if t:
            text += t + "\n"
    return text

def chunk_text(text):
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

# ================= OPENROUTER ================= #

def call_openrouter(chunk):
    prompt = (
        "You are a JSON generator.\n"
        "Create AT MOST 3 MEDIUM-difficulty MCQs.\n\n"
        "Rules:\n"
        "- Exactly 4 options\n"
        "- One correct answer (0-3)\n"
        "- No Aparchit\n"
        "- No explanations\n\n"
        "Return ONLY JSON array:\n"
        "[{\"question\":\"Q\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"answer\":0}]\n\n"
        "CONTENT:\n"
        f"{chunk}"
    )

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 450,
        },
        timeout=120,
    )

    logging.info("OPENROUTER RAW RESPONSE ↓")
    logging.info(r.text[:1000])

    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ================= BULLETPROOF MCQ EXTRACTOR ================= #

def extract_mcqs(raw):
    raw = raw.replace("```json", "").replace("```", "").strip()

    mcqs = []
    buf = ""
    depth = 0

    for ch in raw:
        if ch == "{":
            depth += 1
        if depth > 0:
            buf += ch
        if ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(buf)
                    if (
                        "question" in obj
                        and "options" in obj
                        and "answer" in obj
                        and len(obj["options"]) == 4
                    ):
                        mcqs.append(obj)
                except:
                    pass
                buf = ""

    return mcqs

# ================= BOT HANDLERS ================= #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n\n"
        "• Medium difficulty MCQs\n"
        "• Numbered questions\n"
        "• Options A–D\n"
        "• Each quiz ≥ 20 questions\n\n"
        "Start later with /quiz 1"
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("📥 Downloading PDF...")

    file = await msg.document.get_file()
    pdf_path = "input.pdf"
    await file.download_to_drive(pdf_path)

    await msg.reply_text("📖 Extracting text...")
    text = extract_text(pdf_path)

    await msg.reply_text(f"📊 Extracted {len(text)} characters")

    if len(text) < 1000:
        await msg.reply_text("❌ No readable text found.")
        return

    await msg.reply_text("🧠 Generating MCQs...")

    used = load_used()
    all_mcqs = []

    for chunk in chunk_text(text):
        raw = call_openrouter(chunk)
        mcqs = extract_mcqs(raw)

        logging.info(f"MCQs extracted from chunk: {len(mcqs)}")

        for m in mcqs:
            q_text = m["question"].strip()

            h = qhash(q_text)
            if h in used:
                continue

            used.add(h)
            all_mcqs.append(m)

        time.sleep(SLEEP)

    save_used(used)

    if not all_mcqs:
        await msg.reply_text("❌ No MCQs generated.")
        return

    # -------- BUNDLING (MIN 20) -------- #

    quizzes = []
    buf = []

    for q in all_mcqs:
        buf.append(q)
        if len(buf) == QUIZ_MAX:
            quizzes.append(buf)
            buf = []

    if len(buf) >= QUIZ_MIN:
        quizzes.append(buf)
    elif quizzes:
        quizzes[-1].extend(buf)

    for i, quiz in enumerate(quizzes, start=1):
        with open(f"{QUIZ_DIR}/quiz_{i}.json", "w") as f:
            json.dump(quiz, f, indent=2)

    await msg.reply_text(
        f"✅ Generated {len(all_mcqs)} MCQs\n"
        f"📦 {len(quizzes)} quiz bundles created\n\n"
        f"Start with:\n/quiz 1\n/quiz 2"
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

    for idx, q in enumerate(quiz):
        labeled_options = [
            f"A. {q['options'][0]}",
            f"B. {q['options'][1]}",
            f"C. {q['options'][2]}",
            f"D. {q['options'][3]}",
        ]

        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=f"Q. {idx+1}. {q['question']}"[:300],
            options=labeled_options,
            type="quiz",
            correct_option_id=q["answer"],
            is_anonymous=True,
        )
        time.sleep(0.6)

# ================= MAIN ================= #

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logging.info("MCQ Bot running — exam format enabled")
    app.run_polling()

if __name__ == "__main__":
    main()
