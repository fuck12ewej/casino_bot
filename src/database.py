import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import aiofiles


class Database:
    def __init__(self, db_path: str = "data/database/users.json"):
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Создает файл базы данных, если он не существует"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    async def load_data(self) -> Dict:
        """Асинхронная загрузка данных"""
        async with aiofiles.open(self.db_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    
    async def save_data(self, data: Dict):
        """Асинхронное сохранение данных"""
        async with aiofiles.open(self.db_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя"""
        data = await self.load_data()
        return data.get(str(user_id))
    
    async def create_user(self, user_id: int, username: str = None, starting_balance: float = 100.0):
        """Создать нового пользователя"""
        data = await self.load_data()
        user_id_str = str(user_id)
        
        if user_id_str in data:
            return data[user_id_str]
        
        data[user_id_str] = {
            "user_id": user_id,
            "username": username,
            "balance": starting_balance,
            "total_deposited": starting_balance,
            "total_wagered": 0.0,
            "total_won": 0.0,
            "total_lost": 0.0,
            "games_played": 0,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "game_history": []
        }
        
        await self.save_data(data)
        return data[user_id_str]
    
    async def update_balance(self, user_id: int, amount: float) -> float:
        """Обновить баланс пользователя"""
        data = await self.load_data()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            return 0.0
        
        data[user_id_str]["balance"] += amount
        data[user_id_str]["last_activity"] = datetime.now().isoformat()
        
        await self.save_data(data)
        return data[user_id_str]["balance"]
    
    async def get_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        user = await self.get_user(user_id)
        return user["balance"] if user else 0.0
    
    async def add_game_to_history(self, user_id: int, game_type: str, bet: float, 
                                  win_amount: float, result: str):
        """Добавить игру в историю"""
        data = await self.load_data()
        user_id_str = str(user_id)
        
        if user_id_str not in data:
            return
        
        game_record = {
            "game_type": game_type,
            "bet": bet,
            "win_amount": win_amount,
            "profit": win_amount - bet,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        # Добавляем в начало списка
        data[user_id_str]["game_history"].insert(0, game_record)
        
        # Оставляем только последние 50 игр
        data[user_id_str]["game_history"] = data[user_id_str]["game_history"][:50]
        
        # Обновляем статистику
        data[user_id_str]["games_played"] += 1
        data[user_id_str]["total_wagered"] += bet
        
        if win_amount > bet:
            data[user_id_str]["total_won"] += (win_amount - bet)
        else:
            data[user_id_str]["total_lost"] += (bet - win_amount)
        
        data[user_id_str]["last_activity"] = datetime.now().isoformat()
        
        await self.save_data(data)
    
    async def add_deposit(self, user_id: int, amount: float):
        """Добавить депозит"""
        data = await self.load_data()
        user_id_str = str(user_id)
        
        if user_id_str in data:
            data[user_id_str]["balance"] += amount
            data[user_id_str]["total_deposited"] += amount
            data[user_id_str]["last_activity"] = datetime.now().isoformat()
            await self.save_data(data)
    
    async def get_recent_games(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Получить последние игры"""
        user = await self.get_user(user_id)
        if not user or "game_history" not in user:
            return []
        
        return user["game_history"][:limit]
    
    async def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Получить статистику пользователя"""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        return {
            "balance": user["balance"],
            "total_deposited": user["total_deposited"],
            "total_wagered": user["total_wagered"],
            "total_won": user["total_won"],
            "total_lost": user["total_lost"],
            "games_played": user["games_played"],
            "profit": user["total_won"] - user["total_lost"]
        }

