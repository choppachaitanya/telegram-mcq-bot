import os
import re
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

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

# ---------- COMMAND ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a PDF.\n"
        "I will extract existing MCQs and generate more from theory."
    )

# ---------- PDF HANDLER ----------
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    path = f"/tmp/{update.message.document.file_name}"
    await file.download_to_drive(path)

    await update.message.reply_text("Reading PDF...")

    text = extract_text(path)

    pdf_mcqs = extract_mcqs(text)
    await send_mcqs(update, pdf_mcqs, "MCQs found in PDF")

    await update.message.reply_text("Generating AI MCQs...")
    ai_mcqs = generate_mcqs(text)
    await send_mcqs(update, ai_mcqs, "AI Generated MCQs")

    await update.message.reply_text(
        f"Done.\nPDF MCQs: {len(pdf_mcqs)}\nAI MCQs: {len(ai_mcqs)}"
    )

# ---------- PDF TEXT ----------
def extract_text(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"
    return text

# ---------- MCQ EXTRACTION ----------
def extract_mcqs(text):
    pattern = re.compile(
        r"(Q\.?\s*\d+.*?Answer\s*[:\-]\s*[A-D])",
        re.DOTALL | re.IGNORECASE,
    )
    return [m.strip() for m in pattern.findall(text)]

# ---------- AI MCQs ----------
def generate_mcqs(text):
    prompt = (
        "Create maximum MCQs from the following content.\n"
        "Format strictly:\n"
        "Q. Question\n"
        "A) ... B) ... C) ... D) ...\n"
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
    return [m.strip() for m in re.split(r"\n(?=Q\.)", content) if "Answer" in m]

# ---------- SAFE SENDER ----------
async def send_mcqs(update, mcqs, title):
    if not mcqs:
        await update.message.reply_text(f"No {title.lower()} found.")
        return

    await update.message.reply_text(f"{title}: {len(mcqs)}")

    buf = ""
    for m in mcqs:
        if len(buf) + len(m) > 3500:
            await update.message.reply_text(buf)
            buf = ""
        buf += m + "\n\n"

    if buf:
        await update.message.reply_text(buf)

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
