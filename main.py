from flask import Flask, request
import telebot
import os

# ✅ Your bot token
BOT_TOKEN = "8128064097:AAEZpZ-XV660gElE_cHAl2QnIhvHM9O76Rs"

# ✅ Telegram Bot & Flask App Init
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ Home route (for Render health check)
@app.route('/')
def home():
    return "🤖 Hosting Bot is Running!"

# ✅ Webhook Receiver
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ✅ /start command handler
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id, "👋 Hello gnex! Webhook working perfectly ✅")

# ✅ Run Flask + Set Webhook on startup
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # Remove previous webhook if any
    bot.remove_webhook()

    # Set webhook to your hosted URL
    bot.set_webhook(url=f"https://webhookhosting-1.onrender.com/{BOT_TOKEN}")

    # Run Flask app
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
