import telebot
import requests
import os
import re
import random
import time
from flask import Flask, request
from googlesearch import search

# ==========================================
# ТОКЕН БОТА
# ==========================================
TOKEN = '8637534012:AAHzjCKTr1ZKM7ZKDUd8D0_--gMZoWQziSE'

# ==========================================
# КЛЮЧ OPENROUTER (из Environment Variables)
# ==========================================
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')

if not OPENROUTER_KEY:
    print("❌ ОШИБКА: Переменная окружения OPENROUTER_KEY не задана!")
    exit(1)

ADMIN_ID = 8577385618
MODEL = "openai/gpt-oss-120b:free"

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
    if len(history) > 50:
        history.pop(0)

def clear_history(user_id):
    if user_id in user_history:
        user_history[user_id] = []

def clean_response(text):
    if not text:
        return text
    lines = text.split('\n')
    cleaned = [l for l in lines if 'User Safety' not in l and 'safety:' not in l.lower()]
    return '\n'.join(cleaned).strip()

# ==========================================
# OPENROUTER
# ==========================================
def ask_ai(user_id, prompt):
    history = get_history(user_id)
    
    messages = [
        {"role": "system", "content": "Ты — Смайл, дружелюбный, вежливый и умный ИИ-помощник. Отвечай вежливо, грамотно, с умеренными эмодзи. Мысль всегда заканчивай."}
    ]
    
    for msg in history[-50:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    
    messages.append({"role": "user", "content": prompt})
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            raw = response.json()["choices"][0]["message"]["content"]
            return clean_response(raw)
        else:
            return f"❌ Ошибка OpenRouter: {response.status_code}\n\n{response.text[:300]}"
    except Exception as e:
        return f"❌ Исключение: {str(e)[:300]}"

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
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Придумай короткую, смешную шутку на русском языке. Отвечай только шуткой, без лишнего текста."}],
        "max_tokens": 200,
        "temperature": 1.0
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            raw = response.json()["choices"][0]["message"]["content"]
            return clean_response(raw)
        return f"❌ Ошибка шутки: {response.status_code}"
    except Exception as e:
        return f"❌ Исключение: {str(e)[:200]}"

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
    response = ask_ai(user_id, text)
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
    return "🤖 Бот Смайл работает!"

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