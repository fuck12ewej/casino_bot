import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import aiofiles


class CashoutManager:
    """Менеджер для управления запросами на вывод средств"""
    
    def __init__(self, cashout_file: str = "data/cashout.json"):
        self.cashout_file = cashout_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Создает файл если его нет"""
        os.makedirs(os.path.dirname(self.cashout_file), exist_ok=True)
        if not os.path.exists(self.cashout_file):
            with open(self.cashout_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    async def load_cashouts(self) -> Dict:
        """Загрузить запросы на вывод"""
        try:
            async with aiofiles.open(self.cashout_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except:
            return {}
    
    async def save_cashouts(self, data: Dict):
        """Сохранить запросы на вывод"""
        async with aiofiles.open(self.cashout_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def create_cashout(self, user_id: int, amount: float, username: str = None) -> str:
        """
        Создать запрос на вывод средств
        
        Returns:
            cashout_id: ID запроса на вывод
        """
        cashouts = await self.load_cashouts()
        
        cashout_id = f"cashout_{user_id}_{int(datetime.now().timestamp() * 1000)}"
        
        cashout_data = {
            "cashout_id": cashout_id,
            "user_id": user_id,
            "username": username,
            "amount": amount,
            "status": "pending",  # pending, processed, cancelled
            "created_at": datetime.now().isoformat(),
            "processed_at": None
        }
        
        cashouts[cashout_id] = cashout_data
        await self.save_cashouts(cashouts)
        
        return cashout_id
    
    async def get_user_cashouts(self, user_id: int) -> List[Dict]:
        """Получить все запросы на вывод пользователя"""
        cashouts = await self.load_cashouts()
        
        user_cashouts = [
            cashout for cashout in cashouts.values()
            if cashout.get("user_id") == user_id
        ]
        
        # Сортируем по дате (новые первыми)
        user_cashouts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return user_cashouts
    
    async def get_pending_cashouts(self) -> List[Dict]:
        """Получить все ожидающие запросы на вывод"""
        cashouts = await self.load_cashouts()
        
        pending = [
            cashout for cashout in cashouts.values()
            if cashout.get("status") == "pending"
        ]
        
        pending.sort(key=lambda x: x.get("created_at", ""))
        
        return pending
    
    async def update_cashout_status(self, cashout_id: str, status: str):
        """Обновить статус запроса на вывод"""
        cashouts = await self.load_cashouts()
        
        if cashout_id in cashouts:
            cashouts[cashout_id]["status"] = status
            if status == "processed":
                cashouts[cashout_id]["processed_at"] = datetime.now().isoformat()
            
            await self.save_cashouts(cashouts)
            return True
        
        return False

