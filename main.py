# main.py

import os, time, json, shutil, subprocess, threading, requests, psutil
from flask import Flask, request
import telebot
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, InputFile

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
hosting = {}  # user_id → step, folder, etc.

# ========== ROUTES ========== #

@app.route('/')
def home():
    return "✅ Webhook Bot is Live"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return 'ok'
    return 'forbidden', 403

@app.before_first_request
def setup_webhook():
    time.sleep(1)
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook set to {WEBHOOK_URL}")

# ========== TELEGRAM BOT HANDLERS ========== #

def make_user_dir(uid):
    folder = f"hostings/user_{uid}"
    os.makedirs(folder, exist_ok=True)
    return folder

@bot.message_handler(commands=['start'])
def start(m):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💻 Hosting", "🔑 JWT Token Generator")
    bot.send_message(m.chat.id, "👋 Welcome to Webhook Hosting Bot!", reply_markup=kb)

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
        bot.send_message(call.message.chat.id, "⏳ Send custom time in minutes:")
    else:
        start_file_upload(call.message.chat.id, uid, int(value))

@bot.message_handler(func=lambda m: m.from_user.id in hosting and hosting[m.from_user.id]["step"] == "custom")
def custom_minutes(m):
    try:
        mins = int(m.text.strip())
        start_file_upload(m.chat.id, m.from_user.id, mins)
    except:
        bot.send_message(m.chat.id, "❌ Invalid number. Please send only digits like `60`, `120`")

def start_file_upload(chat_id, uid, mins):
    folder = make_user_dir(uid)
    hosting[uid].update({"step": "upload", "minutes": mins, "folder": folder, "files": []})
    bot.send_message(chat_id, f"📤 Send your `.py` and other required files\n✅ Type `done` when you're ready.")

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
def run_uploaded(m):
    uid = m.from_user.id
    if uid not in hosting or hosting[uid]["step"] != "upload":
        return
    folder = hosting[uid]["folder"]
    py_files = [f for f in hosting[uid]["files"] if f.endswith(".py")]
    if not py_files:
        bot.send_message(m.chat.id, "❌ No `.py` file found.")
        return
    main_file = py_files[0]
    try:
        proc = subprocess.Popen(["python3", main_file], cwd=folder)
        end = time.time() + hosting[uid]['minutes'] * 60
        hosting[uid].update({"step": "running", "process": proc, "end": end})
        bot.send_message(m.chat.id, f"✅ Running `{main_file}` for {hosting[uid]['minutes']} minutes")
        threading.Thread(target=auto_kill, args=(uid,)).start()
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

def auto_kill(uid):
    while time.time() < hosting[uid]['end']:
        time.sleep(5)
    try:
        proc = hosting[uid]['process']
        if psutil.pid_exists(proc.pid):
            proc.kill()
        shutil.rmtree(hosting[uid]["folder"])
        bot.send_message(uid, "⛔ Time finished. Hosting ended.")
    except Exception as e:
        bot.send_message(uid, f"⚠️ Error during cleanup: {e}")
    hosting.pop(uid, None)

# ========== JWT TOKEN GEN ==========
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
        output, log = [], []
        for user in creds:
            uid_val = user.get("uid")
            pwd = user.get("password")
            if not uid_val or not pwd:
                log.append("❌ Invalid entry")
                continue
            try:
                r = requests.get(f"https://jw-ttoken.vercel.app/token?uid={uid_val}&password={pwd}", timeout=10)
                token = r.text.strip() if r.status_code == 200 else "ERR"
                if token != "ERR":
                    output.append({"uid": uid_val, "token": token})
                    log.append(f"✅ {uid_val}")
                else:
                    log.append(f"❌ {uid_val}")
            except:
                log.append(f"⚠️ {uid_val} (request fail)")

        out_path = os.path.join(hosting[uid]["folder"], "tokens.json")
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        bot.send_message(m.chat.id, "\n".join(log[-20:]))
        bot.send_document(m.chat.id, InputFile(out_path))
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")
    hosting.pop(uid, None)

# ========== RUN APP ========== #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
