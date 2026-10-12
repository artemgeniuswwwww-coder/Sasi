import telebot
import requests
import os
import re
import random
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from googlesearch import search

# ==========================================
# ДАННЫЕ
# ==========================================
TOKEN = '8637534012:AAHzjCKTr1ZKM7ZKDUd8D0_--gMZoWQziSE'
LLM7_BASE_URL = "https://api.llm7.io/v1"
LLM7_API_KEY = "unused"
ADMIN_ID = 8577385618
MODEL = "fast"

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

# ==========================================
# ИСТОРИЯ (200 хранится, 40 отправляется ИИ)
# ==========================================
user_history = {}

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = []
    return user_history[user_id]

def add_to_history(user_id, role, text):
    history = get_history(user_id)
    history.append({"role": role, "content": text})
    if len(history) > 200:
        history.pop(0)

def clear_history(user_id):
    if user_id in user_history:
        user_history[user_id] = []

# ==========================================
# ЧИСТКА ОТВЕТА
# ==========================================
def clean_response(text, user_prompt=""):
    if not text:
        return text
    
    lines = text.split('\n')
    cleaned = [l for l in lines if 'User Safety' not in l and 'safety:' not in l.lower()]
    text = '\n'.join(cleaned).strip()
    
    if user_prompt:
        prompt_clean = user_prompt.strip()
        if text.endswith(prompt_clean):
            text = text[:-len(prompt_clean)].strip()
        lines = text.split('\n')
        if len(lines) > 1 and lines[-1].strip().lower() == prompt_clean.lower():
            text = '\n'.join(lines[:-1]).strip()
    
    return text.strip()

# ==========================================
# LLM7
# ==========================================
def ask_llm7(user_id, prompt):
    history = get_history(user_id)
    
    messages = [
        {"role": "system", "content": "Ты — Смайл, дружелюбный, вежливый и умный ИИ-помощник. Отвечай вежливо, грамотно, с умеренными эмодзи. Мысль всегда заканчивай. НЕ повторяй вопрос пользователя в конце ответа."}
    ]
    
    # Отправляем ИИ последние 40 сообщений
    for msg in history[-40:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    
    messages.append({"role": "user", "content": prompt})
    
    url = f"{LLM7_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM7_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1200,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            raw = response.json()["choices"][0]["message"]["content"]
            return clean_response(raw, prompt)
        else:
            return f"❌ Ошибка LLM7: {response.status_code}\n\n{response.text[:300]}"
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
    user_name = message.from_user.first_name or "друг"
    clear_history(user_id)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🎨 Нарисуй"),
        KeyboardButton("🔍 Найди"),
        KeyboardButton("🧹 Очистить"),
        KeyboardButton("🔄 Новый диалог"),
        KeyboardButton("ℹ️ Помощь")
    )
    
    greeting = f"""👋 **Привет, {user_name}!**

Я — **Смайл** 😊, твой личный ИИ-помощник. Умею многое:

🎨 **Рисовать** — просто скажи «Нарисуй закат в горах»
🔍 **Искать в Google** — «Найди новости про космос»
💬 **Отвечать на любые вопросы** — от науки до анекдотов
📝 **Помнить наш разговор** — контекст сохраняется

⚡ **Фишки:**
• Могу отвечать подробно или коротко — как попросишь
• Помню до 100 пар «вопрос-ответ»
• Работаю 24/7

💡 **Попробуй прямо сейчас:**
*Привет, как дела?* или *Нарисуй дракона*

⬇️ **Кнопки внизу — для быстрого доступа**"""
    
    bot.reply_to(message, greeting, parse_mode='Markdown', reply_markup=markup)

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

    # === ОБРАБОТКА КНОПОК ===
    if text == "🎨 Нарисуй":
        bot.reply_to(message, "🎨 Напиши: **Нарисуй [что]**\nНапример: *Нарисуй кота в космосе*", parse_mode='Markdown')
        return
    
    if text == "🔍 Найди":
        bot.reply_to(message, "🔍 Напиши: **Найди [запрос]**\nНапример: *Найди новости про ИИ*", parse_mode='Markdown')
        return
    
    if text == "🧹 Очистить":
        clear_history(user_id)
        bot.reply_to(message, "🧹 История диалога очищена! 😊")
        return
    
    if text == "🔄 Новый диалог":
        clear_history(user_id)
        bot.reply_to(message, "🔄 Начал новый диалог! История очищена. 😊")
        return
    
    if text == "ℹ️ Помощь":
        bot.reply_to(
            message,
            "📖 **Команды:**\n\n"
            "🎨 **Нарисуй** [описание] — картинка\n"
            "🔍 **Найди** [запрос] — поиск в Google\n"
            "💬 Любой текст — ответ ИИ\n\n"
            "🧹 Очистить — сброс истории\n"
            "🔄 Новый диалог — начать заново",
            parse_mode='Markdown'
        )
        return

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
    response = ask_llm7(user_id, text)
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
    return "🤖 Бот Смайл работает на LLM7!"

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