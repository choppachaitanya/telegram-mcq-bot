import os
import json
import re
import requests
from pypdf import PdfReader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


def extract_pages(pdf_path, max_pages=20):
    reader = PdfReader(pdf_path)
    out = []
    for i, page in enumerate(reader.pages):
        if i >= max_pages:
            break
        text = page.extract_text()
        if text:
            out.append(text[:1500])
    return out
def generate_mcqs(text):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": "Bearer " + OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Telegram MCQ Bot"
    }

    content = (
        "Create 3 to 5 MCQs from the text below.\n"
        "Return ONLY valid JSON:\n"
        "[{\"question\":\"\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"answer_index\":0}]\n\n"
        + text
    )

    body = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": content}]
    }

    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()

    raw = r.json()["choices"][0]["message"]["content"]
    match = re.search(r"\[.*\]", raw, re.S)
    return json.loads(match.group()) if match else []


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("input.pdf")
    await update.message.reply_text("PDF received. Generating MCQs...")

    total = 0
    for page in extract_pages("input.pdf"):
        for q in generate_mcqs(page):
            await context.bot.send_poll(
                chat_id=update.effective_chat.id,
                question=q["question"],
                options=q["options"],
                type="quiz",
                correct_option_id=q["answer_index"]
            )
            total += 1

    await update.message.reply_text(f"Done. Generated {total} MCQs.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    print("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
