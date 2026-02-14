import os
import re
import json
import requests
from pypdf import PdfReader
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# ===== ENV VARIABLES =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


# ===== PDF TEXT EXTRACTION =====
def extract_full_text(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


# ===== MCQ EXTRACTION FROM PDF =====
def extract_mcqs_from_pdf(text):
    mcqs = []

    pattern = re.compile(
        r"(?:Q\.?\s*\d+|\d+\.)\s*(.*?)\n"
        r"(?:\(?a\)?\s*(.*?)\n)"
        r"(?:\(?b\)?\s*(.*?)\n)"
        r"(?:\(?c\)?\s*(.*?)\n)"
        r"(?:\(?d\)?\s*(.*?))(?:\n|$)",
        re.IGNORECASE | re.DOTALL,
    )

    for m in pattern.findall(text):
        mcqs.append(
            {
                "question": m[0].strip(),
                "options": [
                    m[1].strip(),
                    m[2].strip(),
                    m[3].strip(),
                    m[4].strip(),
                ],
                "answer_index": 0,  # default
            }
        )

    return mcqs


# ===== REMOVE MCQS TO GET THEORY =====
def remove_mcqs_from_text(text):
    cleaned = re.sub(
        r"(?:Q\.?\s*\d+|\d+\.).*?\(?d\)?.*?(?:\n|$)",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return cleaned.strip()


# ===== AI MCQ GENERATION FROM THEORY =====
def generate_ai_mcqs(theory_text, count=25):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Telegram MCQ Bot",
    }

    prompt = f"""
Generate EXACTLY {count} high-quality exam-oriented MCQs from the theory below.

Rules:
- Do NOT repeat questions already in the PDF
- Each MCQ must have 4 options
- One correct answer
- Output ONLY valid JSON

Format:
[
  {{
    "question": "",
    "options": ["A","B","C","D"],
    "answer_index": 0
  }}
]

THEORY:
{theory_text[:4000]}
"""

    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()

        raw = r.json()["choices"][0]["message"]["content"]
        match = re.search(r"\[.*\]", raw, re.DOTALL)

        return json.loads(match.group()) if match else []

    except Exception as e:
        print("AI MCQ error:", e)
        return []


# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF.\n\n"
        "I will:\n"
        "• Extract ALL MCQs already present\n"
        "• Generate extra MCQs from theory\n"
        "• Create a complete question bank ✅"
    )


# ===== PDF HANDLER =====
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("input.pdf")

    await update.message.reply_text("📄 PDF received. Processing...")

    full_text = extract_full_text("input.pdf")

    extracted_mcqs = extract_mcqs_from_pdf(full_text)
    theory_text = remove_mcqs_from_text(full_text)

    total = 0

    # 1️⃣ Send extracted MCQs
    if extracted_mcqs:
        await update.message.reply_text(
            f"📘 Found {len(extracted_mcqs)} MCQs in PDF. Sending..."
        )

        for q in extracted_mcqs:
            await context.bot.send_poll(
                chat_id=update.effective_chat.id,
                question=q["question"],
                options=q["options"],
                type="quiz",
                correct_option_id=q["answer_index"],
            )
            total += 1

    # 2️⃣ Generate AI MCQs from theory
    if len(theory_text) > 500:
        await update.message.reply_text(
            "🧠 Generating additional MCQs from theory..."
        )

        ai_mcqs = generate_ai_mcqs(theory_text, count=25)

        for q in ai_mcqs:
            await context.bot.send_poll(
                chat_id=update.effective_chat.id,
                question=q["question"],
                options=q["options"],
                type="quiz",
                correct_option_id=q["answer_index"],
            )
            total += 1

    await update.message.reply_text(
        f"✅ Done. Total MCQs delivered: {total}"
    )


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("MCQ Bot running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
