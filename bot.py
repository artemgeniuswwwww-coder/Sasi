import telebot
import requests
import os
import re
import random
import time
from flask import Flask, request
from googlesearch import search

# ==========================================
# ТВОИ ДАННЫЕ
# ==========================================
TOKEN = '8637534012:AAHzjCKTr1ZKM7ZKDUd8D0_--gMZoWQziSE'
MISTRAL_KEY = 'mstrl_xIzHsNM6LPLGr2forXbgG3pRgQejABgG_0SJGbx'
ADMIN_ID = 8577385618

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

maintenance_mode = False

def is_admin(user_id):
    return user_id == ADMIN_ID

@bot.message_handler(commands=['maintenance'])
def toggle_maintenance(message):
    global maintenance_mode
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "📝 Использование: /maintenance on / off")
        return
    if args[1].lower() == 'on':
        maintenance_mode = True
        bot.reply_to(message, "🔧 Режим техобслуживания ВКЛЮЧЁН")
    elif args[1].lower() == 'off':
        maintenance_mode = False
        bot.reply_to(message, "✅ Режим техобслуживания ВЫКЛЮЧЕН")

user_history = {}

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = []
    return user_history[user_id]

def add_to_history(user_id, role, text):
    history = get_history(user_id)
    history.append({"role": role, "content": text})
    if len(history) > 30:
        history.pop(0)

def clear_history(user_id):
    if user_id in user_history:
        user_history[user_id] = []

def get_full_context(user_id):
    history = get_history(user_id)
    context = ""
    for msg in history:
        if msg["role"] == "user":
            context += f"Пользователь: {msg['content']}\n"
        else:
            context += f"Смайл: {msg['content']}\n"
    return context

# ==========================================
# MISTRAL
# ==========================================
def ask_mistral(user_id, prompt):
    context = get_full_context(user_id)
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_KEY}",
        "Content-Type": "application/json"
    }
    full_prompt = f"""Ты — Смайл, дружелюбный, вежливый и умный ИИ-помощник.

Правила:
1. Отвечай вежливо, дружелюбно и по делу.
2. Пиши грамотно, без сленга.
3. Добавляй эмодзи 😊, 👋, 👍, 🌟, 💡 — умеренно.
4. Если не знаешь — скажи честно.
5. Отвечай настолько подробно, насколько нужно. Мысль всегда должна быть закончена.

История диалога:
{context}

Вопрос пользователя: {prompt}

Твой ответ:"""
    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": full_prompt}],
        "max_tokens": 1500,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"Mistral статус: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Ошибка Mistral: {e}")
        return None

# ==========================================
# КАРТИНКИ
# ==========================================
def generate_image(prompt):
    clean_prompt = re.sub(r'^(нарисуй|сгенерируй|изобрази|покажи)\s+', '', prompt, flags=re.IGNORECASE)
    clean_prompt = clean_prompt.strip()
    if not clean_prompt:
        clean_prompt = "красивый пейзаж"
    styles = ["photorealistic, 8k, highly detailed", "cinematic lighting, sharp focus"]
    style = random.choice(styles)
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{clean_prompt.replace(' ', '%20')}, {style}?width=1024&height=1024&seed={seed}"
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            with open('image.jpg', 'wb') as f:
                f.write(response.content)
            return 'image.jpg', clean_prompt
        return None, None
    except:
        return None, None

# ==========================================
# ПОИСК
# ==========================================
def search_google(query):
    try:
        results = []
        for url in search(query, num_results=5):
            results.append(f"🔗 {url}")
        return "\n".join(results) if results else "❌ Ничего не найдено"
    except Exception as e:
        return f"😅 Ошибка поиска: {e}"

# ==========================================
# ШУТКИ
# ==========================================
def generate_joke():
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": "Придумай короткую, смешную шутку на русском языке. Отвечай только шуткой, без лишнего текста."}],
        "max_tokens": 200,
        "temperature": 1.0
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return "Шутка не придумалась 😅"
    except:
        return "Ошибка при генерации шутки"

# ==========================================
# ДЛИННЫЕ СООБЩЕНИЯ
# ==========================================
def send_long_message(chat_id, text):
    if len(text) <= 4096:
        bot.send_message(chat_id, text, parse_mode='Markdown')
    else:
        for i in range(0, len(text), 4096):
            bot.send_message(chat_id, text[i:i+4096], parse_mode='Markdown')

# ==========================================
# КОМАНДЫ
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "пользователь"
    clear_history(user_id)
    bot.reply_to(
        message,
        f"👋 Здравствуйте, **{user_name}**! Я Смайл 😊\n\n"
        "🎨 **Нарисуй** [описание] — картинка\n"
        "🔍 **Найди** [запрос] — поиск в Google\n"
        "💬 **Просто напишите** вопрос — я постараюсь помочь\n"
        "😂 **/joke** — шутка\n"
        "🔄 **/newchat** — новый диалог\n"
        "🧹 **/clear** — очистить историю",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['joke'])
def joke_cmd(message):
    status = bot.reply_to(message, "😂 Придумываю шутку...")
    joke = generate_joke()
    bot.edit_message_text(f"😂 {joke}", message.chat.id, status.id)

@bot.message_handler(commands=['newchat'])
def new_chat(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "пользователь"
    clear_history(user_id)
    bot.reply_to(message, f"🔄 **{user_name}**, начал новый диалог! История очищена. 😊")

@bot.message_handler(commands=['clear'])
def clear_chat(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "пользователь"
    clear_history(user_id)
    bot.reply_to(message, f"🧹 **{user_name}**, история диалога очищена! 😊")

# ==========================================
# ОСНОВНАЯ ОБРАБОТКА
# ==========================================
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text
    text_lower = text.lower()
    user_name = message.from_user.first_name or "пользователь"

    if maintenance_mode and not is_admin(user_id):
        bot.reply_to(message, "🔧 Ведутся технические работы. Ведутся одним человеком, так что ожидайте.")
        return

    # === КАРТИНКА ===
    draw_keywords = ['нарисуй', 'сгенерируй', 'изобрази', 'покажи']
    is_draw = any(text_lower.startswith(kw) for kw in draw_keywords)
    
    if is_draw:
        prompt = text
        for kw in draw_keywords:
            prompt = re.sub(r'^' + kw + r'\s+', '', prompt, flags=re.IGNORECASE)
        prompt = prompt.strip()
        if not prompt:
            bot.reply_to(message, f"📝 **{user_name}**, что нарисовать?", parse_mode='Markdown')
            return
        add_to_history(user_id, "user", f"Попросил нарисовать: {prompt}")
        status = bot.reply_to(message, f"🎨 Рисую...")
        image_path, clean_prompt = generate_image(prompt)
        if image_path:
            with open(image_path, 'rb') as f:
                bot.send_photo(message.chat.id, f, caption=f"🎨 *{clean_prompt.capitalize()}* готово!")
            os.remove(image_path)
            add_to_history(user_id, "assistant", f"Отправил картинку {clean_prompt}")
            bot.delete_message(message.chat.id, status.id)
        else:
            bot.edit_message_text("😅 Не удалось создать картинку.", message.chat.id, status.id)
        return

    # === ПОИСК ===
    if text_lower.startswith('найди') or text_lower.startswith('поищи'):
        query = text
        for word in ['найди', 'поищи', 'найди мне', 'поищи мне']:
            query = query.replace(word, '')
        query = query.strip()
        if not query:
            bot.reply_to(message, f"📝 **{user_name}**, что найти?", parse_mode='Markdown')
            return
        status = bot.reply_to(message, f"🔍 Ищу в Google...")
        search_results = search_google(query)
        add_to_history(user_id, "user", f"Поиск: {query}")
        add_to_history(user_id, "assistant", search_results)
        bot.delete_message(message.chat.id, status.id)
        send_long_message(message.chat.id, search_results)
        return

    # === ОБЫЧНЫЙ ОТВЕТ ===
    add_to_history(user_id, "user", text)
    status = bot.reply_to(message, f"🤔 Думаю...")
    response = ask_mistral(user_id, text)
    if response is None:
        response = "🔧 Ведутся технические работы. Ведутся одним человеком, так что ожидайте."
    add_to_history(user_id, "assistant", response)
    bot.delete_message(message.chat.id, status.id)
    send_long_message(message.chat.id, response)

# ==========================================
# WEBHOOK
# ==========================================
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        return f"Error: {e}", 400

@app.route('/')
def index():
    return "🤖 Бот Смайл работает на Mistral!"

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == '__main__':
    bot.remove_webhook()
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/{TOKEN}"
    bot.set_webhook(url=webhook_url)
    print(f"✅ Вебхук установлен: {webhook_url}")
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)