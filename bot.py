import os
import json
import asyncio
import logging
from io import BytesIO
from pypdf import PdfReader
from telegram import Update
from telegram.constants import PollType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------- HELPERS ----------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n".join(text)


def chunk_text(text: str, max_chars=3000):
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) < max_chars:
            current += line + "\n"
        else:
            chunks.append(current)
            current = line + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


def generate_mcqs(text_chunk: str, max_q=10):
    prompt = f"""
Generate MCQs strictly in JSON.
Rules:
- EXACTLY 4 options per question
- Options must be complete sentences
- No text fragments
- No repetition
- No explanations

Return ONLY JSON array.

Format:
[
  {{
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "answer_index": 0
  }}
]

Text:
{text_chunk}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    content = response.choices[0].message.content.strip()
    return json.loads(content)


def valid_mcq(m):
    return (
        isinstance(m.get("question"), str)
        and isinstance(m.get("options"), list)
        and len(m["options"]) == 4
        and len(set(m["options"])) == 4
        and isinstance(m.get("answer_index"), int)
        and 0 <= m["answer_index"] < 4
    )

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will generate MCQs automatically.\n"
        "No waiting. All questions will be sent."
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    await update.message.reply_text("📥 Downloading PDF...")
    file = await update.message.document.get_file()
    file_bytes = await file.download_as_bytearray()

    await update.message.reply_text("📖 Extracting text...")
    text = extract_text_from_pdf(file_bytes)

    if len(text) < 500:
        await update.message.reply_text("❌ PDF has insufficient readable text.")
        return

    chunks = chunk_text(text)
    all_mcqs = []

    await update.message.reply_text("🧠 Generating MCQs...")

    for chunk in chunks:
        try:
            mcqs = generate_mcqs(chunk)
            for m in mcqs:
                if valid_mcq(m):
                    all_mcqs.append(m)
        except Exception as e:
            logger.error(f"MCQ generation failed: {e}")

    if not all_mcqs:
        await update.message.reply_text("❌ No valid MCQs generated.")
        return

    await update.message.reply_text(f"✅ Generated {len(all_mcqs)} MCQs.\nSending now...")

    # SEND ALL QUESTIONS (NO WAITING)
    for i, m in enumerate(all_mcqs, start=1):
        await context.bot.send_poll(
            chat_id=chat_id,
            question=f"Q{i}. {m['question']}",
            options=m["options"],
            type=PollType.QUIZ,
            correct_option_id=m["answer_index"],
            is_anonymous=False,
        )
        await asyncio.sleep(0.3)  # Telegram safety delay

    await update.message.reply_text("🎉 Done! All questions sent.")

# ---------------- MAIN ----------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logger.info("MCQ Bot running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
