import os
import io
import re
import pdfplumber
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a PDF containing MCQs or theory.")

def extract_mcqs(text):
    mcqs = []
    pattern = re.compile(
        r"\d+\.\s*(.*?)\nA\)\s*(.*?)\nB\)\s*(.*?)\nC\)\s*(.*?)\nD\)\s*(.*?)",
        re.DOTALL
    )
    for m in pattern.finditer(text):
        mcqs.append(
            (m.group(1).strip(), [m.group(i).strip() for i in range(2, 6)])
        )
    return mcqs

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    data = await file.download_as_bytearray()

    text = ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    mcqs = extract_mcqs(text)

    if not mcqs:
        await update.message.reply_text("No MCQs found in this PDF.")
        return

    await update.message.reply_text(f"Found {len(mcqs)} MCQs.")

    for q, opts in mcqs[:10]:
        msg = q + "\n\n"
        for i, o in enumerate(opts):
            msg += chr(65+i) + ") " + o + "\n"
        await update.message.reply_text(msg)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    print("MCQ Bot running")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
