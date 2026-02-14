import os
import re
import time
import requests
from PyPDF2 import PdfReader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

# ---------------- START COMMAND ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a PDF.\n\n"
        "I will:\n"
        "1) Extract MCQs already present\n"
        "2) Generate additional MCQs from theory\n"
        "3) Send everything cleanly"
    )

# ---------------- PDF HANDLER ----------------
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file = await doc.get_file()
    path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(path)

    await update.message.reply_text("Reading PDF...")

    text = extract_text_from_pdf(path)

    mcqs_from_pdf = extract_existing_mcqs(text)
    await send_mcqs(update, mcqs_from_pdf, "MCQs found in PDF")

    await update.message.reply_text("Generating additional MCQs from theory...")
    ai_mcqs = generate_mcqs_from_text(text)

    await send_mcqs(update, ai_mcqs, "AI-generated MCQs")

    await update.message.reply_text(
        f"Done.\n"
        f"PDF MCQs: {len(mcqs_from_pdf)}\n"
        f"AI MCQs: {len(ai_mcqs)}"
    )

# ---------------- PDF TEXT EXTRACTION ----------------
def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    full_text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            full_text += t + "\n"
    return full_text

# ---------------- MCQ EXTRACTION ----------------
def extract_existing_mcqs(text: str):
    pattern = re.compile(
        r"(Q\.?\s*\d+.*?)(?:Answer\s*[:\-]\s*[A-D])",
        re.DOTALL | re.IGNORECASE,
    )
    matches = pattern.findall(text)
    return [m.strip() for m in matches]

# ---------------- AI MCQ GENERATION ----------------
def generate_mcqs_from_text(text: str):
    prompt = (
        "Generate maximum number of MCQs from the following content.\n"
        "Format strictly:\n"
        "Q. Question\n"
        "A) option\nB) option\nC) option\nD) option\n"
        "Answer: X\n\n"
        f"{text[:12000]}"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    r = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
    r.raise_for_status()

    content = r.json()["choices"][0]["message"]["content"]

    mcqs = re.split(r"\n(?=Q\.)", content)
    return [m.strip() for m in mcqs if "Answer" in m]

# ---------------- SAFE TELEGRAM SENDING ----------------
async def send_mcqs(update, mcqs, title):
    if not mcqs:
        await update.message.reply_text(f"No {title.lower()} found.")
        return

    await update.message.reply_text(f"{title}: {len(mcqs)}")

    chunk = ""
    for mcq in mcqs:
        if len(chunk) + len(mcq) > 3500:
            await update.message.reply_text(chunk)
            chunk = ""
        chunk += mcq + "\n\n"

    if chunk:
        await update.message.reply_text(chunk)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    print("MCQ Bot running")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

# ---------------- KEEP RAILWAY ALIVE ----------------
while True:
    time.sleep(60)
