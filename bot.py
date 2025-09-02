from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *
from auction_manager import AuctionManager

bot = TeleBot(API_TOKEN)
manager = DatabaseManager(DATABASE)
auction_manager = AuctionManager(DATABASE, bot)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    prize_id = call.data
    user_id = call.message.chat.id

    img = manager.get_prize_img(prize_id)
    with open(f'img/{img}', 'rb') as photo:
        bot.send_photo(user_id, photo)


def send_message():
    prize_id, img = manager.get_random_prize()[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)
    for user in manager.get_users():
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(user, photo, reply_markup=gen_markup(id = prize_id))
        

def shedule_thread():
    schedule.every().minute.do(send_message) # Здесь ты можешь задать периодичность отправки картинок
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегестрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")
        
@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating() 
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)
    
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = call.data
    user_id = call.message.chat.id

    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            manager.mark_prize_used(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")

@bot.message_handler(commands=['start_auction'])
def start_auction(message):
    chat_id = message.chat.id
    result = auction_manager.start_auction(chat_id)
    
    if result:
        prize_id, prize_image = result
        # Отправляем скрытое изображение
        hidden_image = open(f'hidden_img/{prize_image}', 'rb')
        bot.send_photo(chat_id, hidden_image, 
                      caption=f"🎰 Аукцион начался!\n🎁 Приз №{prize_id}\n⏰ Время: 2 минуты\n💸 Ставки: /bid [сумма]")
    else:
        bot.send_message(chat_id, "❌ Нет доступных призов")

@bot.message_handler(commands=['bid'])
def place_bid(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    try:
        amount = float(message.text.split()[1])
        success, response = auction_manager.place_bid(chat_id, user_id, amount)
        
        if success:
            bot.reply_to(message, f"✅ {response}")
        else:
            bot.reply_to(message, f"❌ {response}")
            
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Используй: /bid [сумма]")

@bot.message_handler(commands=['auction_info'])
def auction_info(message):
    chat_id = message.chat.id
    info = auction_manager.get_auction_info(chat_id)
    
    if info:
        bot.send_message(
            chat_id,
            f"🎯 Текущий аукцион:\n"
            f"🎁 Приз: #{info['prize_id']}\n"
            f"💰 Текущая ставка: {info['current_bid']}\n"
            f"⏰ Осталось времени: {info['time_left']} сек."
        )
    else:
        bot.send_message(chat_id, "❌ Сейчас нет активных аукционов")

@bot.message_handler(commands=['balance'])
def check_balance(message):
    user_id = message.from_user.id
    balance = manager.get_user_balance(user_id)
    bot.reply_to(message, f"💰 Твой баланс: {balance}")


def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    
    # Создаем таблицы для новых функций
    conn = sqlite3.connect(DATABASE)
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bids (
                bid_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                prize_id INTEGER,
                amount REAL,
                bid_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS balances (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 1000.0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        conn.commit()
    
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)
  
