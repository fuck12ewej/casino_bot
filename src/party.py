import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import aiofiles


class PartyManager:
    """Менеджер для групповых игр и турниров"""
    
    def __init__(self, party_file: str = "data/party/active_party.json"):
        self.party_file = party_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Создает файл если его нет"""
        os.makedirs(os.path.dirname(self.party_file), exist_ok=True)
        if not os.path.exists(self.party_file):
            with open(self.party_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    async def load_parties(self) -> Dict:
        """Загрузить активные пати"""
        async with aiofiles.open(self.party_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    
    async def save_parties(self, data: Dict):
        """Сохранить данные пати"""
        async with aiofiles.open(self.party_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def create_party(self, creator_id: int, party_name: str, 
                          game_type: str, entry_fee: float = 0) -> str:
        """
        Создать новую пати/турнир
        
        Returns:
            party_id: ID созданной пати
        """
        parties = await self.load_parties()
        
        party_id = f"party_{creator_id}_{datetime.now().timestamp()}"
        
        parties[party_id] = {
            "party_id": party_id,
            "name": party_name,
            "creator_id": creator_id,
            "game_type": game_type,
            "entry_fee": entry_fee,
            "participants": [creator_id],
            "status": "waiting",  # waiting, active, finished
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
            "prize_pool": entry_fee,
            "results": []
        }
        
        await self.save_parties(parties)
        return party_id
    
    async def join_party(self, party_id: str, user_id: int) -> bool:
        """Присоединиться к пати"""
        parties = await self.load_parties()
        
        if party_id not in parties:
            return False
        
        party = parties[party_id]
        
        if party["status"] != "waiting":
            return False
        
        if user_id not in party["participants"]:
            party["participants"].append(user_id)
            party["prize_pool"] += party["entry_fee"]
        
        await self.save_parties(parties)
        return True
    
    async def start_party(self, party_id: str) -> bool:
        """Начать пати"""
        parties = await self.load_parties()
        
        if party_id not in parties:
            return False
        
        party = parties[party_id]
        
        if party["status"] != "waiting":
            return False
        
        party["status"] = "active"
        party["started_at"] = datetime.now().isoformat()
        
        await self.save_parties(parties)
        return True
    
    async def add_result(self, party_id: str, user_id: int, score: float):
        """Добавить результат участника"""
        parties = await self.load_parties()
        
        if party_id not in parties:
            return
        
        party = parties[party_id]
        
        # Проверяем, есть ли уже результат этого пользователя
        existing_result = next(
            (r for r in party["results"] if r["user_id"] == user_id), 
            None
        )
        
        if existing_result:
            existing_result["score"] = score
        else:
            party["results"].append({
                "user_id": user_id,
                "score": score,
                "timestamp": datetime.now().isoformat()
            })
        
        await self.save_parties(parties)
    
    async def finish_party(self, party_id: str) -> Optional[List[Dict]]:
        """
        Завершить пати и вернуть результаты
        
        Returns:
            Отсортированный список результатов (от лучшего к худшему)
        """
        parties = await self.load_parties()
        
        if party_id not in parties:
            return None
        
        party = parties[party_id]
        
        if party["status"] != "active":
            return None
        
        party["status"] = "finished"
        party["finished_at"] = datetime.now().isoformat()
        
        # Сортируем результаты по очкам (от большего к меньшему)
        results = sorted(
            party["results"], 
            key=lambda x: x["score"], 
            reverse=True
        )
        
        party["results"] = results
        
        await self.save_parties(parties)
        return results
    
    async def get_party(self, party_id: str) -> Optional[Dict]:
        """Получить информацию о пати"""
        parties = await self.load_parties()
        return parties.get(party_id)
    
    async def get_active_parties(self) -> List[Dict]:
        """Получить список активных пати"""
        parties = await self.load_parties()
        return [
            p for p in parties.values() 
            if p["status"] in ["waiting", "active"]
        ]
    
    async def delete_party(self, party_id: str) -> bool:
        """Удалить пати"""
        parties = await self.load_parties()
        
        if party_id in parties:
            del parties[party_id]
            await self.save_parties(parties)
            return True
        
        return False
    
    async def calculate_prizes(self, party_id: str) -> Dict[int, float]:
        """
        Расчитать призы для участников
        
        Returns:
            Dict с user_id и суммой приза
        """
        party = await self.get_party(party_id)
        
        if not party or party["status"] != "finished":
            return {}
        
        prize_pool = party["prize_pool"]
        results = party["results"]
        
        if not results:
            return {}
        
        prizes = {}
        
        # Распределение призов (50% первому, 30% второму, 20% третьему)
        if len(results) >= 1:
            prizes[results[0]["user_id"]] = prize_pool * 0.5
        
        if len(results) >= 2:
            prizes[results[1]["user_id"]] = prize_pool * 0.3
        
        if len(results) >= 3:
            prizes[results[2]["user_id"]] = prize_pool * 0.2
        
        return prizes

