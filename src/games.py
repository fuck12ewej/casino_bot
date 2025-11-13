import random
from typing import Dict, Tuple
from enum import Enum


class GameResult:
    def __init__(self, won: bool, bet: float, win_amount: float, result_text: str, 
                 emoji: str = ""):
        self.won = won
        self.bet = bet
        self.win_amount = win_amount
        self.profit = win_amount - bet
        self.result_text = result_text
        self.emoji = emoji


class RouletteColor(Enum):
    RED = "red"
    BLACK = "black"
    GREEN = "green"


class CasinoGames:
    """Класс для всех игр казино"""
    
    # Красные числа на рулетке
    RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    
    # Черные числа на рулетке
    BLACK_NUMBERS = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
    
    @staticmethod
    def play_roulette(bet: float, bet_type: str, bet_value: any = None) -> GameResult:
        """
        Игра в рулетку
        
        Args:
            bet: Размер ставки
            bet_type: Тип ставки ('number', 'color', 'even_odd', 'high_low')
            bet_value: Значение ставки (число, цвет и т.д.)
        """
        # Генерируем выпавшее число (0-36)
        result_number = random.randint(0, 36)
        
        # Определяем цвет
        if result_number == 0:
            result_color = RouletteColor.GREEN
        elif result_number in CasinoGames.RED_NUMBERS:
            result_color = RouletteColor.RED
        else:
            result_color = RouletteColor.BLACK
        
        won = False
        multiplier = 0
        
        # Проверяем ставку на конкретное число
        if bet_type == "number":
            if result_number == bet_value:
                won = True
                multiplier = 35
        
        # Проверяем ставку на цвет
        elif bet_type == "color":
            if bet_value.lower() in ["red", "красный", "r"]:
                if result_color == RouletteColor.RED:
                    won = True
                    multiplier = 2
            elif bet_value.lower() in ["black", "черный", "b"]:
                if result_color == RouletteColor.BLACK:
                    won = True
                    multiplier = 2
            elif bet_value.lower() in ["green", "зеленый", "g"]:
                if result_color == RouletteColor.GREEN:
                    won = True
                    multiplier = 35
        
        # Проверяем ставку на четное/нечетное
        elif bet_type == "even_odd":
            if result_number != 0:
                if bet_value.lower() in ["even", "четное", "e"] and result_number % 2 == 0:
                    won = True
                    multiplier = 2
                elif bet_value.lower() in ["odd", "нечетное", "o"] and result_number % 2 == 1:
                    won = True
                    multiplier = 2
        
        # Проверяем ставку на высокие/низкие
        elif bet_type == "high_low":
            if result_number != 0:
                if bet_value.lower() in ["high", "высокие", "h"] and result_number > 18:
                    won = True
                    multiplier = 2
                elif bet_value.lower() in ["low", "низкие", "l"] and result_number <= 18:
                    won = True
                    multiplier = 2
        
        win_amount = bet * multiplier if won else 0
        
        # Формируем текст результата
        color_emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}
        result_text = f"Выпало: {result_number} {color_emoji.get(result_color.value, '')}"
        
        if won:
            result_text += f"\n✅ Вы выиграли ${win_amount:.2f}!"
        else:
            result_text += f"\n❌ Вы проиграли ${bet:.2f}"
        
        return GameResult(won, bet, win_amount, result_text, "🎰")
    
    @staticmethod
    def play_dice(bet: float, guess: int) -> GameResult:
        """
        Игра в кубик
        
        Args:
            bet: Размер ставки
            guess: Предполагаемое число (1-6)
        """
        result = random.randint(1, 6)
        won = result == guess
        multiplier = 6 if won else 0
        win_amount = bet * multiplier if won else 0
        
        dice_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
        result_text = f"Выпало: {dice_emoji[result-1]} ({result})\n"
        result_text += f"Ваш выбор: {dice_emoji[guess-1]} ({guess})\n"
        
        if won:
            result_text += f"✅ Вы выиграли ${win_amount:.2f}!"
        else:
            result_text += f"❌ Вы проиграли ${bet:.2f}"
        
        return GameResult(won, bet, win_amount, result_text, "🎲")
    
    @staticmethod
    def play_slots(bet: float) -> GameResult:
        """
        Игра в слоты
        
        Args:
            bet: Размер ставки
        """
        symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔔", "⭐"]
        weights = [25, 20, 20, 15, 10, 5, 3, 2]  # Вероятности
        
        # Крутим 3 барабана
        reel1 = random.choices(symbols, weights=weights)[0]
        reel2 = random.choices(symbols, weights=weights)[0]
        reel3 = random.choices(symbols, weights=weights)[0]
        
        result_text = f"{reel1} {reel2} {reel3}\n"
        
        won = False
        multiplier = 0
        
        # Все три одинаковые
        if reel1 == reel2 == reel3:
            won = True
            # Множители в зависимости от символа
            multipliers = {
                "🍒": 3, "🍋": 4, "🍊": 5, "🍇": 6,
                "💎": 10, "7️⃣": 20, "🔔": 15, "⭐": 25
            }
            multiplier = multipliers.get(reel1, 5)
        # Две одинаковые
        elif reel1 == reel2 or reel2 == reel3 or reel1 == reel3:
            won = True
            multiplier = 1.5
        
        win_amount = bet * multiplier if won else 0
        
        if won:
            result_text += f"✅ Вы выиграли ${win_amount:.2f}! (x{multiplier})"
        else:
            result_text += f"❌ Вы проиграли ${bet:.2f}"
        
        return GameResult(won, bet, win_amount, result_text, "🎰")
    
    @staticmethod
    def play_coinflip(bet: float, choice: str) -> GameResult:
        """
        Игра в подбрасывание монеты
        
        Args:
            bet: Размер ставки
            choice: Выбор игрока ('heads'/'орел' или 'tails'/'решка')
        """
        result = random.choice(["heads", "tails"])
        
        # Нормализуем выбор игрока
        choice_normalized = choice.lower()
        if choice_normalized in ["орел", "heads", "h", "о"]:
            choice_normalized = "heads"
        else:
            choice_normalized = "tails"
        
        won = result == choice_normalized
        multiplier = 2 if won else 0
        win_amount = bet * multiplier if won else 0
        
        emoji_map = {"heads": "🦅 Орел", "tails": "🪙 Решка"}
        result_text = f"Выпало: {emoji_map[result]}\n"
        result_text += f"Ваш выбор: {emoji_map[choice_normalized]}\n"
        
        if won:
            result_text += f"✅ Вы выиграли ${win_amount:.2f}!"
        else:
            result_text += f"❌ Вы проиграли ${bet:.2f}"
        
        return GameResult(won, bet, win_amount, result_text, "🪙")
    
    @staticmethod
    def play_crash(bet: float, target_multiplier: float) -> GameResult:
        """
        Игра Crash - множитель растет и может "упасть"
        
        Args:
            bet: Размер ставки
            target_multiplier: Целевой множитель для вывода
        """
        # Генерируем случайную точку краша
        # Используем экспоненциальное распределение для реалистичности
        crash_point = 1.0 + random.expovariate(0.5)
        crash_point = round(crash_point, 2)
        
        won = target_multiplier <= crash_point
        
        if won:
            win_amount = bet * target_multiplier
            result_text = f"💥 Краш на x{crash_point:.2f}\n"
            result_text += f"✅ Вы вывели на x{target_multiplier:.2f}!\n"
            result_text += f"Выигрыш: ${win_amount:.2f}"
        else:
            win_amount = 0
            result_text = f"💥 Краш на x{crash_point:.2f}\n"
            result_text += f"❌ Вы не успели вывести x{target_multiplier:.2f}\n"
            result_text += f"Потеря: ${bet:.2f}"
        
        return GameResult(won, bet, win_amount, result_text, "📈")
    
    @staticmethod
    def play_blackjack_simple(bet: float) -> GameResult:
        """
        Упрощенная версия блэкджека (автоматическая игра)
        
        Args:
            bet: Размер ставки
        """
        def card_value(card):
            if card in ['J', 'Q', 'K']:
                return 10
            elif card == 'A':
                return 11
            else:
                return int(card)
        
        def calculate_hand(hand):
            value = sum(card_value(card) for card in hand)
            # Обработка тузов
            aces = hand.count('A')
            while value > 21 and aces:
                value -= 10
                aces -= 1
            return value
        
        # Колода
        deck = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4
        random.shuffle(deck)
        
        # Раздаем карты
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        
        # Игрок берет карты до 17
        while calculate_hand(player_hand) < 17:
            player_hand.append(deck.pop())
        
        # Дилер берет карты до 17
        while calculate_hand(dealer_hand) < 17:
            dealer_hand.append(deck.pop())
        
        player_value = calculate_hand(player_hand)
        dealer_value = calculate_hand(dealer_hand)
        
        result_text = f"Ваши карты: {' '.join(player_hand)} = {player_value}\n"
        result_text += f"Карты дилера: {' '.join(dealer_hand)} = {dealer_value}\n"
        
        # Определяем победителя
        if player_value > 21:
            won = False
            win_amount = 0
            result_text += "❌ Перебор! Вы проиграли"
        elif dealer_value > 21:
            won = True
            win_amount = bet * 2
            result_text += "✅ У дилера перебор! Вы выиграли"
        elif player_value > dealer_value:
            won = True
            win_amount = bet * 2
            result_text += "✅ Вы выиграли!"
        elif player_value < dealer_value:
            won = False
            win_amount = 0
            result_text += "❌ Дилер выиграл"
        else:
            won = True
            win_amount = bet  # Возврат ставки
            result_text += "🤝 Ничья! Ставка возвращена"
        
        return GameResult(won, bet, win_amount, result_text, "🃏")

