import asyncio
import logging
import configparser
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import Database
from crypto_payment import CryptoPayment
from room_manager import RoomManager
from multiplayer_games import DiceGame, CoinflipGame
from cashout_manager import CashoutManager
from ban_manager import BanManager


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
config = configparser.ConfigParser()
config.read('config.cfg')

BOT_TOKEN = config.get('TELEGRAM', 'BOT_TOKEN', fallback='YOUR_BOT_TOKEN')
CRYPTO_MODE = config.get('CRYPTOBOT', 'MODE', fallback='test').lower()
CRYPTO_API_TOKEN = config.get('CRYPTOBOT', 'API_TOKEN', fallback='')
TEST_CRYPTO_TOKEN = config.get('CRYPTOBOT', 'TEST_API_TOKEN', fallback='')
STARTING_BALANCE = config.getfloat('SETTINGS', 'STARTING_BALANCE', fallback=100.0)
MIN_BET = config.getfloat('SETTINGS', 'MIN_BET', fallback=1.0)
MAX_BET = config.getfloat('SETTINGS', 'MAX_BET', fallback=1000.0)
HOUSE_FEE = config.getfloat('SETTINGS', 'HOUSE_FEE', fallback=5.0)  # Комиссия казино (%)

# Загрузка администраторов
ADMIN_IDS_STR = config.get('ADMIN', 'ADMIN_IDS', fallback='')
ADMIN_IDS = [int(uid.strip()) for uid in ADMIN_IDS_STR.split(',') if uid.strip()] if ADMIN_IDS_STR else []

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()
room_manager = RoomManager()
cashout_manager = CashoutManager()
ban_manager = BanManager()

# Выбор режима оплаты на основе MODE в конфиге
is_testnet = (CRYPTO_MODE != 'real')

if CRYPTO_MODE == 'real':
    if CRYPTO_API_TOKEN and CRYPTO_API_TOKEN != 'YOUR_CRYPTOBOT_TOKEN_HERE':
        crypto = CryptoPayment(CRYPTO_API_TOKEN, testnet=False)
        logger.info("💳 Using MAINNET CryptoBot API (https://pay.crypt.bot/)")
    else:
        logger.warning("⚠️ REAL mode selected but no valid API token")
        logger.warning("⚠️ Please set API_TOKEN in config.cfg or use test mode")
        crypto = None
else:
    # Testnet режим
    if TEST_CRYPTO_TOKEN:
        crypto = CryptoPayment(TEST_CRYPTO_TOKEN, testnet=True)
        logger.info("🧪 Using TESTNET CryptoBot API (https://testnet-pay.crypt.bot/)")
    else:
        logger.warning("⚠️ No TESTNET token provided")
        crypto = None

# Словарь для отслеживания активных инвойсов
active_invoices = {}


# FSM состояния
class GameStates(StatesGroup):
    choosing_game = State()
    entering_bet = State()
    waiting_for_opponent = State()
    coinflip_choice = State()
    deposit_amount = State()
    cashout_amount = State()
    admin_ban_user_id = State()
    admin_ban_reason = State()
    admin_unban_user_id = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


def get_main_keyboard(user_id: int = None):
    """Главное меню"""
    keyboard_buttons = [
        [InlineKeyboardButton(text="🎮 Создать комнату", callback_data="create_room")],
        [InlineKeyboardButton(text="🔍 Найти игру", callback_data="find_room")],
        [InlineKeyboardButton(text="💰 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="💳 Пополнить", callback_data="deposit")],
        [InlineKeyboardButton(text="💸 Вывод", callback_data="cashout"),
         InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
    ]
    
    # Добавляем админ-панель для администраторов
    if user_id and is_admin(user_id):
        keyboard_buttons.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel")])
    
    keyboard_buttons.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_game_type_keyboard():
    """Выбор типа игры"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Кубик", callback_data="game_type_dice")],
        [InlineKeyboardButton(text="🪙 Монетка", callback_data="game_type_coinflip")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def get_back_keyboard():
    """Кнопка назад"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ])
    return keyboard


async def check_ban(message: Message) -> bool:
    """Проверка бана пользователя"""
    user_id = message.from_user.id
    
    if await ban_manager.is_banned(user_id):
        ban_info = await ban_manager.get_ban_info(user_id)
        reason = ban_info.get('reason', 'Не указана')
        
        text = (
            "🚫 ВЫ ЗАБЛОКИРОВАНЫ\n\n"
            f"Причина: {reason}\n\n"
            "Для разблокировки обратитесь к администратору"
        )
        
        await message.answer(text)
        return True
    
    return False


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Проверка бана
    if await check_ban(message):
        return
    
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, username, STARTING_BALANCE)
        welcome_text = (
            f"🎰 Добро пожаловать в MULTIPLAYER CASINO, {username}!\n\n"
            f"🎁 Стартовый баланс: ${STARTING_BALANCE:.2f}\n\n"
            "🎮 Играйте 1 на 1 с другими игроками:\n"
            "• 🎲 Кубик - у кого больше, тот выиграл\n"
            "• 🪙 Монетка - угадайте результат\n\n"
            "💰 Победитель забирает всю ставку!"
        )
    else:
        balance = user['balance']
        welcome_text = (
            f"👋 С возвращением, {username}!\n\n"
            f"💰 Баланс: ${balance:.2f}\n\n"
            "Создайте комнату или найдите противника!"
        )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id))


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    user_id = callback.from_user.id
    
    # Проверка бана
    if await ban_manager.is_banned(user_id):
        ban_info = await ban_manager.get_ban_info(user_id)
        reason = ban_info.get('reason', 'Не указана')
        await callback.message.edit_text(
            f"🚫 ВЫ ЗАБЛОКИРОВАНЫ\n\nПричина: {reason}"
        )
        await callback.answer()
        return
    
    balance = await db.get_balance(user_id)
    
    text = (
        "🎰 Главное меню\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n\n"
        "Выберите действие:"
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=get_main_keyboard(user_id))
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=get_main_keyboard(user_id))
    
    await callback.answer()


# ========== СОЗДАНИЕ КОМНАТЫ ==========

@dp.callback_query(F.data == "create_room")
async def create_room_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания комнаты"""
    user_id = callback.from_user.id
    
    # Проверка бана
    if await ban_manager.is_banned(user_id):
        ban_info = await ban_manager.get_ban_info(user_id)
        reason = ban_info.get('reason', 'Не указана')
        await callback.answer(f"🚫 Вы заблокированы\nПричина: {reason}", show_alert=True)
        return
    
    balance = await db.get_balance(user_id)
    
    text = (
        "🎮 СОЗДАНИЕ КОМНАТЫ\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n\n"
        "Выберите игру:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_game_type_keyboard())
    await state.set_state(GameStates.choosing_game)
    await callback.answer()


@dp.callback_query(F.data.startswith("game_type_"))
async def choose_game_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа игры"""
    game_type = callback.data.split("_")[2]  # dice или coinflip
    await state.update_data(game_type=game_type)
    
    game_name = "🎲 Кубик" if game_type == "dice" else "🪙 Монетка"
    balance = await db.get_balance(callback.from_user.id)
    
    text = (
        f"🎮 Создание комнаты: {game_name}\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n\n"
        f"Введите размер ставки:\n"
        f"(от ${MIN_BET:.2f} до ${MAX_BET:.2f})"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await state.set_state(GameStates.entering_bet)
    await callback.answer()


@dp.message(GameStates.entering_bet)
async def create_room_with_bet(message: Message, state: FSMContext):
    """Создание комнаты с указанной ставкой"""
    try:
        bet = float(message.text)
        
        if bet < MIN_BET or bet > MAX_BET:
            await message.answer(f"❌ Ставка должна быть от ${MIN_BET:.2f} до ${MAX_BET:.2f}")
            return
        
        balance = await db.get_balance(message.from_user.id)
        if bet > balance:
            await message.answer(
                f"❌ Недостаточно средств!\n💰 Ваш баланс: ${balance:.2f}",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        # Создаем комнату
        data = await state.get_data()
        game_type = data.get("game_type")
        
        room = room_manager.create_room(message.from_user.id, game_type, bet)
        await state.update_data(room_id=room.room_id)
        
        game_name = "🎲 Кубик" if game_type == "dice" else "🪙 Монетка"
        
        # Резервируем ставку
        await db.update_balance(message.from_user.id, -bet)
        
        text = (
            f"✅ Комната создана!\n\n"
            f"🎮 Игра: {game_name}\n"
            f"💰 Ставка: ${bet:.2f}\n"
            f"🆔 ID комнаты: {room.room_id}\n\n"
            f"⏳ Ожидание противника...\n\n"
            f"Другой игрок может подключиться через 'Найти игру' или по ID комнаты"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_room_{room.room_id}")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"check_room_{room.room_id}")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(GameStates.waiting_for_opponent)
    
    except ValueError:
        await message.answer("❌ Введите корректную сумму числом")


@dp.callback_query(F.data.startswith("cancel_room_"))
async def cancel_room(callback: CallbackQuery, state: FSMContext):
    """Отмена комнаты"""
    room_id = callback.data.split("_")[2]
    room = room_manager.get_room(room_id)
    
    if room and room.status == "waiting":
        # Возвращаем ставку
        await db.update_balance(room.creator_id, room.bet)
        room_manager.delete_room(room_id)
        
        await callback.message.edit_text(
            "❌ Комната отменена\n💰 Ставка возвращена",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.answer("❌ Комната уже не существует или игра началась")
    
    await state.clear()


@dp.callback_query(F.data.startswith("check_room_"))
async def check_room(callback: CallbackQuery):
    """Проверка статуса комнаты"""
    room_id = callback.data.split("_")[2]
    room = room_manager.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната не найдена", show_alert=True)
        return
    
    if room.status == "playing":
        await callback.answer("✅ Противник подключился! Играем...", show_alert=True)
        # Автоматически начинаем игру
        await start_multiplayer_game(callback.message, room)
    else:
        await callback.answer("⏳ Пока никто не подключился", show_alert=True)


# ========== ПОИСК И ПОДКЛЮЧЕНИЕ К КОМНАТЕ ==========

@dp.callback_query(F.data == "find_room")
async def find_room(callback: CallbackQuery):
    """Поиск доступных комнат"""
    waiting_rooms = room_manager.get_waiting_rooms()
    
    if not waiting_rooms:
        text = (
            "🔍 Нет доступных комнат\n\n"
            "Создайте свою комнату или подождите,\n"
            "пока кто-то создаст новую игру"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    else:
        text = "🔍 ДОСТУПНЫЕ КОМНАТЫ\n\n"
        
        keyboard_buttons = []
        for room in waiting_rooms[:10]:  # Показываем максимум 10 комнат
            game_emoji = "🎲" if room.game_type == "dice" else "🪙"
            game_name = "Кубик" if room.game_type == "dice" else "Монетка"
            
            button_text = f"{game_emoji} {game_name} - ${room.bet:.2f}"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"join_{room.room_id}"
                )
            ])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="find_room")])
        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    await callback.answer()


@dp.callback_query(F.data.startswith("join_"))
async def join_room(callback: CallbackQuery, state: FSMContext):
    """Подключение к комнате"""
    room_id = callback.data.split("_")[1]
    room = room_manager.get_room(room_id)
    
    if not room:
        await callback.answer("❌ Комната уже не доступна", show_alert=True)
        return
    
    if room.status != "waiting":
        await callback.answer("❌ В комнату уже кто-то подключился", show_alert=True)
        return
    
    # Проверяем баланс
    balance = await db.get_balance(callback.from_user.id)
    if balance < room.bet:
        await callback.answer(
            f"❌ Недостаточно средств!\nНужно: ${room.bet:.2f}\nУ вас: ${balance:.2f}",
            show_alert=True
        )
        return
    
    # Подключаемся
    if room_manager.join_room(room_id, callback.from_user.id):
        # Резервируем ставку
        await db.update_balance(callback.from_user.id, -room.bet)
        
        game_name = "🎲 Кубик" if room.game_type == "dice" else "🪙 Монетка"
        
        text = (
            f"✅ Вы подключились к игре!\n\n"
            f"🎮 Игра: {game_name}\n"
            f"💰 Ставка: ${room.bet:.2f}\n\n"
            f"⚔️ Начинаем игру..."
        )
        
        await callback.message.edit_text(text)
        
        # Начинаем игру
        await start_multiplayer_game(callback.message, room)
    else:
        await callback.answer("❌ Не удалось подключиться", show_alert=True)


# ========== ИГРОВОЙ ПРОЦЕСС ==========

async def start_multiplayer_game(message: Message, room):
    """Начало мультиплеер игры"""
    
    if room.game_type == "dice":
        # Анимация броска кубика
        await animate_dice_game(message, room)
    
    elif room.game_type == "coinflip":
        # Монетка - нужно дождаться выборов обоих игроков
        await request_coinflip_choices(message, room)


async def animate_dice_game(message: Message, room):
    """Анимация игры в кубик"""
    creator_name = (await db.get_user(room.creator_id))['username']
    opponent_name = (await db.get_user(room.opponent_id))['username']
    
    # Уведомляем обоих о начале
    start_text = (
        "🎲 БРОСАЕМ КУБИКИ!\n\n"
        f"⚔️ {creator_name} VS {opponent_name}\n\n"
        "🎲 ░░░░░░"
    )
    
    try:
        msg1 = await bot.send_message(room.creator_id, start_text)
        msg2 = await bot.send_message(room.opponent_id, start_text)
    except:
        result = room.play()
        await show_dice_result(message, room, result)
        return
    
    # Анимация загрузки
    frames = [
        "🎲 ░░░░░░",
        "🎲 █░░░░░",
        "🎲 ██░░░░",
        "🎲 ███░░░",
        "🎲 ████░░",
        "🎲 █████░",
        "🎲 ██████"
    ]
    
    for frame in frames:
        await asyncio.sleep(0.3)
        text = (
            "🎲 БРОСАЕМ КУБИКИ!\n\n"
            f"⚔️ {creator_name} VS {opponent_name}\n\n"
            f"{frame}"
        )
        try:
            await msg1.edit_text(text)
            await msg2.edit_text(text)
        except:
            pass
    
    await asyncio.sleep(0.5)
    
    # Играем
    result = room.play()
    
    # Удаляем анимацию и показываем результат
    try:
        await msg1.delete()
        await msg2.delete()
    except:
        pass
    
    await show_dice_result(message, room, result)


async def show_dice_result(message: Message, room, result):
    """Показать результат игры в кубик"""
    creator_name = (await db.get_user(room.creator_id))['username']
    opponent_name = (await db.get_user(room.opponent_id))['username']
    
    dice_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    
    creator_dice = dice_emoji[result['creator_result'] - 1]
    opponent_dice = dice_emoji[result['opponent_result'] - 1]
    
    text = (
        "🎲 РЕЗУЛЬТАТ ИГРЫ В КУБИК\n\n"
        f"👤 {creator_name}: {creator_dice} ({result['creator_result']})\n"
        f"👤 {opponent_name}: {opponent_dice} ({result['opponent_result']})\n\n"
    )
    
    if result['is_draw']:
        # Ничья - возврат ставок
        text += f"🤝 НИЧЬЯ!\n\n💰 Ставки возвращены"
        await db.update_balance(room.creator_id, room.bet)
        await db.update_balance(room.opponent_id, room.bet)
        
        # История
        await db.add_game_to_history(room.creator_id, "dice_mp", room.bet, room.bet, "Draw")
        await db.add_game_to_history(room.opponent_id, "dice_mp", room.bet, room.bet, "Draw")
    else:
        winner_id = result['winner_id']
        loser_id = room.opponent_id if winner_id == room.creator_id else room.creator_id
        winner_name = creator_name if winner_id == room.creator_id else opponent_name
        
        # Расчет выигрыша с учетом комиссии
        full_prize = room.bet * 2  # Полный призовой фонд
        fee_amount = full_prize * (HOUSE_FEE / 100)  # Комиссия
        final_prize = full_prize - fee_amount  # Итоговый выигрыш после комиссии
        
        text += f"🏆 ПОБЕДИТЕЛЬ: {winner_name}\n\n"
        text += f"💰 Выигрыш: ${final_prize:.2f}\n"
        if HOUSE_FEE > 0:
            text += f"💸 Комиссия казино ({HOUSE_FEE}%): -${fee_amount:.2f}\n"
        text += f"📊 Призовой фонд: ${full_prize:.2f}"
        
        # Начисляем выигрыш (уже с вычетом комиссии)
        await db.update_balance(winner_id, final_prize)
        
        # История (сохраняем полный выигрыш для статистики, но реально начислен final_prize)
        await db.add_game_to_history(winner_id, "dice_mp", room.bet, final_prize, "Win")
        await db.add_game_to_history(loser_id, "dice_mp", room.bet, 0, "Loss")
    
    # Клавиатура с реваншем
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Реванш", callback_data=f"rematch_dice_{room.bet}_{room.creator_id}_{room.opponent_id}")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")]
    ])
    
    # Уведомляем обоих игроков
    try:
        await bot.send_message(room.creator_id, text, reply_markup=keyboard)
    except:
        pass
    
    try:
        await bot.send_message(room.opponent_id, text, reply_markup=keyboard)
    except:
        pass
    
    # Удаляем комнату
    room_manager.delete_room(room.room_id)


async def request_coinflip_choices(message: Message, room):
    """Запросить выбор только у создателя комнаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦅 Орел", callback_data=f"coin_choice_{room.room_id}_heads")],
        [InlineKeyboardButton(text="🪙 Решка", callback_data=f"coin_choice_{room.room_id}_tails")]
    ])
    
    text = "🪙 Вы создатель комнаты!\nВыберите сторону монетки:"
    
    # Отправляем только создателю
    try:
        await bot.send_message(room.creator_id, text, reply_markup=keyboard)
    except:
        pass
    
    # Уведомляем оппонента
    opponent_text = "⏳ Создатель комнаты выбирает сторону...\nВы автоматически получите противоположную сторону"
    try:
        await bot.send_message(room.opponent_id, opponent_text)
    except:
        pass


@dp.callback_query(F.data.startswith("coin_choice_"))
async def coinflip_choice(callback: CallbackQuery):
    """Обработка выбора в монетке (только создатель)"""
    parts = callback.data.split("_")
    room_id = parts[2]
    choice = parts[3]  # heads или tails
    
    room = room_manager.get_room(room_id)
    if not room:
        await callback.answer("❌ Игра уже завершена", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Только создатель может выбирать
    if user_id != room.creator_id:
        await callback.answer("❌ Только создатель комнаты выбирает сторону", show_alert=True)
        return
    
    # Сохраняем выбор создателя
    room.set_creator_choice(choice)
    opponent_choice = room.get_opponent_choice()
    
    choice_emoji = {"heads": "🦅 Орел", "tails": "🪙 Решка"}
    
    await callback.message.edit_text(
        f"✅ Вы выбрали: {choice_emoji[choice]}\n\n"
        f"🎲 Подбрасываем монетку..."
    )
    
    # Уведомляем оппонента о его стороне
    try:
        await bot.send_message(
            room.opponent_id,
            f"✅ Создатель выбрал свою сторону\n"
            f"🎯 Ваша сторона: {choice_emoji[opponent_choice]}\n\n"
            f"🎲 Подбрасываем монетку..."
        )
    except:
        pass
    
    # Небольшая задержка для драматического эффекта
    await asyncio.sleep(1)
    
    # Играем
    result = room.play()
    await show_coinflip_result(callback.message, room, result)
    
    await callback.answer()


async def show_coinflip_result(message: Message, room, result):
    """Показать результат монетки"""
    creator_name = (await db.get_user(room.creator_id))['username']
    opponent_name = (await db.get_user(room.opponent_id))['username']
    
    choice_emoji = {"heads": "🦅 Орел", "tails": "🪙 Решка"}
    
    text = (
        "🪙 РЕЗУЛЬТАТ ИГРЫ В МОНЕТКУ\n\n"
        f"Выпало: {choice_emoji[result['result']]}\n\n"
        f"👤 {creator_name} выбрал: {choice_emoji[result['creator_choice']]}\n"
        f"👤 {opponent_name} получил: {choice_emoji[result['opponent_choice']]}\n\n"
    )
    
    if result['is_draw']:
        text += f"🤝 НИЧЬЯ!\n\n💰 Ставки возвращены"
        await db.update_balance(room.creator_id, room.bet)
        await db.update_balance(room.opponent_id, room.bet)
        
        await db.add_game_to_history(room.creator_id, "coinflip_mp", room.bet, room.bet, "Draw")
        await db.add_game_to_history(room.opponent_id, "coinflip_mp", room.bet, room.bet, "Draw")
    else:
        winner_id = result['winner_id']
        loser_id = room.opponent_id if winner_id == room.creator_id else room.creator_id
        winner_name = creator_name if winner_id == room.creator_id else opponent_name
        
        # Расчет выигрыша с учетом комиссии
        full_prize = room.bet * 2  # Полный призовой фонд
        fee_amount = full_prize * (HOUSE_FEE / 100)  # Комиссия
        final_prize = full_prize - fee_amount  # Итоговый выигрыш после комиссии
        
        text += f"🏆 ПОБЕДИТЕЛЬ: {winner_name}\n\n"
        text += f"💰 Выигрыш: ${final_prize:.2f}\n"
        if HOUSE_FEE > 0:
            text += f"💸 Комиссия казино ({HOUSE_FEE}%): -${fee_amount:.2f}\n"
        text += f"📊 Призовой фонд: ${full_prize:.2f}"
        
        # Начисляем выигрыш (уже с вычетом комиссии)
        await db.update_balance(winner_id, final_prize)
        
        # История
        await db.add_game_to_history(winner_id, "coinflip_mp", room.bet, final_prize, "Win")
        await db.add_game_to_history(loser_id, "coinflip_mp", room.bet, 0, "Loss")
    
    # Клавиатура с реваншем
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Реванш", callback_data=f"rematch_coinflip_{room.bet}_{room.creator_id}_{room.opponent_id}")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")]
    ])
    
    # Уведомляем обоих
    try:
        await bot.send_message(room.creator_id, text, reply_markup=keyboard)
    except:
        pass
    
    try:
        await bot.send_message(room.opponent_id, text, reply_markup=keyboard)
    except:
        pass
    
    room_manager.delete_room(room.room_id)


# ========== РЕВАНШ ==========

# Хранилище для отслеживания запросов на реванш
rematch_requests = {}

@dp.callback_query(F.data.startswith("rematch_"))
async def request_rematch(callback: CallbackQuery):
    """Обработка запроса на реванш"""
    parts = callback.data.split("_")
    game_type = parts[1]  # dice или coinflip
    bet = float(parts[2])
    player1_id = int(parts[3])
    player2_id = int(parts[4])
    
    user_id = callback.from_user.id
    opponent_id = player2_id if user_id == player1_id else player1_id
    
    # Проверяем баланс
    balance = await db.get_balance(user_id)
    if balance < bet:
        await callback.answer(
            f"❌ Недостаточно средств для реванша!\nНужно: ${bet:.2f}\nУ вас: ${balance:.2f}",
            show_alert=True
        )
        return
    
    # Создаем уникальный ключ для пары игроков
    pair_key = f"{min(player1_id, player2_id)}_{max(player1_id, player2_id)}_{game_type}_{bet}"
    
    # Проверяем, есть ли уже запрос от оппонента
    if pair_key in rematch_requests:
        existing_request = rematch_requests[pair_key]
        
        # Если оппонент уже запросил реванш
        if existing_request['requester_id'] != user_id:
            await callback.message.edit_text("✅ Реванш принят! Создаем новую игру...")
            
            # Удаляем запрос
            del rematch_requests[pair_key]
            
            # Создаем новую комнату (инициатор реванша становится создателем)
            room = room_manager.create_room(existing_request['requester_id'], game_type, bet)
            
            # Подключаем второго игрока (БЕЗ снятия денег - это бесплатный реванш)
            room_manager.join_room(room.room_id, user_id)
            
            game_name = "🎲 Кубик" if game_type == "dice" else "🪙 Монетка"
            
            # Уведомляем обоих
            text = f"🔄 РЕВАНШ!\n\n🎮 Игра: {game_name}\n💰 Ставка: ${bet:.2f}\n\n⚔️ Начинаем..."
            
            try:
                await bot.send_message(existing_request['requester_id'], text)
            except:
                pass
            
            try:
                await bot.send_message(user_id, text)
            except:
                pass
            
            # Запускаем игру
            await asyncio.sleep(1)
            await start_multiplayer_game(callback.message, room)
            
            await callback.answer("✅ Реванш начался!")
        else:
            await callback.answer("⏳ Вы уже запросили реванш, ждите оппонента", show_alert=True)
    else:
        # Сохраняем запрос на реванш
        rematch_requests[pair_key] = {
            'requester_id': user_id,
            'opponent_id': opponent_id,
            'game_type': game_type,
            'bet': bet
        }
        
        game_name = "🎲 Кубик" if game_type == "dice" else "🪙 Монетка"
        
        await callback.message.edit_text(
            f"⏳ Запрос на реванш отправлен!\n\n"
            f"🎮 Игра: {game_name}\n"
            f"💰 Ставка: ${bet:.2f}\n\n"
            f"Ожидание ответа от противника..."
        )
        
        # Уведомляем оппонента
        opponent_name = (await db.get_user(user_id))['username']
        notification = (
            f"🔔 {opponent_name} предлагает реванш!\n\n"
            f"🎮 Игра: {game_name}\n"
            f"💰 Ставка: ${bet:.2f}\n\n"
            f"Нажмите 🔄 Реванш чтобы принять"
        )
        
        try:
            await bot.send_message(opponent_id, notification)
        except:
            pass
        
        await callback.answer("✅ Запрос на реванш отправлен!")


# ========== ПРОФИЛЬ И СТАТИСТИКА ==========

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    """Показать профиль с историей последних 5 ставок"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Получаем последние 5 игр
    recent_games = await db.get_recent_games(user_id, 5)
    
    # Формируем текст профиля
    username = user['username']
    balance = user['balance']
    games_played = user['games_played']
    total_wagered = user['total_wagered']
    profit = user['total_won'] - user['total_lost']
    
    # Определяем ранг
    if games_played > 100:
        rank = "👑 ЛЕГЕНДА"
    elif games_played > 50:
        rank = "💎 ПРО"
    elif games_played > 20:
        rank = "⭐ ИГРОК"
    else:
        rank = "🍀 НОВИЧОК"
    
    text = (
        f"👤 ПРОФИЛЬ: @{username}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Баланс: ${balance:.2f}\n"
        f"🏆 Ранг: {rank}\n"
        f"🎮 Игр сыграно: {games_played}\n"
        f"💵 Всего ставок: ${total_wagered:.2f}\n"
    )
    
    if profit >= 0:
        text += f"📈 Прибыль: +${profit:.2f}\n"
    else:
        text += f"📉 Убыток: -${abs(profit):.2f}\n"
    
    # История последних 5 ставок
    text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 ПОСЛЕДНИЕ 5 СТАВОК:\n\n"
    
    if recent_games:
        for i, game in enumerate(recent_games, 1):
            game_type = game.get("game_type", "Unknown")
            bet = game.get("bet", 0)
            win_amount = game.get("win_amount", 0)
            profit_game = game.get("profit", 0)
            
            # Иконки для игр
            icons = {
                "dice_mp": "🎲",
                "coinflip_mp": "🪙",
                "dice": "🎲",
                "coinflip": "🪙",
                "roulette": "🎰",
                "slots": "🎰"
            }
            icon = icons.get(game_type, "🎮")
            
            # Название игры
            game_name = game_type.replace("_mp", "").upper()
            
            # Результат
            if profit_game > 0:
                result = f"✅ +${profit_game:.2f}"
            elif profit_game < 0:
                result = f"❌ -${abs(profit_game):.2f}"
            else:
                result = f"🤝 ±$0.00"
            
            text += f"{i}. {icon} {game_name}\n"
            text += f"   💰 Ставка: ${bet:.2f}\n"
            text += f"   {result}\n\n"
    else:
        text += "Нет сыгранных игр\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    """Статистика"""
    user_id = callback.from_user.id
    stats = await db.get_user_stats(user_id)
    
    if not stats:
        await callback.answer("❌ Статистика не найдена")
        return
    
    win_rate = 0
    if stats['games_played'] > 0:
        wins = stats['total_won']
        total = stats['total_wagered']
        win_rate = (wins / total * 100) if total > 0 else 0
    
    text = (
        "📊 СТАТИСТИКА\n\n"
        f"💰 Баланс: ${stats['balance']:.2f}\n"
        f"💵 Депозитов: ${stats['total_deposited']:.2f}\n"
        f"🎮 Игр: {stats['games_played']}\n"
        f"💸 Ставок: ${stats['total_wagered']:.2f}\n"
        f"✅ Выиграно: ${stats['total_won']:.2f}\n"
        f"❌ Проиграно: ${stats['total_lost']:.2f}\n"
        f"📈 Прибыль: ${stats['profit']:.2f}\n"
        f"🎯 Винрейт: {win_rate:.1f}%"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    """Помощь"""
    text = (
        "ℹ️ ПОМОЩЬ - MULTIPLAYER CASINO\n\n"
        "🎮 КАК ИГРАТЬ:\n\n"
        "1️⃣ Создайте комнату с выбранной игрой и ставкой\n"
        "2️⃣ Дождитесь противника или найдите существующую комнату\n"
        "3️⃣ Играйте 1 на 1!\n"
        "4️⃣ Победитель забирает всю ставку\n\n"
        "🎲 КУБИК:\n"
        "Оба игрока бросают кубик\n"
        "У кого больше - тот выиграл!\n\n"
        "🪙 МОНЕТКА:\n"
        "Выберите орел или решку\n"
        "Угадавший забирает приз!\n\n"
        "💰 В случае ничьей ставки возвращаются\n\n"
        "Удачи! 🍀"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()


# ========== ПОПОЛНЕНИЕ ==========

async def auto_check_payment(invoice_id: int, user_id: int):
    """Автоматическая проверка оплаты в фоне"""
    max_attempts = 120  # 120 попыток = 10 минут (каждые 5 секунд)
    attempt = 0
    
    logger.info(f"Starting payment check for invoice {invoice_id}, user {user_id}")
    
    while attempt < max_attempts:
        await asyncio.sleep(5)  # Проверяем каждые 5 секунд
        attempt += 1
        
        # Проверяем, не удален ли инвойс
        if invoice_id not in active_invoices:
            logger.info(f"Invoice {invoice_id} removed from active list")
            return
        
        try:
            # Проверяем статус
            invoice = await crypto.check_invoice(invoice_id)
            
            if invoice:
                status = invoice.get("status", "").lower()
                
                # Логируем для отладки
                if attempt % 12 == 0:  # Каждую минуту
                    logger.info(f"Checking invoice {invoice_id}: status={status}, attempt={attempt}")
                
                # Проверяем статус "paid"
                if status == "paid":
                    # Получаем сумму - может быть в разных полях
                    amount = None
                    
                    # Пробуем разные поля для суммы (согласно документации API)
                    if "paid_amount" in invoice:
                        amount = float(invoice["paid_amount"])
                    elif "amount" in invoice:
                        amount = float(invoice["amount"])
                    elif "paid_usd_amount" in invoice:
                        amount = float(invoice["paid_usd_amount"])
                    elif "amount_usd" in invoice:
                        amount = float(invoice["amount_usd"])
                    
                    if amount:
                        # Проверяем, не был ли уже зачислен этот платеж
                        invoice_data = active_invoices.get(invoice_id)
                        if invoice_data and invoice_data.get('processed'):
                            logger.info(f"Invoice {invoice_id} already processed, skipping")
                            return
                        
                        # Отмечаем как обработанный
                        active_invoices[invoice_id]['processed'] = True
                        
                        # Зачисляем средства
                        await db.add_deposit(user_id, amount)
                        new_balance = await db.get_balance(user_id)
                        
                        logger.info(f"✅ Payment confirmed! Invoice {invoice_id}: ${amount} for user {user_id}")
                        
                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                user_id,
                                f"✅ ПЛАТЕЖ ПОЛУЧЕН!\n\n"
                                f"💰 Зачислено: ${amount:.2f}\n"
                                f"💳 Новый баланс: ${new_balance:.2f}\n\n"
                                f"Спасибо за пополнение!",
                                reply_markup=get_back_keyboard()
                            )
                            logger.info(f"Payment notification sent to user {user_id}")
                        except Exception as e:
                            logger.error(f"Failed to send payment confirmation: {e}")
                        
                        # Удаляем из активных
                        if invoice_id in active_invoices:
                            del active_invoices[invoice_id]
                        
                        return
                    else:
                        logger.warning(f"Invoice {invoice_id} is paid but amount is missing")
            else:
                # Если инвойс не найден, продолжаем проверку (может быть еще не создан в API)
                if attempt % 12 == 0:
                    logger.debug(f"Invoice {invoice_id} not found in API yet, continuing...")
                    
        except Exception as e:
            logger.error(f"Error checking invoice {invoice_id}: {e}")
            # Продолжаем проверку при ошибках
    
    # Таймаут - удаляем из активных
    if invoice_id in active_invoices:
        del active_invoices[invoice_id]
    
    logger.warning(f"⏰ Payment check timeout for invoice {invoice_id} after {max_attempts} attempts")


@dp.callback_query(F.data == "deposit")
async def start_deposit(callback: CallbackQuery, state: FSMContext):
    """Пополнение"""
    text = (
        "💳 Пополнение баланса\n\n"
        "Введите сумму в USD:\n"
        "Минимум: $5.00"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await state.set_state(GameStates.deposit_amount)
    await callback.answer()


@dp.message(GameStates.deposit_amount)
async def process_deposit(message: Message, state: FSMContext):
    """Обработка пополнения"""
    try:
        amount = float(message.text)
        
        if amount < 5:
            await message.answer("❌ Минимум $5.00")
            return
        
        user_id = message.from_user.id
        invoice = await crypto.create_invoice(amount, "USD", f"Пополнение ${amount:.2f}", user_id)
        
        if invoice:
            invoice_id = invoice['invoice_id']
            
            # Сохраняем инвойс для автопроверки
            active_invoices[invoice_id] = {
                'user_id': user_id,
                'amount': amount,
                'created_at': asyncio.get_event_loop().time()
            }
            
            # Кнопка для оплаты
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=invoice['bot_invoice_url'])],
                [InlineKeyboardButton(text="🔄 Проверить платеж", callback_data=f"check_invoice_{invoice_id}")],
                [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_to_menu")]
            ])
            
            # Сообщение в зависимости от режима
            if is_testnet:
                text = (
                    f"💳 Инвойс создан!\n\n"
                    f"💰 Сумма: ${amount:.2f}\n\n"
                    f"🧪 TESTNET режим\n"
                    f"Для получения тестовых монет: @CryptoPayTestBot\n\n"
                    f"💳 Нажмите 'Оплатить' и оплатите через CryptoTestnetBot\n"
                    f"⚡ Деньги зачислятся автоматически после оплаты!"
                )
            else:
                text = (
                    f"💳 Инвойс создан!\n\n"
                    f"💰 Сумма: ${amount:.2f}\n\n"
                    f"💳 Нажмите 'Оплатить' и оплатите через CryptoBot\n"
                    f"⚡ Деньги зачислятся автоматически после оплаты!\n\n"
                    f"Принимаем: USDT, TON, BTC, ETH, TRX, USDC"
                )
            
            await message.answer(text, reply_markup=keyboard)
            
            # Запускаем автопроверку в фоне
            asyncio.create_task(auto_check_payment(invoice_id, user_id))
            
            await state.clear()
        else:
            await message.answer("❌ Ошибка создания инвойса", reply_markup=get_back_keyboard())
            await state.clear()
    
    except ValueError:
        await message.answer("❌ Введите корректную сумму")


@dp.callback_query(F.data.startswith("check_invoice_"))
async def manual_check_invoice(callback: CallbackQuery):
    """Ручная проверка статуса инвойса"""
    invoice_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Проверяем, относится ли этот инвойс к пользователю
    if invoice_id not in active_invoices:
        await callback.answer("❌ Инвойс не найден", show_alert=True)
        return
    
    invoice_data = active_invoices[invoice_id]
    if invoice_data['user_id'] != user_id:
        await callback.answer("❌ Это не ваш инвойс", show_alert=True)
        return
    
    # Проверяем статус
    await callback.answer("⏳ Проверяю платеж...", show_alert=False)
    
    invoice = await crypto.check_invoice(invoice_id)
    
    if invoice:
        status = invoice.get("status", "").lower()
        
        if status == "paid":
            # Получаем сумму
            amount = None
            if "amount" in invoice:
                amount = float(invoice["amount"])
            elif "paid_amount" in invoice:
                amount = float(invoice["paid_amount"])
            elif "paid_usd_amount" in invoice:
                amount = float(invoice["paid_usd_amount"])
            
            if amount:
                # Проверяем, не был ли уже обработан
                if invoice_data.get('processed'):
                    new_balance = await db.get_balance(user_id)
                    await callback.message.edit_text(
                        f"✅ ПЛАТЕЖ УЖЕ ОБРАБОТАН!\n\n"
                        f"💰 Сумма: ${amount:.2f}\n"
                        f"💳 Ваш баланс: ${new_balance:.2f}",
                        reply_markup=get_back_keyboard()
                    )
                else:
                    # Отмечаем и зачисляем
                    active_invoices[invoice_id]['processed'] = True
                    await db.add_deposit(user_id, amount)
                    new_balance = await db.get_balance(user_id)
                    
                    await callback.message.edit_text(
                        f"✅ ПЛАТЕЖ ПОДТВЕРЖДЕН!\n\n"
                        f"💰 Зачислено: ${amount:.2f}\n"
                        f"💳 Новый баланс: ${new_balance:.2f}\n\n"
                        f"Спасибо за пополнение!",
                        reply_markup=get_back_keyboard()
                    )
                    
                    # Удаляем из активных
                    del active_invoices[invoice_id]
                    
                    logger.info(f"✅ Manual check: Payment confirmed for invoice {invoice_id}, amount ${amount}")
            else:
                await callback.message.edit_text(
                    "⚠️ Платеж обнаружен, но сумма не найдена\n\nОбратитесь к администратору",
                    reply_markup=get_back_keyboard()
                )
        elif status == "active":
            await callback.answer("⏳ Платеж еще не получен", show_alert=True)
        else:
            status_text = {
                "expired": "⏰ Истек",
                "refund": "↩️ Возвращен",
                "failed": "❌ Ошибка"
            }
            await callback.answer(f"Статус: {status_text.get(status, status)}", show_alert=True)
    else:
        await callback.answer("❌ Инвойс не найден в системе платежей", show_alert=True)


# ========== ВЫВОД СРЕДСТВ ==========

@dp.callback_query(F.data == "cashout")
async def cashout_menu(callback: CallbackQuery):
    """Меню вывода средств"""
    user_id = callback.from_user.id
    balance = await db.get_balance(user_id)
    
    # Получаем последние запросы на вывод
    user_cashouts = await cashout_manager.get_user_cashouts(user_id)
    pending_count = len([c for c in user_cashouts if c.get("status") == "pending"])
    
    text = (
        "💸 ВЫВОД СРЕДСТВ\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n\n"
    )
    
    if pending_count > 0:
        text += f"⏳ Ожидающих выводов: {pending_count}\n\n"
    
    text += "Выберите действие:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести средства", callback_data="cashout_request")],
        [InlineKeyboardButton(text="📋 История выводов", callback_data="cashout_history")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "cashout_request")
async def cashout_request_start(callback: CallbackQuery, state: FSMContext):
    """Начало запроса на вывод"""
    user_id = callback.from_user.id
    balance = await db.get_balance(user_id)
    
    if balance < MIN_BET:
        await callback.answer(
            f"❌ Минимальная сумма для вывода: ${MIN_BET:.2f}",
            show_alert=True
        )
        return
    
    text = (
        "💸 ВЫВОД СРЕДСТВ\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n\n"
        f"Введите сумму для вывода:\n"
        f"(от ${MIN_BET:.2f} до ${balance:.2f})"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await state.set_state(GameStates.cashout_amount)
    await callback.answer()


@dp.message(GameStates.cashout_amount)
async def process_cashout(message: Message, state: FSMContext):
    """Обработка запроса на вывод"""
    try:
        amount = float(message.text)
        user_id = message.from_user.id
        balance = await db.get_balance(user_id)
        
        # Валидация суммы
        if amount < MIN_BET:
            await message.answer(f"❌ Минимальная сумма для вывода: ${MIN_BET:.2f}")
            return
        
        if amount > balance:
            await message.answer(
                f"❌ Недостаточно средств!\n💰 Ваш баланс: ${balance:.2f}",
                reply_markup=get_back_keyboard()
            )
            await state.clear()
            return
        
        # Снимаем баланс
        new_balance = await db.update_balance(user_id, -amount)
        
        # Получаем имя пользователя
        user = await db.get_user(user_id)
        username = user.get('username') if user else None
        
        # Создаем запрос на вывод
        cashout_id = await cashout_manager.create_cashout(user_id, amount, username)
        
        text = (
            "✅ ЗАПРОС НА ВЫВОД СОЗДАН!\n\n"
            f"💰 Сумма: ${amount:.2f}\n"
            f"💳 Новый баланс: ${new_balance:.2f}\n"
            f"🆔 ID запроса: {cashout_id}\n\n"
            f"⏳ Ваш запрос обрабатывается администратором\n"
            f"Средства будут переведены в ближайшее время"
        )
        
        await message.answer(text, reply_markup=get_back_keyboard())
        await state.clear()
        
        logger.info(f"Cashout request created: {cashout_id} for user {user_id}, amount: ${amount}")
    
    except ValueError:
        await message.answer("❌ Введите корректную сумму числом")


@dp.callback_query(F.data == "cashout_history")
async def cashout_history(callback: CallbackQuery):
    """История выводов"""
    user_id = callback.from_user.id
    cashouts = await cashout_manager.get_user_cashouts(user_id)
    
    if not cashouts:
        text = "📋 ИСТОРИЯ ВЫВОДОВ\n\nНет запросов на вывод"
        await callback.message.edit_text(text, reply_markup=get_back_keyboard())
        await callback.answer()
        return
    
    text = "📋 ИСТОРИЯ ВЫВОДОВ\n\n"
    
    # Показываем последние 10 запросов
    for cashout in cashouts[:10]:
        amount = cashout.get("amount", 0)
        status = cashout.get("status", "unknown")
        created_at = cashout.get("created_at", "")
        
        # Форматируем дату
        try:
            dt = datetime.fromisoformat(created_at)
            date_str = dt.strftime("%d.%m.%Y %H:%M")
        except:
            date_str = created_at
        
        # Статусы
        status_emoji = {
            "pending": "⏳",
            "processed": "✅",
            "cancelled": "❌"
        }
        emoji = status_emoji.get(status, "❓")
        
        status_text = {
            "pending": "Ожидает",
            "processed": "Выполнен",
            "cancelled": "Отменен"
        }
        
        text += f"{emoji} ${amount:.2f} - {status_text.get(status, status)}\n"
        text += f"   📅 {date_str}\n\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()


# ========== АДМИН ПАНЕЛЬ ==========

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    """Админ панель"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    text = (
        "⚙️ АДМИН ПАНЕЛЬ\n\n"
        "Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Управление банами", callback_data="admin_bans")],
        [InlineKeyboardButton(text="💸 Управление транзакциями", callback_data="admin_cashouts")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ========== УПРАВЛЕНИЕ БАНАМИ ==========

@dp.callback_query(F.data == "admin_bans")
async def admin_bans_menu(callback: CallbackQuery):
    """Меню управления банами"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    bans = await ban_manager.get_all_bans()
    
    text = "🚫 УПРАВЛЕНИЕ БАНАМИ\n\n"
    
    if not bans:
        text += "Список банов пуст"
    else:
        text += f"Всего забанено: {len(bans)}\n\n"
        for ban in bans[:10]:  # Показываем первые 10
            user_id_ban = ban.get('user_id')
            reason = ban.get('reason', 'Не указана')
            text += f"ID: {user_id_ban}\nПричина: {reason}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Забанить пользователя", callback_data="admin_ban_user")],
        [InlineKeyboardButton(text="✅ Разбанить пользователя", callback_data="admin_unban_user")],
        [InlineKeyboardButton(text="📋 Список банов", callback_data="admin_list_bans")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_ban_user")
async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса бана"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    text = (
        "🔨 ЗАБАНИТЬ ПОЛЬЗОВАТЕЛЯ\n\n"
        "Введите ID пользователя для бана:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await state.set_state(GameStates.admin_ban_user_id)
    await callback.answer()


@dp.message(GameStates.admin_ban_user_id)
async def admin_ban_user_id_handler(message: Message, state: FSMContext):
    """Обработка ID пользователя для бана"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен!")
        await state.clear()
        return
    
    try:
        target_user_id = int(message.text)
        
        # Проверяем, не админ ли это
        if is_admin(target_user_id):
            await message.answer("❌ Нельзя забанить администратора!")
            await state.clear()
            return
        
        # Проверяем, забанен ли уже
        if await ban_manager.is_banned(target_user_id):
            await message.answer("❌ Этот пользователь уже забанен!")
            await state.clear()
            return
        
        await state.update_data(target_user_id=target_user_id)
        
        text = (
            f"🔨 ЗАБАНИТЬ ПОЛЬЗОВАТЕЛЯ\n\n"
            f"ID: {target_user_id}\n\n"
            "Введите причину бана:"
        )
        
        await message.answer(text, reply_markup=get_back_keyboard())
        await state.set_state(GameStates.admin_ban_reason)
    
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")


@dp.message(GameStates.admin_ban_reason)
async def admin_ban_reason_handler(message: Message, state: FSMContext):
    """Обработка причины бана"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен!")
        await state.clear()
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    reason = message.text
    
    # Баним пользователя
    await ban_manager.ban_user(target_user_id, reason, message.from_user.id)
    
    # Уведомляем забаненного пользователя
    try:
        await bot.send_message(
            target_user_id,
            f"🚫 ВЫ ЗАБЛОКИРОВАНЫ\n\nПричина: {reason}"
        )
    except:
        pass
    
    await message.answer(
        f"✅ Пользователь {target_user_id} забанен!\nПричина: {reason}",
        reply_markup=get_back_keyboard()
    )
    
    await state.clear()
    logger.info(f"User {target_user_id} banned by admin {message.from_user.id}. Reason: {reason}")


@dp.callback_query(F.data == "admin_unban_user")
async def admin_unban_user_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса разбана"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    text = (
        "✅ РАЗБАНИТЬ ПОЛЬЗОВАТЕЛЯ\n\n"
        "Введите ID пользователя для разбана:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await state.set_state(GameStates.admin_unban_user_id)
    await callback.answer()


@dp.message(GameStates.admin_unban_user_id)
async def admin_unban_user_id_handler(message: Message, state: FSMContext):
    """Обработка ID пользователя для разбана"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен!")
        await state.clear()
        return
    
    try:
        target_user_id = int(message.text)
        
        # Разбаниваем
        if await ban_manager.unban_user(target_user_id):
            await message.answer(
                f"✅ Пользователь {target_user_id} разбанен!",
                reply_markup=get_back_keyboard()
            )
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    target_user_id,
                    "✅ ВЫ РАЗБЛОКИРОВАНЫ\n\nДобро пожаловать обратно!"
                )
            except:
                pass
            
            logger.info(f"User {target_user_id} unbanned by admin {message.from_user.id}")
        else:
            await message.answer("❌ Этот пользователь не забанен!")
        
        await state.clear()
    
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")


@dp.callback_query(F.data == "admin_list_bans")
async def admin_list_bans(callback: CallbackQuery):
    """Список всех банов"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    bans = await ban_manager.get_all_bans()
    
    if not bans:
        text = "🚫 СПИСОК БАНОВ\n\nСписок пуст"
    else:
        text = f"🚫 СПИСОК БАНОВ\n\nВсего: {len(bans)}\n\n"
        for ban in bans[:20]:  # Показываем последние 20
            user_id_ban = ban.get('user_id')
            reason = ban.get('reason', 'Не указана')
            banned_at = ban.get('banned_at', '')
            
            try:
                dt = datetime.fromisoformat(banned_at)
                date_str = dt.strftime("%d.%m.%Y %H:%M")
            except:
                date_str = banned_at
            
            text += f"ID: {user_id_ban}\nПричина: {reason}\nДата: {date_str}\n\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()


# ========== УПРАВЛЕНИЕ ТРАНЗАКЦИЯМИ ==========

@dp.callback_query(F.data == "admin_cashouts")
async def admin_cashouts_menu(callback: CallbackQuery):
    """Меню управления транзакциями"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    pending_cashouts = await cashout_manager.get_pending_cashouts()
    
    text = "💸 УПРАВЛЕНИЕ ТРАНЗАКЦИЯМИ\n\n"
    
    if not pending_cashouts:
        text += "⏳ Нет ожидающих транзакций"
    else:
        text += f"⏳ Ожидающих транзакций: {len(pending_cashouts)}\n\n"
        for cashout in pending_cashouts[:5]:
            cashout_id = cashout.get('cashout_id')
            user_id_target = cashout.get('user_id')
            username = cashout.get('username', 'Unknown')
            amount = cashout.get('amount', 0)
            text += f"💰 ${amount:.2f} | @{username} ({user_id_target})\n"
            text += f"   ID: {cashout_id}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Ожидающие", callback_data="admin_pending_cashouts")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == "admin_pending_cashouts")
async def admin_pending_cashouts_list(callback: CallbackQuery):
    """Список ожидающих транзакций"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    pending_cashouts = await cashout_manager.get_pending_cashouts()
    
    if not pending_cashouts:
        text = "⏳ Нет ожидающих транзакций"
        await callback.message.edit_text(text, reply_markup=get_back_keyboard())
        await callback.answer()
        return
    
    text = "⏳ ОЖИДАЮЩИЕ ТРАНЗАКЦИИ\n\n"
    
    keyboard_buttons = []
    
    for cashout in pending_cashouts[:10]:
        cashout_id = cashout.get('cashout_id')
        user_id_target = cashout.get('user_id')
        username = cashout.get('username', 'Unknown')
        amount = cashout.get('amount', 0)
        created_at = cashout.get('created_at', '')
        
        try:
            dt = datetime.fromisoformat(created_at)
            date_str = dt.strftime("%d.%m %H:%M")
        except:
            date_str = created_at
        
        text += f"💰 ${amount:.2f} | @{username}\n"
        text += f"   ID: {user_id_target} | {date_str}\n\n"
        
        # Кнопки для каждой транзакции
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"✅ Одобрить ${amount:.2f}",
                callback_data=f"admin_approve_{cashout_id}"
            ),
            InlineKeyboardButton(
                text=f"❌ Отклонить",
                callback_data=f"admin_reject_{cashout_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_cashouts")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_cashout(callback: CallbackQuery):
    """Одобрить транзакцию"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    # Извлекаем cashout_id из callback_data (все после "admin_approve_")
    cashout_id = callback.data.replace("admin_approve_", "", 1)
    
    logger.info(f"Admin {user_id} approving cashout {cashout_id}")
    
    # Обновляем статус
    if await cashout_manager.update_cashout_status(cashout_id, "processed"):
        await callback.answer("✅ Транзакция одобрена!", show_alert=True)
        
        # Получаем информацию о транзакции
        cashouts = await cashout_manager.load_cashouts()
        cashout = cashouts.get(cashout_id)
        
        if cashout:
            target_user_id = cashout.get('user_id')
            amount = cashout.get('amount', 0)
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    target_user_id,
                    f"✅ ВАШ ЗАПРОС НА ВЫВОД ОДОБРЕН!\n\n"
                    f"💰 Сумма: ${amount:.2f}\n\n"
                    f"Средства будут переведены в ближайшее время"
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_user_id}: {e}")
        
        # Обновляем список
        await admin_pending_cashouts_list(callback)
    else:
        await callback.answer("❌ Ошибка! Транзакция не найдена", show_alert=True)
        logger.error(f"Failed to approve cashout {cashout_id}")


@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_cashout(callback: CallbackQuery):
    """Отклонить транзакцию"""
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    # Извлекаем cashout_id из callback_data (все после "admin_reject_")
    cashout_id = callback.data.replace("admin_reject_", "", 1)
    
    logger.info(f"Admin {user_id} rejecting cashout {cashout_id}")
    
    # Получаем информацию о транзакции
    cashouts = await cashout_manager.load_cashouts()
    cashout = cashouts.get(cashout_id)
    
    if cashout:
        target_user_id = cashout.get('user_id')
        amount = cashout.get('amount', 0)
        
        # Возвращаем средства пользователю
        await db.update_balance(target_user_id, amount)
        
        # Обновляем статус
        if await cashout_manager.update_cashout_status(cashout_id, "cancelled"):
            await callback.answer("❌ Транзакция отклонена! Средства возвращены.", show_alert=True)
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    target_user_id,
                    f"❌ ВАШ ЗАПРОС НА ВЫВОД ОТКЛОНЕН\n\n"
                    f"💰 Сумма ${amount:.2f} возвращена на ваш баланс"
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_user_id}: {e}")
            
            # Обновляем список
            await admin_pending_cashouts_list(callback)
        else:
            await callback.answer("❌ Ошибка при обновлении статуса", show_alert=True)
    else:
        await callback.answer("❌ Транзакция не найдена!", show_alert=True)
        logger.error(f"Cashout {cashout_id} not found")


async def main():
    """Запуск бота"""
    logger.info("Starting multiplayer casino bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
