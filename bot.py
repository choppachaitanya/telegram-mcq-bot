import os
import io
import re
from PyPDF2 import PdfReader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send a PDF containing MCQs or theory. I will extract MCQs."
    )


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
    return full_text


def extract_mcqs(text: str):
    mcqs = []

    pattern = re.compile(
        r"\d+\.\s*(.*?)\nA\)\s*(.*?)\nB\)\s*(.*?)\nC\)\s*(.*?)\nD\)\s*(.*?)",
        re.DOTALL | re.IGNORECASE
    )

    for match in pattern.finditer(text):
        question = match.group(1).strip()
        options = [
            match.group(2).strip(),
            match.group(3).strip(),
            match.group(4).strip(),
            match.group(5).strip(),
        ]
        mcqs.append((question, options))

    return mcqs


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file = await document.get_file()
    pdf_bytes = await file.download_as_bytearray()

    text = extract_text_from_pdf(pdf_bytes)
    mcqs = extract_mcqs(text)

    if not mcqs:
        await update.message.reply_text("No MCQs found in this PDF.")
        return

    await update.message.reply_text(f"Found {len(mcqs)} MCQs. Sending now…")

    for q, opts in mcqs:
        message = q + "\n\n"
        for i, opt in enumerate(opts):
            message += f"{chr(65+i)}) {opt}\n"

        # Telegram limit safety
        if len(message) > 3500:
            message = message[:3500]

        await update.message.reply_text(message)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("MCQ Bot running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
