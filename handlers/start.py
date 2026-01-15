"""
Обработчик команды /start и выбора страны/региона
"""
import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.enums import ChatType

from keyboards import (
    get_countries_keyboard, 
    get_regions_keyboard, 
    get_question_count_keyboard,
    get_main_menu_keyboard
)
from questions_loader import questions_manager
from database import get_or_create_user, get_user_stats
from config import COUNTRIES, DEV_PHOTO_PATH, DEV_INFO_TEXT

router = Router()
logger = logging.getLogger(__name__)


def is_private_chat(message_or_callback) -> bool:
    """Проверить, что это личный чат"""
    if isinstance(message_or_callback, Message):
        return message_or_callback.chat.type == ChatType.PRIVATE
    else:
        return message_or_callback.message.chat.type == ChatType.PRIVATE


# Сообщение при отсутствии username
NO_USERNAME_MESSAGE = """
🎉 Привет! 

Чтобы окунуться в мир вина с нами, тебе нужно установить username в настройках Telegram. Это займёт минуту!

📱 *Как это сделать:*
1. Перейди в «Настройки» Telegram
2. Нажми на свой профиль
3. Установи имя пользователя (username)

Как только сделаешь — пиши /start снова! 🍷
"""

# Приветственное сообщение
WELCOME_MESSAGE = """
🎉 *Добро пожаловать в Wine Quiz!*

Проверь свои знания о винах разных стран и регионов!

🍷 *ВЫБЕРИ СТРАНУ ДЛЯ ВИКТОРИНЫ:*
"""


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Проверяем наличие username
    if not user.username and message.chat.type == ChatType.PRIVATE:
        await message.answer(
            NO_USERNAME_MESSAGE,
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем/обновляем пользователя в БД
    await get_or_create_user(user.id, user.username, user.first_name)
    
    # Показываем главное меню с кнопками
    await message.answer(
        "🍷 Привет! Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )
    
    # Показываем меню выбора страны
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Команда /menu - обновить кнопки меню"""
    await message.answer(
        "✅ Меню обновлено.",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(F.text == "🍷 Начать викторину")
async def btn_start_quiz(message: Message):
    """Кнопка начать викторину"""
    user = message.from_user
    
    # Сохраняем/обновляем пользователя в БД
    await get_or_create_user(user.id, user.username, user.first_name)
    
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.text == "📊 Моя статистика")
async def btn_my_stats(message: Message):
    """Кнопка моя статистика"""
    user = message.from_user
    
    # Получаем статистику пользователя
    stats = await get_user_stats(user.id)
    
    if not stats or stats['total_questions'] == 0:
        await message.answer(
            "📊 У тебя пока нет статистики.\n\n"
            "Пройди хотя бы одну викторину! 🍷"
        )
        return
    
    success_rate = stats.get('success_rate', 0)
    total = stats.get('total_questions', 0)
    correct = stats.get('correct_answers', 0)
    quizzes = stats.get('quizzes_completed', 0)
    
    text = f"📊 Твоя статистика:\n\n"
    text += f"✅ Правильных ответов: {success_rate}% ({total} вопросов)\n"
    text += f"🎯 Верных ответов: {correct} из {total}\n"
    text += f"🏆 Викторин пройдено: {quizzes}"
    
    await message.answer(text)


@router.message(F.text == "💬 Обратная связь")
@router.message(F.text == "👨‍💻 Разработчик")
async def btn_developer_info(message: Message):
    """Кнопка информация о разработчике"""
    photo_path = DEV_PHOTO_PATH
    data_dir = os.path.dirname(DEV_PHOTO_PATH)
    if not os.path.exists(photo_path):
        candidates = [
            os.path.join(data_dir, "developer.jpg"),
            os.path.join(data_dir, "developer.jpeg"),
            os.path.join(data_dir, "developer.png"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                photo_path = candidate
                break
        else:
            try:
                for name in os.listdir(data_dir):
                    if name.lower().startswith("developer."):
                        photo_path = os.path.join(data_dir, name)
                        break
            except Exception:
                photo_path = DEV_PHOTO_PATH

    try:
        logger.info(f"[DEV] Sending developer info to chat {message.chat.id}")
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo, caption=DEV_INFO_TEXT, parse_mode=None)
    except Exception as e:
        logger.warning(f"[DEV] Failed to send photo, fallback to text: {e}")
        await message.answer(DEV_INFO_TEXT, parse_mode=None)


@router.message(F.text == "👥 Multiplayer")
async def btn_multiplayer_info(message: Message):
    """Кнопка информации о мультиплеере"""
    text = (
        "Для игры в режиме мультиплеер добавьте бота в групповой чат "
        "и нажмите /start. После этого выберите «Начать викторину» в меню."
    )
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats - статистика пользователя"""
    await btn_my_stats(message)


@router.callback_query(F.data == "new_quiz")
async def callback_new_quiz(callback: CallbackQuery):
    """Начать новую викторину (личный режим)"""
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # В группе используется gnew_quiz
    await callback.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("country:"))
async def callback_country_selected(callback: CallbackQuery):
    """Обработка выбора страны (личный режим)"""
    # Этот обработчик только для личных чатов
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # В группе используется gcountry:
    
    country_code = callback.data.split(":")[1]
    
    if country_code == "all":
        # Рандом по всем странам - сразу к выбору количества
        available = questions_manager.get_questions_count()
        
        if available == 0:
            await callback.answer("❌ Нет доступных вопросов!", show_alert=True)
            return
        
        text = "🌍 *Викторина по всем странам*\n\n"
        text += f"📊 Доступно вопросов: {available}\n\n"
        text += "Выбери количество вопросов:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_question_count_keyboard("all", "all", available),
            parse_mode="Markdown"
        )
    else:
        # Конкретная страна - показываем регионы
        if country_code not in COUNTRIES:
            await callback.answer("❌ Страна не найдена!", show_alert=True)
            return
        
        country_data = COUNTRIES[country_code]
        available = questions_manager.get_questions_count(country=country_code)
        
        text = f"{country_data['flag']} *Выберите вариант для {country_data['name'].replace(country_data['flag'], '').strip()}:*\n\n"
        text += f"📊 Всего вопросов по стране: {available}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_regions_keyboard(country_code),
            parse_mode="Markdown"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("region:"))
async def callback_region_selected(callback: CallbackQuery):
    """Обработка выбора региона (личный режим)"""
    # Этот обработчик только для личных чатов
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # В группе используется gregion:
    
    parts = callback.data.split(":")
    country_code = parts[1]
    region_code = parts[2]
    
    # Определяем количество доступных вопросов
    if region_code == "all":
        available = questions_manager.get_questions_count(country=country_code)
        region_name = "всей стране"
    else:
        available = questions_manager.get_questions_count(country=country_code, region=region_code)
        region_data = COUNTRIES.get(country_code, {}).get("regions", {}).get(region_code, {})
        region_name = region_data.get("name", region_code)
    
    if available == 0:
        await callback.answer("❌ Нет доступных вопросов для этого региона!", show_alert=True)
        return
    
    text = f"📊 *Выбор количества вопросов*\n\n"
    text += f"📍 Регион: {region_name}\n"
    text += f"📚 Доступно вопросов: {available}\n\n"
    text += "⚠️ _Если выбрано больше, чем есть — будут использованы все доступные._\n\n"
    text += "Выбери количество вопросов:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_question_count_keyboard(country_code, region_code, available),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "back:countries")
async def callback_back_to_countries(callback: CallbackQuery):
    """Возврат к выбору страны (личный режим)"""
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # В группе используется gback:countries
    await callback.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back:region:"))
async def callback_back_to_regions(callback: CallbackQuery):
    """Возврат к выбору региона (личный режим)"""
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # В группе используется gback:region:
    
    country_code = callback.data.split(":")[2]
    
    if country_code not in COUNTRIES:
        await callback.answer("❌ Страна не найдена!", show_alert=True)
        return
    
    country_data = COUNTRIES[country_code]
    available = questions_manager.get_questions_count(country=country_code)
    
    text = f"{country_data['flag']} *Выберите вариант для {country_data['name'].replace(country_data['flag'], '').strip()}:*\n\n"
    text += f"📊 Всего вопросов по стране: {available}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_regions_keyboard(country_code),
        parse_mode="Markdown"
    )
    await callback.answer()
