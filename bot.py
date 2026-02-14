import os
import re
import asyncio
import logging
from collections import defaultdict

from telegram import Update
from telegram.constants import PollType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    PollAnswerHandler,
    ContextTypes,
    filters,
)

from PyPDF2 import PdfReader

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # set in Railway
QUESTIONS_PER_QUIZ = 50
TIME_LIMIT = 20  # seconds per question
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_scores = defaultdict(int)
user_progress = defaultdict(int)
active_quizzes = defaultdict(list)

# ---------------- UTILITIES ----------------

def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    text = []
    for page in reader.pages:
        if page.extract_text():
            text.append(page.extract_text())
    return "\n".join(text)


def extract_existing_mcqs(text: str):
    """
    Extracts MCQs already present in PDF (A/B/C/D format)
    """
    mcqs = []
    pattern = re.compile(
        r"(Q\d+.*?\?)\s*A\.\s*(.*?)\s*B\.\s*(.*?)\s*C\.\s*(.*?)\s*D\.\s*(.*?)\s*Answer[:\-]?\s*([A-D])",
        re.S | re.I,
    )

    for match in pattern.findall(text):
        question, a, b, c, d, ans = match
        mcqs.append({
            "q": question.strip(),
            "options": [a, b, c, d],
            "answer": ord(ans.upper()) - ord("A"),
        })
    return mcqs


def generate_ai_mcqs_from_text(text: str, limit: int):
    """
    Lightweight AI-style MCQ generation (no external API)
    """
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 60]
    mcqs = []

    for s in sentences[:limit]:
        mcqs.append({
            "q": f"What is the correct statement regarding: {s[:80]}…?",
            "options": [
                s[:60],
                s[10:70],
                s[20:80],
                s[30:90],
            ],
            "answer": 0,
        })

    return mcqs


def split_quizzes(mcqs):
    return [
        mcqs[i:i + QUESTIONS_PER_QUIZ]
        for i in range(0, len(mcqs), QUESTIONS_PER_QUIZ)
    ]

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 **MCQ PDF Quiz Bot**\n\n"
        "➡️ Send a PDF\n"
        "➡️ Get AI + existing MCQs\n"
        "➡️ Timed quiz mode\n"
        "➡️ Score summary\n\n"
        "Type /score anytime to see your score.",
        parse_mode="Markdown"
    )


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file = await doc.get_file()
    path = f"/tmp/{doc.file_name}"
    await file.download_to_drive(path)

    await update.message.reply_text("📖 Reading PDF…")

    text = extract_text_from_pdf(path)

    pdf_mcqs = extract_existing_mcqs(text)
    ai_mcqs = generate_ai_mcqs_from_text(text, max(0, 150 - len(pdf_mcqs)))

    all_mcqs = pdf_mcqs + ai_mcqs
    quizzes = split_quizzes(all_mcqs)

    active_quizzes[update.effective_user.id] = quizzes
    user_progress[update.effective_user.id] = 0

    await update.message.reply_text(
        f"✅ Found **{len(all_mcqs)} MCQs**\n"
        f"📦 Split into **{len(quizzes)} quizzes** (50 each)\n\n"
        f"Send /quiz to start Quiz 1",
        parse_mode="Markdown"
    )


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in active_quizzes:
        await update.message.reply_text("❌ Upload a PDF first.")
        return

    quiz_index = user_progress[uid] // QUESTIONS_PER_QUIZ
    quiz = active_quizzes[uid][quiz_index]

    await update.message.reply_text(
        f"🎯 **Starting Quiz {quiz_index + 1}**\n"
        f"⏱ {TIME_LIMIT}s per question",
        parse_mode="Markdown"
    )

    for q in quiz:
        poll = await update.message.reply_poll(
            question=q["q"],
            options=q["options"],
            type=PollType.QUIZ,
            correct_option_id=q["answer"],
            is_anonymous=False,
            open_period=TIME_LIMIT,
        )
        context.bot_data[poll.poll.id] = q["answer"]
        await asyncio.sleep(TIME_LIMIT + 1)

    user_progress[uid] += QUESTIONS_PER_QUIZ
    await update.message.reply_text("✅ Quiz finished. Send /quiz for next quiz.")


async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    correct = context.bot_data.get(answer.poll_id)

    if correct is not None and answer.option_ids:
        if answer.option_ids[0] == correct:
            user_scores[answer.user.id] += 1


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    score = user_scores.get(update.effective_user.id, 0)
    await update.message.reply_text(f"🏆 Your Score: **{score}**", parse_mode="Markdown")


# ---------------- MAIN ----------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", start_quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(PollAnswerHandler(poll_answer))

    logger.info("MCQ Bot running")
    app.run_polling()


if __name__ == "__main__":
    main()
