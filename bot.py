import os
import logging
import asyncio
from collections import defaultdict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    PollAnswerHandler, MessageHandler, ContextTypes, filters
)

from pypdf import PdfReader

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
QUIZ_SIZE = 50
TIME_PER_Q = 15
NEGATIVE_MARK = 0.25

logging.basicConfig(level=logging.INFO)

# ---------------- MEMORY ----------------
USERS = defaultdict(dict)
POLL_MAP = {}
LEADERBOARD = defaultdict(float)

# ---------------- HELPERS ----------------

def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for p in reader.pages:
        text += (p.extract_text() or "") + "\n"
    return text

def generate_mcqs_from_text(text, limit=120):
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 40]
    mcqs = []

    for s in sentences[:limit]:
        mcqs.append({
            "q": s[:250] + "?",
            "opt": ["True", "False", "Not mentioned", "Cannot be inferred"],
            "ans": 0
        })
    return mcqs

def split_mcqs(mcqs, size):
    return [mcqs[i:i+size] for i in range(0, len(mcqs), size)]

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 MCQ Quiz Bot\n\n"
        "• Upload PDF\n"
        "• Topic-wise quizzes\n"
        "• Timed model tests\n"
        "• Resume & Leaderboard\n\n"
        "📎 Send a PDF to begin."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    file = await update.message.document.get_file()

    path = f"/tmp/{user_id}.pdf"
    await file.download_to_drive(path)

    text = extract_text(path)
    mcqs = generate_mcqs_from_text(text)

    USERS[user_id] = {
        "mcqs": mcqs,
        "sets": split_mcqs(mcqs, QUIZ_SIZE),
        "score": 0,
        "current": 0
    }

    buttons = [
        [InlineKeyboardButton(
            f"Model Quiz {i+1} ({len(q)} Qs)",
            callback_data=f"quiz:{i}"
        )]
        for i, q in enumerate(USERS[user_id]["sets"])
    ]

    await update.message.reply_text(
        f"✅ Generated {len(mcqs)} MCQs\nSelect quiz:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    idx = int(query.data.split(":")[1])
    quiz = USERS[user_id]["sets"][idx]

    USERS[user_id]["current"] = idx
    USERS[user_id]["score"] = 0

    for q in quiz:
        poll = await context.bot.send_poll(
            chat_id=query.message.chat.id,
            question=q["q"],
            options=q["opt"],
            type="quiz",
            correct_option_id=q["ans"],
            is_anonymous=False,
            open_period=TIME_PER_Q
        )

        POLL_MAP[poll.poll.id] = (user_id, q["ans"])
        await asyncio.sleep(TIME_PER_Q + 1)

    score = USERS[user_id]["score"]
    LEADERBOARD[user_id] += score

    await query.message.reply_text(
        f"🏁 Quiz Completed\n"
        f"Score: {score} / {len(quiz)}"
    )

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll = update.poll_answer
    poll_id = poll.poll_id

    if poll_id not in POLL_MAP:
        return

    user_id, correct = POLL_MAP[poll_id]
    if poll.option_ids:
        if poll.option_ids[0] == correct:
            USERS[user_id]["score"] += 1
        else:
            USERS[user_id]["score"] -= NEGATIVE_MARK

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    idx = USERS[user_id].get("current", 0)
    await start_quiz(update, context)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Leaderboard\n\n"
    for uid, score in sorted(LEADERBOARD.items(), key=lambda x: -x[1]):
        text += f"{uid}: {score}\n"
    await update.message.reply_text(text or "No data yet")

# ---------------- MAIN ----------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern="^quiz"))
    app.add_handler(PollAnswerHandler(poll_answer))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    logging.info("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
