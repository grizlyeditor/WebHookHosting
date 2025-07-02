from flask import Flask, request
import telebot

# 🔐 Bot token yahan daal do
BOT_TOKEN = "8128064097:AAEZpZ-XV660gElE_cHAl2QnIhvHM9O76Rs"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ Home route for testing
@app.route('/')
def home():
    return "✅ Bot is Live via Webhook!"

# ✅ Webhook route (must match token!)
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

# ✅ Bot command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 Hello gnex! Bot is working with webhook!")
