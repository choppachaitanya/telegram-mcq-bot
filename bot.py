       t = page.extract_text()
        if t:
            text += t + "\n"
    return text


# ================== EXTRACT MCQS FROM PDF ==================
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


# ================== REMOVE MCQS TO GET THEORY ==================
def remove_mcqs_from_text(text):
    cleaned = re.sub(
        r"(?:Q\.?\s*\d+|\d+\.).*?\(?d\)?.*?(?:\n|$)",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return cleaned.strip()


# ================== SANITIZE MCQ (TELEGRAM SAFE) ==================
def sanitize_mcq(mcq):
    question = mcq["question"].replace("\n", " ").strip()[:300]

    options = []
    for opt in mcq["options"]:
        clean = opt.replace("\n", " ").strip()[:100]
        if clean:
            options.append(clean)

    if len(options) < 2:
        return None

    return {
        "question": question,
        "options": options[:10],
        "answer_index": min(mcq.get("answer_index", 0), len(options) - 1),
    }


# ================== AI MCQ GENERATION ==================
def generate_ai_mcqs(theory_text, count=25):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Telegram MCQ Bot",
    }

    prompt = f"""
Generate EXACTLY {count} unique, exam-oriented MCQs from the THEORY below.

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


# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF.\n\n"
        "I will:\n"
        "• Extract ALL MCQs already present\n"
        "• Generate extra MCQs from theory\n"
        "• Deliver a complete question bank ✅"
    )


# ================== PDF HANDLER ==================
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("input.pdf")

    await update.message.reply_text("📄 PDF received. Processing...")

    full_text = extract_full_text("input.pdf")
    extracted_mcqs = extract_mcqs_from_pdf(full_text)
    theory_text = remove_mcqs_from_text(full_text)

    total = 0

    # ---- SEND EXTRACTED MCQS ----
    if extracted_mcqs:
        await update.message.reply_text(
            f"📘 Found {len(extracted_mcqs)} MCQs in PDF. Sending..."
        )

        for raw_q in extracted_mcqs:
            mcq = sanitize_mcq(raw_q)
            if not mcq:
                continue

            try:
                await context.bot.send_poll(
                    chat_id=update.effective_chat.id,
                    question=mcq["question"],
                    options=mcq["options"],
                    type="quiz",
                    correct_option_id=mcq["answer_index"],
                )
                await asyncio.sleep(0.35)  # rate-limit safety
                total += 1
            except Exception as e:
                print("Failed to send extracted MCQ:", e)

    # ---- SEND AI MCQS ----
    if len(theory_text) > 500:
        await update.message.reply_text(
            "🧠 Generating additional MCQs from theory..."
        )

        ai_mcqs = generate_ai_mcqs(theory_text, count=25)

        for raw_q in ai_mcqs:
            mcq = sanitize_mcq(raw_q)
            if not mcq:
                continue

            try:
                await context.bot.send_poll(
                    chat_id=update.effective_chat.id,
                    question=mcq["question"],
                    options=mcq["options"],
                    type="quiz",
                    correct_option_id=mcq["answer_index"],
                )
                await asyncio.sleep(0.35)
                total += 1
            except Exception as e:
                print("Failed to send AI MCQ:", e)

    await update.message.reply_text(
        f"✅ Done. Total MCQs delivered: {total}"
    )


# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("MCQ Bot running")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()        r"(?:\(?a\)?\s*(.*?)\n)"
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
import os
import re
import io
import logging
from typing import List

import pdfplumber
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # set in Railway variables
MAX_MESSAGE_LENGTH = 3500  # Telegram safe limit

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =========================
# HELPERS
# =========================

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text)


def extract_existing_mcqs(text: str) -> List[str]:
    """
    Tries to detect MCQs already present in PDF.
    Looks for patterns like:
    1. Question?
       a) ...
       b) ...
    """
    mcqs = []
    pattern = re.compile(
        r"\n?\d+\.\s.*?(?:\n[a-dA-D][\).].*){2,}",
        re.DOTALL
    )
    matches = pattern.findall(text)
    for m in matches:
        cleaned = m.strip()
        if len(cleaned) > 30:
            mcqs.append(cleaned)
    return mcqs


def generate_ai_mcqs_from_theory(text: str, limit: int = 40) -> List[str]:
    """
    SAFE fallback AI logic (NO API).
    Converts theory sentences into MCQ-style questions.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    mcqs = []

    for s in sentences:
        if len(mcqs) >= limit:
            break
        if len(s) < 60:
            continue
        question = f"Q. What is meant by the following?\n{s.strip()}"
        options = (
            "A) Correct explanation\n"
            "B) Incorrect explanation\n"
            "C) Partially correct\n"
            "D) None of the above"
        )
        mcqs.append(f"{question}\n{options}")

    return mcqs


def chunk_text(text: str) -> List[str]:
    chunks = []
    while text:
        chunks.append(text[:MAX_MESSAGE_LENGTH])
        text = text[MAX_MESSAGE_LENGTH:]
    return chunks


# =========================
# HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Send me a PDF.\n"
        "I will:\n"
        "✔ Extract MCQs already present\n"
        "✔ Generate additional MCQs from theory\n"
        "✔ Send everything as text (safe & stable)"
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ Please send a PDF file.")
        return

    await update.message.reply_text("📄 PDF received. Processing…")

    file = await document.get_file()
    pdf_bytes = await file.download_as_bytearray()

    text = extract_text_from_pdf(pdf_bytes)

    if not text.strip():
        await update.message.reply_text("❌ Could not read text from PDF.")
        return

    existing_mcqs = extract_existing_mcqs(text)
    ai_mcqs = generate_ai_mcqs_from_theory(text)

    all_mcqs = existing_mcqs + ai_mcqs

    if not all_mcqs:
        await update.message.reply_text("⚠️ No MCQs could be generated.")
        return

    await update.message.reply_text(
        f"✅ Found {len(existing_mcqs)} MCQs in PDF\n"
        f"🤖 Generated {len(ai_mcqs)} new MCQs\n"
        f"📤 Sending now…"
    )

    full_text = "\n\n".join(
        f"{i+1}. {mcq}" for i, mcq in enumerate(all_mcqs)
    )

    for chunk in chunk_text(full_text):
        await update.message.reply_text(chunk)

    await update.message.reply_text(
        f"🎉 Done. Generated {len(all_mcqs)} MCQs."
    )


# =========================
# MAIN
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    print("🤖 MCQ Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
