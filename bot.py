import os
import asyncio
import logging
from telegram import Update
from telegram.constants import PollType
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from pypdf import PdfReader
import openai

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- PDF TEXT EXTRACTION ----------------

def extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n".join(text)

# ---------------- MCQ CLEANING ----------------

def clean_options(options):
    cleaned = []
    for o in options:
        o = o.strip()
        if len(o) < 15:
            continue
        if any(o.lower() in x.lower() or x.lower() in o.lower() for x in cleaned):
            continue
        cleaned.append(o)
    return cleaned

def clean_mcqs(mcqs):
    final = []
    for q in mcqs:
        opts = clean_options(q["options"])
        if len(opts) < 4:
            continue
        ans = q["answer"]
        if ans >= len(opts):
            ans = 0
        final.append({
            "q": q["q"].strip(),
            "options": opts[:6],
            "answer": ans
        })
    return final

# ---------------- AI MCQ GENERATION ----------------

def generate_mcqs(text, count=120):
    prompt = f"""
Create {count} UPSC-level MCQs from the text.

STRICT:
- Each option must be a full meaningful sentence
- No partial or overlapping options
- 4–6 options only
- Return JSON ONLY

Format:
[
  {{
    "q": "question",
    "options": ["A","B","C","D"],
    "answer": 0
  }}
]

TEXT:
{text[:14000]}
"""

    res = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return eval(res.choices[0].message.content)

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will generate MCQs automatically.\n"
        "No waiting. All questions will be sent."
    )

async def pdf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Please upload a PDF file.")
        return

    await update.message.reply_text("📥 Downloading PDF...")
    file = await doc.get_file()
    path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(path)

    await update.message.reply_text("📖 Extracting text...")
    text = extract_pdf_text(path)

    if len(text) < 1000:
        await update.message.reply_text("PDF text too short.")
        return

    await update.message.reply_text("🧠 Generating MCQs...")
    raw_mcqs = generate_mcqs(text)
    mcqs = clean_mcqs(raw_mcqs)

    if not mcqs:
        await update.message.reply_text("No valid MCQs generated.")
        return

    quiz_no = 1
    count = 0

    for i, q in enumerate(mcqs, start=1):
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=f"Q{i}. {q['q']}",
            options=q["options"],
            type=PollType.QUIZ,
            correct_option_id=q["answer"],
            is_anonymous=True
        )

        count += 1
        await asyncio.sleep(0.6)

        if count % 50 == 0:
            quiz_no += 1
            await update.message.reply_text(f"✅ Quiz {quiz_no - 1} completed")

    await update.message.reply_text(f"🎉 Done. Generated {count} MCQs.")

# ---------------- MAIN ----------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, pdf_handler))

    logger.info("MCQ PDF Bot running")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
