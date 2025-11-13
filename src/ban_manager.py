import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import aiofiles


class BanManager:
    """Менеджер для управления банами пользователей"""
    
    def __init__(self, bans_file: str = "data/bans.json"):
        self.bans_file = bans_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Создает файл если его нет"""
        os.makedirs(os.path.dirname(self.bans_file), exist_ok=True)
        if not os.path.exists(self.bans_file):
            with open(self.bans_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    async def load_bans(self) -> Dict:
        """Загрузить список банов"""
        async with aiofiles.open(self.bans_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    
    async def save_bans(self, data: Dict):
        """Сохранить список банов"""
        async with aiofiles.open(self.bans_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def ban_user(self, user_id: int, reason: str = "", admin_id: int = None) -> bool:
        """
        Забанить пользователя
        
        Args:
            user_id: ID пользователя для бана
            reason: Причина бана
            admin_id: ID администратора
            
        Returns:
            True если успешно
        """
        bans = await self.load_bans()
        
        bans[str(user_id)] = {
            "user_id": user_id,
            "reason": reason,
            "banned_by": admin_id,
            "banned_at": datetime.now().isoformat(),
            "status": "banned"
        }
        
        await self.save_bans(bans)
        return True
    
    async def unban_user(self, user_id: int) -> bool:
        """Разбанить пользователя"""
        bans = await self.load_bans()
        
        user_id_str = str(user_id)
        if user_id_str in bans:
            del bans[user_id_str]
            await self.save_bans(bans)
            return True
        
        return False
    
    async def is_banned(self, user_id: int) -> bool:
        """Проверить, забанен ли пользователь"""
        bans = await self.load_bans()
        return str(user_id) in bans
    
    async def get_ban_info(self, user_id: int) -> Optional[Dict]:
        """Получить информацию о бане"""
        bans = await self.load_bans()
        return bans.get(str(user_id))
    
    async def get_all_bans(self) -> List[Dict]:
        """Получить все баны"""
        bans = await self.load_bans()
        return list(bans.values())

