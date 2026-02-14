import os, json, time, hashlib, logging, requests, re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from pypdf import PdfReader

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODEL = "mistralai/mistral-7b-instruct"
QUIZ_SIZE = 50
QUIZ_DIR = "quizzes"
USED_FILE = "used_questions.json"

os.makedirs(QUIZ_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

# ---------------- UTIL ---------------- #

def load_used():
    return set(json.load(open(USED_FILE))) if os.path.exists(USED_FILE) else set()

def save_used(s):
    json.dump(list(s), open(USED_FILE, "w"))

def qhash(q):
    return hashlib.sha256(q.lower().encode()).hexdigest()

# ---------------- PDF ---------------- #

def extract_text(path):
    reader = PdfReader(path)
    text = ""
    for p in reader.pages:
        t = p.extract_text()
        if t:
            text += t + "\n"
    return text

def chunk_text(text, size=4500):
    return [text[i:i+size] for i in range(0, len(text), size)]

# ---------------- OPENROUTER ---------------- #

def call_openrouter(chunk):
    prompt = f"""
Generate MEDIUM difficulty competitive exam MCQs.

STRICT RULES:
- Exactly 4 options
- Only one correct answer
- No Aparchit
- Clean English
- No explanations
- Output JSON ONLY

FORMAT:
[
 {{"question":"...","options":["A","B","C","D"],"answer":0}}
]

TEXT:
{chunk}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6
        },
        timeout=120
    )

    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def extract_json(text):
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except:
        return []

def generate_mcqs(full_text):
    mcqs = []
    chunks = chunk_text(full_text)

    for chunk in chunks:
        try:
            raw = call_openrouter(chunk)
            parsed = extract_json(raw)
            mcqs.extend(parsed)
        except Exception as e:
            logging.error(e)
        time.sleep(1)

    return mcqs

# ---------------- BOT ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Send a PDF.\n"
        "I will create MEDIUM-level quiz bundles.\n"
        "Each quiz = 50 questions.\n"
        "Use /quiz 1 later."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("📥 Downloading PDF...")

    f = await msg.document.get_file()
    path = "input.pdf"
    await f.download_to_drive(path)

    await msg.reply_text("📖 Extracting text...")
    text = extract_text(path)

    await msg.reply_text("🧠 Generating MCQs...")
    raw = generate_mcqs(text)

    used = load_used()
    final = []

    for m in raw:
        q = m.get("question", "").strip()
        if not q or "aparchit" in q.lower():
            continue
        h = qhash(q)
        if h in used:
            continue
        if len(m.get("options", [])) != 4:
            continue
        used.add(h)
        final.append(m)

    save_used(used)

    if not final:
        await msg.reply_text("❌ MCQ generation failed. Try another PDF.")
        return

    quizzes = [final[i:i+QUIZ_SIZE] for i in range(0, len(final), QUIZ_SIZE)]

    for i, q in enumerate(quizzes, 1):
        with open(f"{QUIZ_DIR}/quiz_{i}.json", "w") as f:
            json.dump(q, f, indent=2)

    await msg.reply_text(
        f"✅ Generated {len(final)} MCQs\n"
        f"📦 {len(quizzes)} quizzes created\n\n"
        f"Use /quiz 1, /quiz 2 anytime"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /quiz 1")
        return

    path = f"{QUIZ_DIR}/quiz_{context.args[0]}.json"
    if not os.path.exists(path):
        await update.message.reply_text("❌ Quiz not found.")
        return

    quiz = json.load(open(path))
    await update.message.reply_text(f"📘 Quiz {context.args[0]} starting")

    for q in quiz:
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=q["question"],
            options=q["options"],
            type="quiz",
            correct_option_id=q["answer"],
            is_anonymous=True,
        )
        time.sleep(0.5)

# ---------------- MAIN ---------------- #

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    logging.info("MCQ Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
