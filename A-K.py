import logging, os, json, asyncio
from gtts import gTTS
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# --- CONFIGURATION ---
TOKEN = "8656659663:AAGVS3jeK_-eL9ulQ2wWnBTm7uBPH3IiG5s"

CHANNEL_1 = "@anujkashyap12345"
CHANNEL_2 = "@anujkashyap123"

ADMIN_ID = 8434061505
STORAGE_CHANNEL_ID = "@my_test_storage"

DB_FILE = "database.json"

temp_storage = {}
user_history = {}

# --- DATABASE ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            pass

    return {
        "gaming": [],
        "jio": [],
        "airtel": [],
        "vi": []
    }

def save_to_db(cat, fid):
    db = load_db()

    if fid not in db.get(cat.lower(), []):
        db.setdefault(cat.lower(), []).append(fid)

        with open(DB_FILE, "w") as f:
            json.dump(db, f)

# --- CLEAR SCREEN ---
async def clear_screen(uid, context):
    if uid in user_history:
        tasks = []

        for mid in user_history[uid]:
            tasks.append(
                context.bot.delete_message(uid, mid)
            )

        await asyncio.gather(*tasks, return_exceptions=True)

        user_history[uid] = []

# --- CHANNEL CHECK ---
async def is_joined(user_id, bot):
    channels = [CHANNEL_1, CHANNEL_2]

    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, user_id)

            if member.status not in [
                "member",
                "administrator",
                "creator"
            ]:
                return False

        except:
            return False

    return True

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    fname = update.effective_user.first_name

    if uid not in user_history:
        user_history[uid] = []

    user_history[uid].append(update.message.message_id)

    number = "Unknown"

    asyncio.create_task(
        context.bot.send_message(
            ADMIN_ID,
            f"👤 **New User:** {fname}\n🆔 {uid}\n📞 {number}",
            parse_mode="Markdown"
        )
    )

    v_file = "v.ogg"

    if not os.path.exists(v_file):
        gTTS(
            text="Namaste, join karke verify dabayein.",
            lang='hi'
        ).save(v_file)

    with open(v_file, "rb") as vf:
        v_msg = await context.bot.send_voice(uid, vf)

    user_history[uid].append(v_msg.message_id)

    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join 1",
                url=f"https://t.me/{CHANNEL_1[1:]}"
            ),

            InlineKeyboardButton(
                "📢 Join 2",
                url=f"https://t.me/{CHANNEL_2[1:]}"
            )
        ]
    ])

    m1 = await update.message.reply_text(
        f"👋 **Hi {fname}!**\n\nJoin channels then click verify.",
        reply_markup=btn,
        parse_mode="Markdown"
    )

    m2 = await update.message.reply_text(
        "👇",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("✅ Verify & Continue")]
            ],
            resize_keyboard=True
        )
    )

    user_history[uid].extend([
        m1.message_id,
        m2.message_id
    ])

# --- CLEAR COMMAND ---
async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id

    if uid not in user_history:
        user_history[uid] = []

    user_history[uid].append(update.message.message_id)

    await clear_screen(uid, context)

    await context.bot.send_message(
        uid,
        "🧹 **Chat Cleared!**\n\n/start dabayein.",
        parse_mode="Markdown"
    )

# --- MESSAGE HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    text = update.message.text

    if uid not in user_history:
        user_history[uid] = []

    user_history[uid].append(update.message.message_id)

    main_menu = ReplyKeyboardMarkup(
        [
            ["🎮 Gaming", "🌐 Jio"],
            ["📁 Airtel", "📶 Vi"]
        ],
        resize_keyboard=True
    )

    # VERIFY
    if text == "✅ Verify & Continue":

        joined = await is_joined(uid, context.bot)

        if not joined:
            return await update.message.reply_text(
                "❌ Pehle dono channels join karo."
            )

        await clear_screen(uid, context)

        await context.bot.send_message(
            uid,
            "✅ **Verified Successfully!**\n\nCategory choose karo 👇",
            reply_markup=main_menu,
            parse_mode="Markdown"
        )

        return

    # CATEGORY SYSTEM
    cats = {
        "🎮 Gaming": "gaming",
        "🌐 Jio": "jio",
        "📁 Airtel": "airtel",
        "📶 Vi": "vi"
    }

    if text in cats:

        files = load_db().get(cats[text], [])

        if not files:
            return await update.message.reply_text(
                "⚠️ Folder khali hai."
            )

        tasks = []

        for f_id in files:
            tasks.append(
                context.bot.send_document(uid, f_id)
            )

        await asyncio.gather(*tasks)

        return

    # ADMIN PANEL
    if uid == ADMIN_ID:

        if text and text.startswith("Save in "):

            cat = text.replace(
                "Save in ",
                ""
            ).lower()

            fid = temp_storage.pop(uid, None)

            if fid:

                save_to_db(cat, fid)

                await update.message.reply_text(
                    "✅ Saved Successfully!",
                    reply_markup=main_menu
                )

        elif update.message.document:

            fwd = await update.message.forward(
                STORAGE_CHANNEL_ID
            )

            temp_storage[uid] = fwd.document.file_id

            await update.message.reply_text(
                "📂 Folder choose karo:",
                reply_markup=ReplyKeyboardMarkup(
                    [
                        ["Save in Gaming", "Save in Jio"],
                        ["Save in Airtel", "Save in Vi"]
                    ],
                    resize_keyboard=True
                )
            )

# --- MAIN ---
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("clear", clear_cmd)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT | filters.Document.ALL,
            handle_message
        )
    )

    print("🚀 Turbo Bot Running...")

    app.run_polling(
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()