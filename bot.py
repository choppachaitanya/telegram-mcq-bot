import os
import re
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from PyPDF2 import PdfReader

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Set this in Railway Variables
MAX_MSG_LEN = 3800

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- HELPERS ----------------
def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text.append(page_text)
    return "\n".join(text)


def extract_mcqs(text: str):
    """
    Very tolerant MCQ extractor
    """
    pattern = re.compile(
        r"(Q\.?\s*\d+.*?)(?:\n\s*A\)|\n\s*\(A\))",
        re.DOTALL | re.IGNORECASE
    )
    matches = pattern.findall(text)
    return [m.strip() for m in matches]


def generate_mcqs_from_theory(text: str, count=20):
    """
    Simple rule-based MCQ generation (safe & offline)
    """
    sentences = re.split(r"[.\n]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 60]

    mcqs = []
    for i, s in enumerate(sentences[:count], start=1):
        q = f"Q. {i} Which of the following is related to:\n{s[:120]}?"
        opts = [
            "A) Statement is correct",
            "B) Statement is incorrect",
            "C) Both A and B",
            "D) Cannot be determined",
        ]
        mcqs.append(q + "\n" + "\n".join(opts) + "\nAnswer: A")

    return mcqs


def send_long_message(chat_id, text, context):
    for i in range(0, len(text), MAX_MSG_LEN):
        context.bot.send_message(chat_id=chat_id, text=text[i:i+MAX_MSG_LEN])


# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF.\n\n"
        "I will:\n"
        "1️⃣ Extract MCQs already present\n"
        "2️⃣ Generate additional MCQs from theory\n"
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file = await document.get_file()

    pdf_path = f"/tmp/{document.file_name}"
    await file.download_to_drive(pdf_path)

    await update.message.reply_text("📖 Reading PDF...")

    text = extract_text_from_pdf(pdf_path)

    extracted_mcqs = extract_mcqs(text)
    generated_mcqs = generate_mcqs_from_theory(text, count=25)

    await update.message.reply_text(
        f"✅ Found {len(extracted_mcqs)} MCQs in PDF\n"
        f"🤖 Generated {len(generated_mcqs)} MCQs from theory\n\n"
        "📤 Sending now..."
    )

    all_mcqs = extracted_mcqs + generated_mcqs

    for idx, mcq in enumerate(all_mcqs, start=1):
        send_long_message(
            update.message.chat_id,
            f"{idx}. {mcq}",
            context
        )

    os.remove(pdf_path)


# ---------------- MAIN ----------------
def main():
    print("MCQ Bot running")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.Document.PDF, handle_pdf)
    )

    app.run_polling()


if __name__ == "__main__":
    main()
