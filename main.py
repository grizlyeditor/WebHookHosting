# hosting_bot_final_webhook.py

import telebot, os, subprocess, time, threading, shutil, psutil
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# === BOT CONFIG ===
BOT_TOKEN = '7718570853:AAGLRnxyQ-GJm2qvmQ7VXC-WEzgdK6DBQ1I'
bot = telebot.TeleBot(BOT_TOKEN)
hosting = {}

WEBHOOK_URL = "https://your-domain.com"  # ⚠️ Replace with your deployed domain
WEBHOOK_SECRET = "supersecret"

app = Flask(__name__)

# === TELEGRAM WEBHOOK ROUTE ===
@app.route(f"/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# === START HANDLER ===
@bot.message_handler(commands=['start'])
def start(m):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💻 Hosting"))
    bot.send_message(m.chat.id, "👋 Welcome to Hosting Panel!", reply_markup=kb)

# === HOSTING TIME CHOICE ===
@bot.message_handler(func=lambda m: m.text == "💻 Hosting")
def ask_time(m):
    uid = m.from_user.id
    hosting[uid] = {"step": "time"}
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⏱ 1 Hour", callback_data="host_60"),
        InlineKeyboardButton("📆 1 Day", callback_data="host_1440"),
        InlineKeyboardButton("🗓 7 Days", callback_data="host_10080"),
        InlineKeyboardButton("📅 1 Month", callback_data="host_43200")
    )
    kb.add(InlineKeyboardButton("🧮 Enter Custom Minutes", callback_data="host_custom"))
    bot.send_message(m.chat.id, "🕒 Choose hosting time:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("host_"))
def choose_time(call):
    uid = call.from_user.id
    code = call.data.split("_")[1]
    if code == "custom":
        bot.send_message(call.message.chat.id, "✍️ Send custom time in minutes:")
        hosting[uid]["step"] = "custom"
    else:
        mins = int(code)
        setup_upload_flow(call.message.chat.id, uid, mins)

@bot.message_handler(func=lambda m: m.from_user.id in hosting and hosting[m.from_user.id]["step"] == "custom")
def get_custom_minutes(m):
    try:
        mins = int(m.text.strip())
        uid = m.from_user.id
        setup_upload_flow(m.chat.id, uid, mins)
    except:
        bot.send_message(m.chat.id, "❌ Invalid number. Please send minutes like `30`, `120`, etc.")

def setup_upload_flow(chat_id, uid, mins):
    folder = f"hostings/user_{uid}"
    os.makedirs(folder, exist_ok=True)
    hosting[uid].update({
        "minutes": mins,
        "step": "upload",
        "folder": folder,
        "files": []
    })
    bot.send_message(chat_id, f"⏳ Hosting time set: `{mins} minutes`\n\n📤 Now send your `.py` file and extra files (e.g. `username.txt`)\n✅ Type `done` when finished.")

@bot.message_handler(content_types=['document'])
def save_file(m):
    uid = m.from_user.id
    if uid not in hosting or hosting[uid].get("step") != "upload":
        return
    folder = hosting[uid]["folder"]
    fname = m.document.file_name
    file_info = bot.get_file(m.document.file_id)
    data = bot.download_file(file_info.file_path)
    with open(os.path.join(folder, fname), "wb") as f:
        f.write(data)
    hosting[uid]["files"].append(fname)
    bot.send_message(m.chat.id, f"✅ Saved `{fname}`")

@bot.message_handler(func=lambda m: m.text.lower() == "done")
def run_script(m):
    uid = m.from_user.id
    if uid not in hosting or hosting[uid].get("step") != "upload":
        return
    folder = hosting[uid]["folder"]
    py_files = [f for f in hosting[uid]["files"] if f.endswith(".py")]
    if not py_files:
        bot.send_message(m.chat.id, "❌ No `.py` file found.")
        return
    main_file = py_files[0]
    try:
        bot.send_message(m.chat.id, "🟡 Hosting started...\n🔁 Preparing environment...\n⚙️ Please wait...")
        proc = subprocess.Popen(["python3", main_file], cwd=folder)
        end_time = time.time() + hosting[uid]["minutes"] * 60
        hosting[uid].update({"process": proc, "end": end_time, "step": "running"})
        bot.send_message(m.chat.id, f"✅ Bot is now running!\n🗓 Will stop after {hosting[uid]['minutes']} minutes.")
        threading.Thread(target=expire_hosting, args=(uid,), daemon=True).start()
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Error: {e}")

def expire_hosting(uid):
    while time.time() < hosting[uid]["end"]:
        time.sleep(5)
    try:
        proc = hosting[uid]["process"]
        if psutil.pid_exists(proc.pid):
            proc.kill()
        folder = hosting[uid]["folder"]
        if os.path.exists(folder):
            shutil.rmtree(folder)
        bot.send_message(uid, "⛔ Hosting time ended.\n🗑️ Files deleted and bot stopped.")
    except Exception as e:
        bot.send_message(uid, f"⚠️ Cleanup error: {e}")
    hosting.pop(uid, None)

# === LAUNCH WEBHOOK ===
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
