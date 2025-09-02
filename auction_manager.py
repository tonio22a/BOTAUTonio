import sqlite3
from datetime import datetime, timedelta
from threading import Timer
import asyncio
from logic import DatabaseManager

class AuctionManager:
    def __init__(self, database, bot):
        self.database = database
        self.bot = bot
        self.manager = DatabaseManager(database)
        self.active_auctions = {}
        
    def start_auction(self, chat_id, duration=120):
        prize = self.manager.get_random_prize()
        if not prize:
            return None
            
        prize_id, prize_image = prize
        
        auction = {
            'prize_id': prize_id,
            'prize_image': prize_image,
            'end_time': datetime.now() + timedelta(seconds=duration),
            'is_active': True,
            'timer': None
        }
        
        self.active_auctions[chat_id] = auction
        self._start_timer(chat_id, duration)
        return prize_id, prize_image
    
    def _start_timer(self, chat_id, duration):
        def end_auction():
            self._end_auction(chat_id)
            
        timer = Timer(duration, end_auction)
        timer.start()
        self.active_auctions[chat_id]['timer'] = timer
    
    def _end_auction(self, chat_id):
        if chat_id not in self.active_auctions:
            return
            
        auction = self.active_auctions[chat_id]
        auction['is_active'] = False
        
        winner = self.manager.get_highest_bidder(auction['prize_id'])
        
        if winner:
            user_id, user_name, winning_bid = winner
            self.manager.add_winner(user_id, auction['prize_id'])
            self.manager.mark_prize_used(auction['prize_id'])
            
            asyncio.run(self._send_winner_message(chat_id, user_name, winning_bid, auction['prize_id']))
        else:
            asyncio.run(self.bot.send_message(chat_id, "❌ На этот аукцион не было ставок. Приз возвращается в пул."))
    
    async def _send_winner_message(self, chat_id, user_name, winning_bid, prize_id):
        try:
            await self.bot.send_message(
                chat_id, 
                f"🎉 Аукцион завершен!\n"
                f"🏆 Победитель: @{user_name}\n"
                f"💰 Выигрышная ставка: {winning_bid}\n"
                f"🎁 Приз №{prize_id} отправлен победителю!"
            )
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")
    
    def place_bid(self, chat_id, user_id, amount):
        if chat_id not in self.active_auctions or not self.active_auctions[chat_id]['is_active']:
            return False, "Аукцион не активен"
        
        balance = self.manager.get_user_balance(user_id)
        if balance < amount:
            return False, "Недостаточно средств"
        
        current_bid = self.manager.get_highest_bid(self.active_auctions[chat_id]['prize_id'])
        if amount <= current_bid:
            return False, f"Ставка должна быть выше текущей ({current_bid})"
        
        self.manager.add_bid(user_id, self.active_auctions[chat_id]['prize_id'], amount)
        return True, "Ставка принята"
    
    def get_auction_info(self, chat_id):
        if chat_id not in self.active_auctions:
            return None
        
        auction = self.active_auctions[chat_id]
        current_bid = self.manager.get_highest_bid(auction['prize_id'])
        time_left = (auction['end_time'] - datetime.now()).seconds
        
        return {
            'prize_id': auction['prize_id'],
            'current_bid': current_bid,
            'time_left': time_left,
            'is_active': auction['is_active']
        }