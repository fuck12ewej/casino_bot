"""
Менеджер игровых комнат для мультиплеер игр
"""
import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import aiofiles

from multiplayer_games import DiceGame, CoinflipGame, MultiplayerGame


class RoomManager:
    """Управление игровыми комнатами"""
    
    def __init__(self, rooms_file: str = "data/rooms/active_rooms.json"):
        self.rooms_file = rooms_file
        self.active_rooms: Dict[str, MultiplayerGame] = {}
        self._ensure_file_exists()
        self.room_counter = 1000
    
    def _ensure_file_exists(self):
        """Создает файл если его нет"""
        os.makedirs(os.path.dirname(self.rooms_file), exist_ok=True)
        if not os.path.exists(self.rooms_file):
            with open(self.rooms_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def generate_room_id(self) -> str:
        """Генерирует уникальный ID комнаты"""
        self.room_counter += 1
        return f"ROOM{self.room_counter}"
    
    def create_room(self, creator_id: int, game_type: str, bet: float) -> MultiplayerGame:
        """
        Создать новую комнату
        
        Args:
            creator_id: ID создателя
            game_type: Тип игры ('dice' или 'coinflip')
            bet: Размер ставки
        """
        room_id = self.generate_room_id()
        
        if game_type == "dice":
            room = DiceGame(room_id, creator_id, bet)
        elif game_type == "coinflip":
            room = CoinflipGame(room_id, creator_id, bet)
        else:
            raise ValueError(f"Unknown game type: {game_type}")
        
        self.active_rooms[room_id] = room
        return room
    
    def get_room(self, room_id: str) -> Optional[MultiplayerGame]:
        """Получить комнату по ID"""
        return self.active_rooms.get(room_id)
    
    def join_room(self, room_id: str, opponent_id: int) -> bool:
        """
        Подключиться к комнате
        
        Returns:
            True если успешно подключился
        """
        room = self.get_room(room_id)
        if not room:
            return False
        
        # Проверяем, что игрок не пытается подключиться к своей же комнате
        if room.creator_id == opponent_id:
            return False
        
        return room.join(opponent_id)
    
    def get_waiting_rooms(self, game_type: Optional[str] = None) -> List[MultiplayerGame]:
        """
        Получить список комнат, ожидающих игроков
        
        Args:
            game_type: Фильтр по типу игры (опционально)
        """
        rooms = [
            room for room in self.active_rooms.values()
            if room.status == "waiting"
        ]
        
        if game_type:
            rooms = [r for r in rooms if r.game_type == game_type]
        
        return rooms
    
    def get_user_rooms(self, user_id: int) -> List[MultiplayerGame]:
        """Получить комнаты пользователя (где он создатель или оппонент)"""
        return [
            room for room in self.active_rooms.values()
            if room.creator_id == user_id or room.opponent_id == user_id
        ]
    
    def delete_room(self, room_id: str) -> bool:
        """Удалить комнату"""
        if room_id in self.active_rooms:
            del self.active_rooms[room_id]
            return True
        return False
    
    def cleanup_finished_rooms(self):
        """Очистка завершенных комнат"""
        finished = [
            room_id for room_id, room in self.active_rooms.items()
            if room.status == "finished"
        ]
        
        for room_id in finished:
            del self.active_rooms[room_id]
    
    async def save_rooms(self):
        """Сохранить активные комнаты в файл"""
        data = {
            room_id: room.to_dict()
            for room_id, room in self.active_rooms.items()
        }
        
        async with aiofiles.open(self.rooms_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def load_rooms(self):
        """Загрузить комнаты из файла"""
        try:
            async with aiofiles.open(self.rooms_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content) if content else {}
                
                # Восстанавливаем комнаты из сохраненных данных
                for room_id, room_data in data.items():
                    game_type = room_data.get("game_type")
                    
                    if game_type == "dice":
                        room = DiceGame(
                            room_data["room_id"],
                            room_data["creator_id"],
                            room_data["bet"]
                        )
                    elif game_type == "coinflip":
                        room = CoinflipGame(
                            room_data["room_id"],
                            room_data["creator_id"],
                            room_data["bet"]
                        )
                    else:
                        continue
                    
                    # Восстанавливаем состояние
                    room.opponent_id = room_data.get("opponent_id")
                    room.status = room_data.get("status", "waiting")
                    room.created_at = room_data.get("created_at")
                    
                    self.active_rooms[room_id] = room
        except Exception as e:
            print(f"Error loading rooms: {e}")

