"""
Обработчик команды /start и выбора страны/региона
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import (
    get_countries_keyboard, 
    get_regions_keyboard, 
    get_question_count_keyboard
)
from questions_loader import questions_manager
from database import get_or_create_user
from config import COUNTRIES

router = Router()


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
    if not user.username:
        await message.answer(
            NO_USERNAME_MESSAGE,
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем/обновляем пользователя в БД
    await get_or_create_user(user.id, user.username, user.first_name)
    
    # Показываем меню выбора страны
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "new_quiz")
async def callback_new_quiz(callback: CallbackQuery):
    """Начать новую викторину"""
    await callback.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("country:"))
async def callback_country_selected(callback: CallbackQuery):
    """Обработка выбора страны"""
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
    """Обработка выбора региона"""
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
    """Возврат к выбору страны"""
    await callback.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=get_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("back:region:"))
async def callback_back_to_regions(callback: CallbackQuery):
    """Возврат к выбору региона"""
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
