from flask import Flask, request
import telebot
import os
import threading
import subprocess
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8128064097:AAEZpZ-XV660gElE_cHAl2QnIhvHM9O76Rs"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

hosting_data = {}

@app.route('/')
def home():
    return "🤖 Hosting Bot is Running!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("💻 Hosting"))
    bot.send_message(message.chat.id, "👋 Welcome to Hosting Bot!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💻 Hosting")
def ask_time_handler(message):
    user_id = message.from_user.id
    hosting_data[user_id] = {"step": "choose_time"}
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⏱ 1 Hour", callback_data="time_60"),
        InlineKeyboardButton("📆 1 Day", callback_data="time_1440")
    )
    kb.add(
        InlineKeyboardButton("🗓 7 Days", callback_data="time_10080"),
        InlineKeyboardButton("🗓 1 Month", callback_data="time_43200")
    )
    bot.send_message(message.chat.id, "Select your hosting time:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("time_"))
def confirm_time_handler(call):
    user_id = call.from_user.id
    minutes = int(call.data.split("_")[1])
    hosting_data[user_id] = {"step": "await_confirm", "time": minutes}
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Confirm", callback_data="confirm_time"))
    bot.edit_message_text(f"You selected: {minutes} minutes. Confirm?",
                          call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "confirm_time")
def wait_for_file(call):
    user_id = call.from_user.id
    folder = f"hosting/user_{user_id}"
    os.makedirs(folder, exist_ok=True)
    hosting_data[user_id]["step"] = "await_file"
    hosting_data[user_id]["folder"] = folder
    bot.edit_message_text("✅ Time confirmed. Now send your `.py` file. Optionally also send `requirements.txt`.",
                          call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['document'])
def file_handler(message):
    user_id = message.from_user.id
    if hosting_data.get(user_id, {}).get("step") != "await_file":
        return
    doc = message.document
    folder = hosting_data[user_id]["folder"]
    path = os.path.join(folder, doc.file_name)
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    with open(path, 'wb') as f:
        f.write(downloaded)
    bot.reply_to(message, f"📂 File `{doc.file_name}` saved.", parse_mode='Markdown')
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("▶️ Start Hosting", callback_data="start_hosting"))
    bot.send_message(message.chat.id, "✅ Ready to host your file.", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "start_hosting")
def start_hosting(call):
    user_id = call.from_user.id
    data = hosting_data.get(user_id)
    folder = data.get("folder")
    py_files = [f for f in os.listdir(folder) if f.endswith(".py")]
    if not py_files:
        bot.send_message(call.message.chat.id, "❌ No .py file found.")
        return
    requirements_path = os.path.join(folder, "requirements.txt")
    if os.path.exists(requirements_path):
        subprocess.call(["pip3", "install", "-r", requirements_path])
    filepath = os.path.join(folder, py_files[0])
    def run_script():
        subprocess.call(["python3", filepath])
    threading.Thread(target=run_script).start()
    bot.send_message(call.message.chat.id, "✅ Your file is now running in background.")
