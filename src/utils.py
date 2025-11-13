"""
Вспомогательные утилиты для бота казино
"""

from datetime import datetime
from typing import Optional


def format_currency(amount: float, currency: str = "USD") -> str:
    """Форматирование валюты"""
    symbols = {
        "USD": "$",
        "EUR": "€",
        "RUB": "₽",
        "GBP": "£"
    }
    symbol = symbols.get(currency, "$")
    return f"{symbol}{amount:.2f}"


def format_timestamp(timestamp: str) -> str:
    """Форматирование временной метки"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return timestamp


def calculate_win_rate(total_won: float, total_lost: float) -> float:
    """Расчет процента побед"""
    total = total_won + total_lost
    if total == 0:
        return 0.0
    return (total_won / total) * 100


def format_profit(profit: float) -> str:
    """Форматирование прибыли с цветом"""
    if profit > 0:
        return f"✅ +${profit:.2f}"
    elif profit < 0:
        return f"❌ -${abs(profit):.2f}"
    else:
        return f"➖ $0.00"


def validate_bet(bet: float, balance: float, min_bet: float, max_bet: float) -> tuple[bool, Optional[str]]:
    """
    Валидация ставки
    
    Returns:
        (is_valid, error_message)
    """
    if bet < min_bet:
        return False, f"❌ Минимальная ставка: ${min_bet:.2f}"
    
    if bet > max_bet:
        return False, f"❌ Максимальная ставка: ${max_bet:.2f}"
    
    if bet > balance:
        return False, f"❌ Недостаточно средств! Ваш баланс: ${balance:.2f}"
    
    return True, None


def get_rank_by_balance(balance: float) -> tuple[str, str]:
    """
    Получить ранг игрока по балансу
    
    Returns:
        (rank_name, emoji)
    """
    if balance >= 10000:
        return "Легенда", "👑"
    elif balance >= 5000:
        return "Магнат", "💎"
    elif balance >= 2000:
        return "Профи", "⭐"
    elif balance >= 1000:
        return "Игрок", "🎰"
    elif balance >= 500:
        return "Новичок+", "🎲"
    else:
        return "Новичок", "🍀"


def get_game_emoji(game_type: str) -> str:
    """Получить эмодзи для типа игры"""
    emojis = {
        "roulette": "🎰",
        "dice": "🎲",
        "slots": "🎰",
        "coinflip": "🪙",
        "crash": "📈",
        "blackjack": "🃏"
    }
    return emojis.get(game_type.lower(), "🎮")


def truncate_text(text: str, max_length: int = 50) -> str:
    """Обрезать текст до максимальной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def parse_amount(text: str) -> Optional[float]:
    """Безопасный парсинг суммы из текста"""
    try:
        # Убираем символы валют и пробелы
        cleaned = text.replace("$", "").replace("€", "").replace("₽", "").strip()
        amount = float(cleaned)
        return amount if amount >= 0 else None
    except ValueError:
        return None


def get_achievement_text(user_stats: dict) -> list[str]:
    """Получить список достижений пользователя"""
    achievements = []
    
    if user_stats.get("games_played", 0) >= 100:
        achievements.append("🏆 Ветеран - 100+ игр")
    
    if user_stats.get("total_won", 0) >= 10000:
        achievements.append("💰 Богач - $10,000+ выигрышей")
    
    if user_stats.get("balance", 0) >= 5000:
        achievements.append("💎 Магнат - баланс $5,000+")
    
    profit = user_stats.get("total_won", 0) - user_stats.get("total_lost", 0)
    if profit >= 1000:
        achievements.append("📈 Успешный - $1,000+ прибыли")
    
    if user_stats.get("games_played", 0) >= 10:
        win_rate = calculate_win_rate(
            user_stats.get("total_won", 0),
            user_stats.get("total_lost", 0)
        )
        if win_rate >= 60:
            achievements.append("🎯 Меткий - 60%+ побед")
    
    return achievements


def format_large_number(num: float) -> str:
    """Форматирование больших чисел (1000 -> 1K)"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return f"{num:.0f}"

