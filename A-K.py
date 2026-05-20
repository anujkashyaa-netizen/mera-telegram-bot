import logging
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# --- CONFIGURATION ---
TOKEN = "8991725410:AAGBfC643nS9QhcAKkkpL_rElXpWtfuvQOA"

CHANNEL_1 = "@anujkashyap12345"
CHANNEL_2 = "@anujkashyap123"

ADMIN_IDS = [6253468734, 8434061505]
PRIMARY_ADMIN = [6253468734, 8434061505]  

STORAGE_CHANNEL_ID = "@ANUJBOT3" 

DB_FILE = "anime_database.json"
HISTORY_FILE = "admin_history.json"

admin_state = {} 
admin_testing_mode = set()  
_db_cache = None
_history_cache = None

# --- DATABASE LOGIC ---
def load_json(filename):
    global _db_cache, _history_cache
    if filename == DB_FILE and _db_cache is not None: return _db_cache
    if filename == HISTORY_FILE and _history_cache is not None: return _history_cache

    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                if filename == DB_FILE: _db_cache = data
                if filename == HISTORY_FILE: _history_cache = data
                return data
        except:
            pass
    return {}

def save_json(filename, data):
    global _db_cache, _history_cache
    if filename == DB_FILE: _db_cache = data
    if filename == HISTORY_FILE: _history_cache = data
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def save_anime_to_db(anime_name, season, episode, file_id):
    db = load_json(DB_FILE)
    if anime_name not in db: db[anime_name] = {}
    if season not in db[anime_name]: db[anime_name][season] = {}
        
    db[anime_name][season][episode] = file_id
    save_json(DB_FILE, db)

    history = load_json(HISTORY_FILE)
    if "names" not in history: history["names"] = []
    if anime_name not in history["names"]:
        history["names"].append(anime_name)
        save_json(HISTORY_FILE, history)

# --- CHANNEL CHECK ---
async def is_joined(user_id, bot):
    for ch in [CHANNEL_1, CHANNEL_2]:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]: return False
        except:
            return False
    return True

# --- KEYBOARD BUILDERS ---
def build_admin_history_keyboard(prefix="adm_an_hist"):
    history = load_json(HISTORY_FILE)
    anime_list = history.get("names", [])
    inline_kb = []
    
    for idx, name in enumerate(anime_list):
        inline_kb.append([InlineKeyboardButton(name, callback_data=f"{prefix}|{idx}")])
            
    inline_kb.append([InlineKeyboardButton("➕ Type New Anime Name", callback_data=f"{prefix[:-8]}_new_anime")])
    return InlineKeyboardMarkup(inline_kb)

def build_seasons_keyboard(prefix="adm_sz"):
    inline_kb = []
    for r in range(1, 11, 2):
        inline_kb.append([
            InlineKeyboardButton(f"Season {r}", callback_data=f"{prefix}|Season {r}"),
            InlineKeyboardButton(f"Season {r+1}", callback_data=f"{prefix}|Season {r+1}")
        ])
    return InlineKeyboardMarkup(inline_kb)

def build_episodes_keyboard():
    inline_kb = []
    for r in range(1, 31, 3):
        inline_kb.append([
            InlineKeyboardButton(f"Ep {r}", callback_data=f"adm_ep|Episode {r}"),
            InlineKeyboardButton(f"Ep {r+1}", callback_data=f"adm_ep|Episode {r+1}"),
            InlineKeyboardButton(f"Ep {r+2}", callback_data=f"adm_ep|Episode {r+2}")
        ])
    return InlineKeyboardMarkup(inline_kb)

def build_user_keyboard():
    db = load_json(DB_FILE)
    inline_kb = []
    for idx, name in enumerate(db.keys()):
        inline_kb.append([InlineKeyboardButton(f"🎬 {name}", callback_data=f"usr_an_idx|{idx}")])
    return InlineKeyboardMarkup(inline_kb)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    fname = update.effective_user.first_name

    try:
        await update.message.delete()
    except:
        pass

    if uid in ADMIN_IDS and uid in admin_testing_mode:
        admin_testing_mode.remove(uid)

    if uid in ADMIN_IDS:
        if uid in admin_state: del admin_state[uid]
        
        help_text = (
            "👑 **WELCOME BACK, ADMIN PANEL!**\n\n"
            "Bot ke saare commands aur unka use niche diya gaya hai:\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "🛠️ **COMMANDS LIST:**\n"
            "▶️ `/start` - Admin command chart dekhne aur panel refresh karne ke liye.\n"
            "▶️ `/bulk` - Multi-upload (Batch Mode) chalu karne ke liye.\n"
            "❌ `/delete` - **[NEW]** Galat uploaded episode ko database se delete karne ke liye.\n"
            "▶️ `/test` - Admin ko 1 second me normal user bana dega testing ke liye.\n\n"
            "📁 **AUTO DETECTION:**\n"
            "💡 Chat mein direct koi bhi Video ya File send/forward karo, single file menu automatically aa jayega."
        )
        await context.bot.send_message(chat_id=uid, text=help_text, parse_mode="Markdown")
        return

    await trigger_user_flow(update, context, uid, fname)

# --- 🔥 USER CHAT CLEANING LOGIC (OPEN FOR ALL USERS) ---
async def clear_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    command = update.message.text.split()[0].lower()
    
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    today_date = datetime.now(timezone.utc).astimezone(tz_ist).date()
    
    current_msg_id = update.message.message_id
    status_msg = await update.message.reply_text("🧹 Chat saaf ki jaa rahi hai...")
    
    to_delete = []
    messages_checked = 0
    
    for msg_id in range(current_msg_id, max(1, current_msg_id - 1500), -1):
        if msg_id == status_msg.message_id:
            continue
            
        try:
            msg_check = await context.bot.forward_message(chat_id=uid, from_chat_id=uid, message_id=msg_id, protect_content=True)
            msg_date = msg_check.date.astimezone(tz_ist).date()
            await msg_check.delete()
            
            if command == "/clear1" and msg_date >= today_date:
                continue
                
            if command == "/clear2" and msg_date < today_date:
                continue
                
            to_delete.append(msg_id)
        except:
            messages_checked += 1
            if messages_checked > 100:
                break
            continue

    deleted_count = 0
    if to_delete:
        chunks = [to_delete[i:i + 100] for i in range(0, len(to_delete), 100)]
        for chunk in chunks:
            try:
                await context.bot.delete_messages(chat_id=uid, message_ids=chunk)
                deleted_count += len(chunk)
            except:
                for single_id in chunk:
                    try:
                        await context.bot.delete_message(chat_id=uid, message_id=single_id)
                        deleted_count += 1
                    except:
                        pass

    await status_msg.edit_text(f"✅ Cleanup successful! **{deleted_count}** messages removed.")
    await asyncio.sleep(2)
    try:
        await status_msg.delete()
    except:
        pass

# --- TEST MODE COMMAND FOR ADMIN ---
async def test_user_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    fname = update.effective_user.first_name
    
    try:
        await update.message.delete()
    except:
        pass
        
    if uid not in ADMIN_IDS:
        return

    admin_testing_mode.add(uid)
    
    await context.bot.send_message(
        chat_id=uid, 
        text="🧪 **Admin Testing Mode Activated!**\nAap temporary normal user ban chuke hain. Dubara admin banna ho toh `/start` likhein.\n\n👇 Interface niche chalu ho raha hai:",
        parse_mode="Markdown"
    )
    await trigger_user_flow(update, context, uid, fname)

# --- REUSABLE USER INTERFACE FUNCTION ---
async def trigger_user_flow(update, context, uid, fname):
    if uid not in ADMIN_IDS:
        asyncio.create_task(context.bot.send_message(PRIMARY_ADMIN, f"👤 **New User:** {fname}\n🆔 {uid}", parse_mode="Markdown"))

    if 'menu_msg_id' in context.user_data:
        try:
            await context.bot.delete_message(chat_id=uid, message_id=context.user_data['menu_msg_id'])
        except:
            pass

    v_file = "v.ogg"
    if os.path.exists(v_file):
        try:
            v_msg = await context.bot.send_voice(uid, v_file)
            context.user_data['last_voice_id'] = v_msg.message_id
        except: 
            pass

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1[1:]}"),
         InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2[1:]}")],
        [InlineKeyboardButton("✅ Verify & Continue", callback_data="verify_user")]
    ])
    
    sent_msg = await context.bot.send_message(
        chat_id=uid,
        text=f"👋 **Hi {fname}!**\n\nBot use karne ke liye niche dono channels join karke **Verify** button par click karein 👇\n\n🧹 *Tip: Aap chat saaf karne ke liye `/clear1` (purani chat) ya `/clear2` (aaj ki chat) likh sakte hain!*",
        reply_markup=btn,
        parse_mode="Markdown"
    )
    context.user_data['menu_msg_id'] = sent_msg.message_id

# --- BULK COMMAND FOR ADMIN ---
async def bulk_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS: return
    
    if uid in admin_testing_mode:
        await update.message.reply_text("⚠️ Pehle `/start` likh kar Testing mode se admin mode me wapas aayein!")
        return

    admin_state[uid] = {"mode": "bulk", "step": "choose_anime"}
    await update.message.reply_text(
        "🚀 **Multi-Upload (Bulk) Mode Active!**\n\nYeh saare episodes kis Anime ke hain? Niche se chuno ya naya naam type karo:",
        reply_markup=build_admin_history_keyboard(prefix="blk_an_hist")
    )

# --- ❌ DELETE EPISODE COMMAND FOR ADMIN ---
async def delete_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS or uid in admin_testing_mode: 
        return
        
    db = load_json(DB_FILE)
    if not db:
        await update.message.reply_text("⚠️ Database abhi poori tarah khali hai!")
        return
        
    inline_kb = []
    for idx, name in enumerate(db.keys()):
        inline_kb.append([InlineKeyboardButton(f"🗑️ {name}", callback_data=f"del_an_idx|{idx}")])
        
    await update.message.reply_text(
        "🛠️ **Delete Menu:**\nKis Anime ka galat episode delete karna hai? Niche se chuno 👇",
        reply_markup=InlineKeyboardMarkup(inline_kb)
    )

# --- MESSAGE HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # Commands ignore karne ke liye taaki text filter unhe block na kare
    if text and text.startswith('/'):
        return

    if uid in ADMIN_IDS and uid in admin_testing_mode:
        return

    if uid not in ADMIN_IDS:
        return

    # BULK MODE RUNNING
    if uid in admin_state and admin_state[uid].get("mode") == "bulk" and admin_state[uid].get("step") == "uploading":
        if update.message.document or update.message.video:
            fwd = await update.message.forward(STORAGE_CHANNEL_ID)
            file_id = fwd.document.file_id if fwd.document else fwd.video.file_id
            
            anime = admin_state[uid]["anime"]
            season = admin_state[uid]["season"]
            next_ep = admin_state[uid]["next_ep"]
            
            episode_str = f"Episode {next_ep}"
            save_anime_to_db(anime, season, episode_str, file_id)
            
            await update.message.reply_text(f"✅ Auto Saved: **{anime}** | **{season}** | **{episode_str}**", parse_mode="Markdown")
            admin_state[uid]["next_ep"] += 1
            return

    # SINGLE MODE RUNNING
    if (update.message.document or update.message.video) and (uid not in admin_state or admin_state[uid].get("mode") != "bulk"):
        fwd = await update.message.forward(STORAGE_CHANNEL_ID)
        file_id = fwd.document.file_id if fwd.document else fwd.video.file_id
        
        admin_state[uid] = {"file_id": file_id, "step": "choose_or_type", "mode": "single"}
        await update.message.reply_text(
            "📂 **Single Video Saved!**\n\nYeh kaun sa Anime hai? Niche se select karo 👇",
            reply_markup=build_admin_history_keyboard(prefix="adm_an_hist")
        )
        return

    # TEXT PROCESSING FOR ADMIN STEPS
    if text and uid in admin_state:
        step = admin_state[uid]["step"]
        mode = admin_state[uid].get("mode", "single")
        
        if step == "typing_anime_name":
            admin_state[uid]["anime"] = text
            admin_state[uid]["step"] = "select_season"
            prefix_str = "blk_sz" if mode == "bulk" else "adm_sz"
            await update.message.reply_text(f"📝 Anime Name Set: **{text}**\n\nAb **Season** select karo 👇", reply_markup=build_seasons_keyboard(prefix=prefix_str), parse_mode="Markdown")
            return
            
        elif step == "select_season":
            admin_state[uid]["season"] = text
            if mode == "bulk":
                admin_state[uid]["step"] = "typing_start_ep"
                await update.message.reply_text(f"📂 Season Set: **{text}**\n\n🔢 Yeh batch kaun se **Episode Number** se shuru karna hai? (E.g. 1):", parse_mode="Markdown")
            else:
                admin_state[uid]["step"] = "select_episode"
                await update.message.reply_text(f"🔢 Season Set: *{text}*\n\nAb niche se **Episode** chuno ya direct type karo 👇", reply_markup=build_episodes_keyboard(), parse_mode="Markdown")
            return

        elif step == "typing_start_ep" and mode == "bulk":
            if text.isdigit():
                admin_state[uid]["next_ep"] = int(text)
                admin_state[uid]["step"] = "uploading"
                await update.message.reply_text(
                    f"🔥 **BATCH MODE FULLY ACTIVE!**\n\n📌 Anime: **{admin_state[uid]['anime']}**\n📂 **{admin_state[uid]['season']}**\n🔢 Starting From: **Episode {text}**\n\n📥 Saare episodes ek saath forward ya send kar do!",
                    parse_mode="Markdown"
                )
            return
            
        elif step == "select_episode" and mode == "single":
            anime = admin_state[uid]["anime"]
            season = admin_state[uid]["season"]
            episode = f"Episode {text}" if text.isdigit() else text
            file_id = admin_state[uid]["file_id"]
            
            save_anime_to_db(anime, season, episode, file_id)
            del admin_state[uid]
            await update.message.reply_text(f"✅ **Success! Save ho gaya!**\n\n📌 Anime: {anime}\n📂 {season}\n🔢 {episode}", parse_mode="Markdown")
            return

# --- INLINE BUTTON CLICKS ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    uid = update.effective_user.id

    if data[0] == "verify_user":
        if uid not in ADMIN_IDS:
            joined = await is_joined(uid, context.bot)
            if not joined:
                return await query.edit_message_text("❌ Pehle dono channels mandatory join karo, phir click karna.")
        
        if 'last_voice_id' in context.user_data:
            try:
                await context.bot.delete_message(chat_id=uid, message_id=context.user_data['last_voice_id'])
            except:
                pass
        
        await query.edit_message_text(
            "✅ **Verification Successful!**\n\nNiche text panel par se apna pasandida Anime select karo ALL ANIME HINDI MA HA 👇", 
            reply_markup=build_user_keyboard()
        )
        return

    if data[0] == "go_home":
        await query.edit_message_text(
            "🏠 **Main Menu**\n\nNiche text panel par se apna pasandida Anime select karo ALL ANIME HINDI MA HA 👇", 
            reply_markup=build_user_keyboard()
        )
        return

    if data[0] == "usr_an_idx":
        db = load_json(DB_FILE)
        if not db:
            return await query.edit_message_text("⚠️ Abhi database mein koi anime available nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="go_home")]]))
            
        anime_name = list(db.keys())[int(data[1])]
        inline_kb = []
        for sz in db[anime_name].keys():
            inline_kb.append([InlineKeyboardButton(f"📁 {sz}", callback_data=f"usr_sz|{data[1]}|{sz}")])
            
        inline_kb.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="go_home")])
        await query.edit_message_text(f"🎬 **{anime_name}**\n\nKaun sa Season dekhna hai?", reply_markup=InlineKeyboardMarkup(inline_kb))
        return

    if data[0] == "usr_sz":
        db = load_json(DB_FILE)
        anime_name = list(db.keys())[int(data[1])]
        season = data[2]
        inline_kb = []
        
        sorted_eps = sorted(db[anime_name][season].keys(), key=lambda x: [int(s) if s.isdigit() else s.lower() for s in x.split()])
        for ep in sorted_eps:
            inline_kb.append([InlineKeyboardButton(f"▶️ {ep}", callback_data=f"usr_ep|{data[1]}|{season}|{ep}")])
            
        inline_kb.append([
            InlineKeyboardButton("🔙 Back to Seasons", callback_data=f"usr_an_idx|{data[1]}"),
            InlineKeyboardButton("🏠 Home Menu", callback_data="go_home")
        ])
        await query.edit_message_text(f"🎬 **{anime_name}**\n📂 **{season}**\n\nKaun sa Episode dekhna hai?", reply_markup=InlineKeyboardMarkup(inline_kb))
        return

    if data[0] == "usr_ep":
        db = load_json(DB_FILE)
        anime_name = list(db.keys())[int(data[1])]
        season = data[2]
        file_id = db[anime_name][season][data[3]]
        await context.bot.send_document(chat_id=uid, document=file_id, caption=f"🎬 **{anime_name}**\n📂 {season}\n🔢 {data[3]}\n\n🍿 Enjoy!")
        return

    # --- ❌ ADMIN CALLBACKS FOR DELETION ---
    if data[0] == "del_an_idx":
        db = load_json(DB_FILE)
        anime_name = list(db.keys())[int(data[1])]
        inline_kb = []
        for sz in db[anime_name].keys():
            inline_kb.append([InlineKeyboardButton(f"📁 {sz}", callback_data=f"del_sz|{data[1]}|{sz}")])
        await query.edit_message_text(f"🗑️ Anime: **{anime_name}**\nKaun se Season ka episode hatana hai?", reply_markup=InlineKeyboardMarkup(inline_kb), parse_mode="Markdown")
        return

    if data[0] == "del_sz":
        db = load_json(DB_FILE)
        anime_name = list(db.keys())[int(data[1])]
        season = data[2]
        inline_kb = []
        for ep in db[anime_name][season].keys():
            inline_kb.append([InlineKeyboardButton(f"❌ Delete {ep}", callback_data=f"del_ep|{data[1]}|{season}|{ep}")])
        await query.edit_message_text(f"🗑️ Anime: **{anime_name}** | **{season}**\nKis episode ko permanent delete karna hai?", reply_markup=InlineKeyboardMarkup(inline_kb), parse_mode="Markdown")
        return

    if data[0] == "del_ep":
        db = load_json(DB_FILE)
        anime_name = list(db.keys())[int(data[1])]
        season = data[2]
        episode = data[3]
        
        if anime_name in db and season in db[anime_name] and episode in db[anime_name][season]:
            del db[anime_name][season][episode]
            
            # Agar poora season khali ho gaya toh season hata do
            if not db[anime_name][season]:
                del db[anime_name][season]
            # Agar poora anime khali ho gaya toh anime hata do
            if not db[anime_name]:
                del db[anime_name]
                
            save_json(DB_FILE, db)
            await query.edit_message_text(f"✅ **Permanent Deleted:**\n**{anime_name}**' ke **{season}** ka **{episode}** database se saaf kar diya gaya hai!", parse_mode="Markdown")
        else:
            await query.edit_message_text("⚠️ Yeh episode pehle hi delete ho chuka hai ya mila nahi.")
        return

    # --- ADMIN WORKFLOW CALLBACKS ---
    if data[0] in ["adm_new_anime", "blk_new_anime"]:
        admin_state[uid]["step"] = "typing_anime_name"
        await query.edit_message_text("✍️ **Naye Anime ka naam chat mein type karke bhejo:**")
        return

    if data[0] in ["adm_an_hist", "blk_an_hist"]:
        history = load_json(HISTORY_FILE)
        anime_name = history["names"][int(data[1])]
        admin_state[uid]["anime"] = anime_name
        admin_state[uid]["step"] = "select_season"
        prefix = "blk_sz" if "blk" in data[0] else "adm_sz"
        await query.edit_message_text(f"Selected Anime: **{anime_name}**\n\nNiche se **Season** select karo 👇", reply_markup=build_seasons_keyboard(prefix=prefix), parse_mode="Markdown")
        return

    if data[0] in ["adm_sz", "blk_sz"]:
        admin_state[uid]["season"] = data[1]
        if "blk" in data[0]:
            admin_state[uid]["step"] = "typing_start_ep"
            await query.edit_message_text(f"📂 Season Set: **{data[1]}**\n\n🔢 Yeh batch kaun se **Episode Number** se shuru karna hai? Type karke bhejo:")
        else:
            admin_state[uid]["step"] = "select_episode"
            await query.edit_message_text(f"📂 Season Set: **{data[1]}**\n\nAb niche se **Episode** chuno ya direct type karo 👇", reply_markup=build_episodes_keyboard(), parse_mode="Markdown")
        return

    if data[0] == "adm_ep":
        save_anime_to_db(admin_state[uid]["anime"], admin_state[uid]["season"], data[1], admin_state[uid]["file_id"])
        del admin_state[uid]
        await query.edit_message_text("✅ **Success! Single file save ho gayi bhai!**")
        return

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bulk", bulk_start)) 
    app.add_handler(CommandHandler("test", test_user_flow))  
    
    # ❌ Admin Delete Handler Link Kiya
    app.add_handler(CommandHandler("delete", delete_episode_start))
    
    # Users ke clear handlers
    app.add_handler(CommandHandler("clear1", clear_chat_history))
    app.add_handler(CommandHandler("clear2", clear_chat_history))
    
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL | filters.VIDEO, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback)) 
    print("🚀 ANUJ_KASHYAP Multi-Admin Premium System Active...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
