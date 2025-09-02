import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import cv2
from threading import Timer
import asyncio

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT
            )
        ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY,
                image TEXT,
                used INTEGER DEFAULT 0
            )
        ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
        ''')

            conn.commit()

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT INTO users VALUES (?, ?)', (user_id, user_name))
            conn.commit()

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('''INSERT INTO prizes (image) VALUES (?)''', data)
            conn.commit()

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor() 
            cur.execute("SELECT * FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
            if cur.fetchall():
                return 0
            else:
                conn.execute('''INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)''', (user_id, prize_id, win_time))
                conn.commit()
                return 1

  
    def mark_prize_used(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''UPDATE prizes SET used = 1 WHERE prize_id = ?''', (prize_id,))
            conn.commit()


    def get_users(self):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")
        return [x[0] for x in cur.fetchall()] 
        
    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute(f"SELECT image FROM prizes WHERE prize_id = {prize_id}")
        return cur.fetchall()[0][0]

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute("SELECT prize_id, image FROM prizes WHERE used = 0 ORDER BY RANDOM() LIMIT 1")
        return cur.fetchall()[0]

    def get_winners_count(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM winners WHERE prize_id = ?', (prize_id, ))
            return cur.fetchall()[0][0]

    def get_rating(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
            SELECT users.user_name, COUNT(winners.prize_id) as count_prize
            FROM winners
            INNER JOIN users on users.user_id = winners.user_id
            GROUP BY winners.user_id
            ORDER BY count_prize DESC
            LIMIT 10
            ''')
            return cur.fetchall()
        
    def get_user_prizes(self, user_id):
        """Получить все призы пользователя (полученные и неполученные)"""
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            # Полученные призы
            cur.execute(''' 
                SELECT p.prize_id, p.image, 1 as obtained 
                FROM winners w
                INNER JOIN prizes p ON w.prize_id = p.prize_id
                WHERE w.user_id = ?
            ''', (user_id, ))
            obtained_prizes = cur.fetchall()
            
            # Все призы
            cur.execute('SELECT prize_id, image FROM prizes')
            all_prizes = cur.fetchall()
            
            # Создаем список всех призов с отметкой о получении
            user_prizes = []
            for prize_id, image in all_prizes:
                obtained = any(p[0] == prize_id for p in obtained_prizes)
                user_prizes.append((prize_id, image, obtained))
            
            return user_prizes
        
    def add_bid(self, user_id, prize_id, amount):
        conn = sqlite3.connect(self.database)
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
            conn.execute('INSERT INTO bids (user_id, prize_id, amount, bid_time) VALUES (?, ?, ?, ?)',
                        (user_id, prize_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()

    def get_highest_bid(self, prize_id):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT MAX(amount) FROM bids WHERE prize_id = ?', (prize_id,))
        result = cur.fetchone()[0]
        return result if result else 0

    def get_highest_bidder(self, prize_id):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('''
            SELECT u.user_id, u.user_name, b.amount 
            FROM bids b
            JOIN users u ON b.user_id = u.user_id
            WHERE b.prize_id = ? 
            ORDER BY b.amount DESC 
            LIMIT 1
        ''', (prize_id,))
        return cur.fetchone()

    def get_user_balance(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS balances (
                    user_id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 1000.0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')
            conn.execute('INSERT OR IGNORE INTO balances (user_id) VALUES (?)', (user_id,))
            conn.commit()
            
            cur = conn.cursor()
            cur.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
            result = cur.fetchone()
            return result[0] if result else 1000.0

    def update_user_balance(self, user_id, amount):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE balances SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
            conn.commit()




def hide_img(img_name):
    image = cv2.imread(f'img/{img_name}')
    blurred_image = cv2.GaussianBlur(image, (15, 15), 0)
    pixelated_image = cv2.resize(blurred_image, (30, 30), interpolation=cv2.INTER_NEAREST)
    pixelated_image = cv2.resize(pixelated_image, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'hidden_img/{img_name}', pixelated_image)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)