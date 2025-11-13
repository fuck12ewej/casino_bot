"""
Мультиплеер игры 1 на 1
"""
import random
from typing import Dict, Tuple, Optional
from datetime import datetime


class MultiplayerGame:
    """Базовый класс для мультиплеер игр"""
    
    def __init__(self, room_id: str, creator_id: int, bet: float, game_type: str):
        self.room_id = room_id
        self.creator_id = creator_id
        self.opponent_id: Optional[int] = None
        self.bet = bet
        self.game_type = game_type
        self.created_at = datetime.now().isoformat()
        self.status = "waiting"  # waiting, playing, finished
        self.creator_result = None
        self.opponent_result = None
        self.winner_id = None
    
    def join(self, opponent_id: int) -> bool:
        """Подключение оппонента"""
        if self.status != "waiting":
            return False
        
        self.opponent_id = opponent_id
        self.status = "playing"
        return True
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        return {
            "room_id": self.room_id,
            "creator_id": self.creator_id,
            "opponent_id": self.opponent_id,
            "bet": self.bet,
            "game_type": self.game_type,
            "created_at": self.created_at,
            "status": self.status,
            "creator_result": self.creator_result,
            "opponent_result": self.opponent_result,
            "winner_id": self.winner_id
        }


class DiceGame(MultiplayerGame):
    """Игра в кубик 1v1 - у кого больше, тот выиграл"""
    
    def __init__(self, room_id: str, creator_id: int, bet: float):
        super().__init__(room_id, creator_id, bet, "dice")
    
    def play(self) -> Dict:
        """Играть в кубик"""
        if self.status != "playing":
            return {"error": "Game is not ready"}
        
        # Бросаем кубики для обоих игроков
        self.creator_result = random.randint(1, 6)
        self.opponent_result = random.randint(1, 6)
        
        # Определяем победителя
        if self.creator_result > self.opponent_result:
            self.winner_id = self.creator_id
        elif self.opponent_result > self.creator_result:
            self.winner_id = self.opponent_id
        else:
            self.winner_id = None  # Ничья
        
        self.status = "finished"
        
        return {
            "creator_result": self.creator_result,
            "opponent_result": self.opponent_result,
            "winner_id": self.winner_id,
            "is_draw": self.winner_id is None
        }


class CoinflipGame(MultiplayerGame):
    """Игра в монетку 1v1 - создатель выбирает сторону"""
    
    def __init__(self, room_id: str, creator_id: int, bet: float):
        super().__init__(room_id, creator_id, bet, "coinflip")
        self.creator_choice = None  # Выбор создателя (heads/tails)
    
    def set_creator_choice(self, choice: str):
        """Установить выбор создателя"""
        self.creator_choice = choice.lower()
    
    def get_opponent_choice(self) -> str:
        """Получить автоматический выбор оппонента (противоположная сторона)"""
        if self.creator_choice == "heads":
            return "tails"
        else:
            return "heads"
    
    def play(self) -> Dict:
        """Играть в монетку"""
        if self.status != "playing":
            return {"error": "Game is not ready"}
        
        if not self.creator_choice:
            return {"error": "Creator must make a choice"}
        
        # Оппонент автоматически получает противоположную сторону
        opponent_choice = self.get_opponent_choice()
        
        # Подбрасываем монетку
        result = random.choice(["heads", "tails"])
        
        self.creator_result = result
        self.opponent_result = result
        
        # Определяем победителя
        if self.creator_choice == result:
            self.winner_id = self.creator_id
        elif opponent_choice == result:
            self.winner_id = self.opponent_id
        else:
            # Это не должно случиться, но на всякий случай
            self.winner_id = None
        
        self.status = "finished"
        
        return {
            "result": result,
            "creator_choice": self.creator_choice,
            "opponent_choice": opponent_choice,
            "winner_id": self.winner_id,
            "is_draw": self.winner_id is None
        }
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        data = super().to_dict()
        data["creator_choice"] = self.creator_choice
        return data

