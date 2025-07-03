import telebot, os, subprocess, time, threading, shutil, psutil, json, requests
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputFile

BOT_TOKEN = os.environ.get("7718570853:AAGLRnxyQ-GJm2qvmQ7VXC-WEzgdK6DBQ1I")  # Must be set in .env or Render env
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Example: https://yourapi.onrender.com/webhook

bot = telebot.TeleBot(BOT_TOKEN)
hosting = {}  # user_id → step, files, etc.

def make_user_dir(uid):
    folder = f"hostings/user_{uid}"
    os.makedirs(folder, exist_ok=True)
    return folder

@bot.message_handler(commands=['start'])
def start(m):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💻 Hosting", "🔑 JWT Token Generator")
    bot.send_message(m.chat.id, "👋 Welcome! Choose an option:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "💻 Hosting")
def ask_time(m):
    uid = m.from_user.id
    hosting[uid] = {"step": "time"}
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⏱ 1 Hour", callback_data="host_60"),
        InlineKeyboardButton("📆 1 Day", callback_data="host_1440"),
    )
    kb.add(
        InlineKeyboardButton("🗓 7 Days", callback_data="host_10080"),
        InlineKeyboardButton("📅 1 Month", callback_data="host_43200"),
    )
    kb.add(InlineKeyboardButton("🧮 Custom Minutes", callback_data="host_custom"))
    bot.send_message(m.chat.id, "🕒 Select hosting time:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("host_"))
def select_time(call):
    uid = call.from_user.id
    value = call.data.split("_")[1]
    if value == "custom":
        hosting[uid]["step"] = "custom"
        bot.send_message(call.message.chat.id, "✍️ Send custom time (in minutes):")
    else:
        mins = int(value)
        start_file_upload(call.message.chat.id, uid, mins)

@bot.message_handler(func=lambda m: m.from_user.id in hosting and hosting[m.from_user.id]["step"] == "custom")
def receive_custom_minutes(m):
    uid = m.from_user.id
    try:
        mins = int(m.text.strip())
        start_file_upload(m.chat.id, uid, mins)
    except:
        bot.send_message(m.chat.id, "❌ Invalid number. Please send only numbers like `30`, `120`, etc.")

def start_file_upload(chat_id, uid, mins):
    folder = make_user_dir(uid)
    hosting[uid].update({"step": "upload", "minutes": mins, "folder": folder, "files": []})
    bot.send_message(chat_id, f"⏳ Hosting for `{mins} minutes`\n📤 Send your `.py` and any required files\n✅ Type `done` when you're ready.")

@bot.message_handler(content_types=['document'])
def save_file(m):
    uid = m.from_user.id
    if uid not in hosting: return
    step = hosting[uid].get("step")
    folder = hosting[uid]["folder"]
    file_info = bot.get_file(m.document.file_id)
    data = bot.download_file(file_info.file_path)
    file_path = os.path.join(folder, m.document.file_name)
    with open(file_path, "wb") as f:
        f.write(data)
    if step == "upload":
        hosting[uid]["files"].append(m.document.file_name)
        bot.send_message(m.chat.id, f"✅ Saved `{m.document.file_name}`")
    elif step == "jwt":
        handle_jwt_file(m, file_path)

@bot.message_handler(func=lambda m: m.text.lower() == "done")
def run_script(m):
    uid = m.from_user.id
    if uid not in hosting or hosting[uid]["step"] != "upload":
        return
    folder = hosting[uid]["folder"]
    py_files = [f for f in hosting[uid]["files"] if f.endswith(".py")]
    if not py_files:
        bot.send_message(m.chat.id, "❌ No `.py` file found.")
        return
    main_file = py_files[0]
    main_path = os.path.join(folder, main_file)

    try:
        with open(main_path, 'rb') as f:
            files = {'file': (main_file, f)}
            data = {'uid': uid, 'minutes': hosting[uid]['minutes']}
            r = requests.post(WEBHOOK_URL, data=data, files=files)
        if r.status_code == 200:
            result = r.json()
            output = result.get("output", result.get("error", "No output"))
            bot.send_message(m.chat.id, f"✅ Hosted via Webhook\n📤 Output:\n```\n{output[:4000]}\n```", parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, f"❌ Webhook Error: {r.status_code}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Exception: {e}")

    # Clean up
    try:
        shutil.rmtree(folder)
    except:
        pass
    hosting.pop(uid, None)

# ===== 🔑 JWT TOKEN GENERATOR =====
@bot.message_handler(func=lambda m: m.text == "🔑 JWT Token Generator")
def ask_jwt(m):
    uid = m.from_user.id
    folder = make_user_dir(uid)
    hosting[uid] = {"step": "jwt", "folder": folder}
    bot.send_message(m.chat.id, "📎 Send your `.json` file with UID and Passwords.")

def handle_jwt_file(m, path):
    uid = m.from_user.id
    bot.send_message(m.chat.id, "⚙️ Generating tokens...")
    try:
        creds = json.load(open(path))
        output = []
        log = []
        for user in creds:
            uid_val = user.get("uid")
            pwd = user.get("password")
            if not uid_val or not pwd:
                log.append(f"❌ Skipped invalid entry")
                continue
            url = f"https://jw-ttoken.vercel.app/token?uid={uid_val}&password={pwd}"
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    token = r.text.strip()
                    output.append({"uid": uid_val, "token": token})
                    log.append(f"✅ {uid_val}")
                else:
                    log.append(f"❌ {uid_val} (code {r.status_code})")
            except:
                log.append(f"⚠️ {uid_val} (request error)")

        out_path = os.path.join(hosting[uid]["folder"], "tokens.json")
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        bot.send_message(m.chat.id, "\n".join(log[-20:]))
        bot.send_document(m.chat.id, InputFile(out_path))
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")
    hosting.pop(uid, None)

# Start polling
bot.infinity_polling()
