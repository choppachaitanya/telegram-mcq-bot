import os
import re
import json
import asyncio
import logging
import requests
from pypdf import PdfReader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL = "mistralai/mistral-7b-instruct"
MAX_MCQS = 100
MCQS_PER_QUIZ = 50

logging.basicConfig(level=logging.INFO)

# ---------------- HELPERS ----------------

def extract_text_from_pdf(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        t = page.extract_text() or ""
        text += t + "\n"
    return text.strip()

def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"Aparchit.*?(?=\.)", "", text, flags=re.I)
    return text

def chunk_text(text, size=3500):
    return [text[i:i+size] for i in range(0, len(text), size)]

def call_openrouter(chunk):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": (
                "Create medium-difficulty MCQs.\n"
                "Return JSON ONLY in this format:\n"
                "[{\"question\":\"Q\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"answer\":0}]\n\n"
                + chunk
            )
        }],
        "temperature": 0.6
    }

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120
    )

    logging.info(r.text[:1500])
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def extract_mcqs(raw):
    try:
        m = re.search(r"\[.*\]", raw, re.S)
        if m:
            return json.loads(m.group())
    except:
        pass

    mcqs = []
    blocks = re.split(r"\n\d+\.", raw)
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 5:
            continue

        q = lines[0].strip()
        opts = []
        for l in lines[1:]:
            if l.strip().startswith(("A)", "B)", "C)", "D)")):
                opts.append(l[2:].strip())

        if len(opts) == 4:
            mcqs.append({
                "question": q,
                "options": opts,
                "answer": 0
            })

    return mcqs

def fallback_mcqs(text, limit=50):
    sentences = re.split(r"[.?!]", text)
    mcqs = []

    for s in sentences:
        s = s.strip()
        if 40 < len(s) < 180:
            mcqs.append({
                "question": f"Which statement is correct?",
                "options": [
                    s,
                    "Incorrect option 1",
                    "Incorrect option 2",
                    "Incorrect option 3"
                ],
                "answer": 0
            })
        if len(mcqs) >= limit:
            break

    return mcqs

def unique_mcqs(mcqs):
    seen = set()
    final = []
    for m in mcqs:
        if m["question"] not in seen:
            seen.add(m["question"])
            final.append(m)
    return final

# ---------------- BOT HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will generate ALL MCQs automatically.\n"
        "No waiting. Medium difficulty. No overlap."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("📥 Downloading PDF...")

    file = await msg.document.get_file()
    path = "input.pdf"
    await file.download_to_drive(path)

    await msg.reply_text("📖 Extracting text...")
    text = extract_text_from_pdf(path)
    text = clean_text(text)

    await msg.reply_text(f"📊 Extracted {len(text)} characters")

    if len(text) < 1000:
        await msg.reply_text("❌ PDF has no readable text.")
        return

    await msg.reply_text("🧠 Generating MCQs...")

    all_mcqs = []
    for chunk in chunk_text(text):
        try:
            raw = call_openrouter(chunk)
            parsed = extract_mcqs(raw)
            all_mcqs.extend(parsed)
        except Exception as e:
            logging.error(e)

        if len(all_mcqs) >= MAX_MCQS:
            break

    if not all_mcqs:
        all_mcqs = fallback_mcqs(text)

    all_mcqs = unique_mcqs(all_mcqs)

    if not all_mcqs:
        await msg.reply_text("❌ No quizzes generated.")
        return

    await msg.reply_text(f"✅ Generated {len(all_mcqs)} MCQs.\nSending quizzes...")

    # Send in bundles of 50
    for i in range(0, len(all_mcqs), MCQS_PER_QUIZ):
        bundle = all_mcqs[i:i+MCQS_PER_QUIZ]

        for q in bundle:
            await context.bot.send_poll(
                chat_id=msg.chat_id,
                question=q["question"][:300],
                options=q["options"],
                type="quiz",
                correct_option_id=q["answer"],
                is_anonymous=True
            )
            await asyncio.sleep(0.4)

    await msg.reply_text("🎯 Done. You can take the quiz anytime.")

# ---------------- MAIN ----------------

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logging.info("MCQ Bot running")
    app.run_polling()
