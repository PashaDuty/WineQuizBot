"""
Обработчик админ-панели
"""
import io
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command

from keyboards import (
    get_admin_keyboard, 
    get_time_settings_keyboard,
    get_admin_back_keyboard
)
from database import (
    get_top_users, 
    get_total_stats, 
    export_users_csv,
    set_setting,
    get_setting
)
from questions_loader import questions_manager
from config import ADMIN_ID, TIME_PER_QUESTION

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id == ADMIN_ID


def escape_markdown(text: str) -> str:
    """Экранирование специальных символов Markdown"""
    if not text:
        return text
    chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    return text


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Обработчик команды /admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        "⚙️ *ПАНЕЛЬ АДМИНИСТРАТОРА:*",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:back")
async def callback_admin_back(callback: CallbackQuery):
    """Возврат в админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "⚙️ *ПАНЕЛЬ АДМИНИСТРАТОРА:*",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    total_users, total_answers = await get_total_stats()
    top_users = await get_top_users(10)
    
    lines = []
    lines.append("📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ:")
    lines.append("")
    lines.append(f"👥 Всего пользователей: {total_users}")
    lines.append(f"📝 Всего ответов: {total_answers}")
    lines.append("")
    
    if top_users:
        lines.append("🏆 ТОП-10:")
        for i, user in enumerate(top_users, 1):
            username = user.get('username', '')
            first_name = user.get('first_name', 'Без имени')
            
            if username:
                display_name = f"@{username}"
            else:
                display_name = first_name
            
            success_rate = user.get('success_rate', 0)
            total = user.get('total_questions', 0)
            
            lines.append(f"{i}. {display_name} — {success_rate}% ({total} вопр.)")
    else:
        lines.append("Пока нет данных о пользователях")
    
    text = "\n".join(lines)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard(),
        parse_mode=None  # Отключаем Markdown чтобы _ не ломал форматирование
    )
    await callback.answer()


@router.callback_query(F.data == "admin:time")
async def callback_admin_time(callback: CallbackQuery):
    """Настройка времени на ответ"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    current_time = await get_setting("time_per_question")
    if not current_time:
        current_time = TIME_PER_QUESTION
    else:
        current_time = int(current_time)
    
    text = f"⏱ НАСТРОЙКА ВРЕМЕНИ НА ОТВЕТ\n\n"
    text += f"Текущее значение: {current_time} секунд\n\n"
    text += "Выберите новое значение:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_time_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:settime:"))
async def callback_admin_set_time(callback: CallbackQuery):
    """Установить время на ответ"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    new_time = int(callback.data.split(":")[2])
    await set_setting("time_per_question", str(new_time))
    
    await callback.answer(f"✅ Время на ответ установлено: {new_time} секунд", show_alert=True)
    
    # Возвращаемся в админ-панель
    await callback.message.edit_text(
        "⚙️ *ПАНЕЛЬ АДМИНИСТРАТОРА:*",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:reload")
async def callback_admin_reload(callback: CallbackQuery):
    """Перезагрузить вопросы"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.answer("🔄 Загрузка вопросов...")
    
    # Перезагружаем вопросы
    await questions_manager.load_all_questions()
    
    # Собираем статистику
    countries = questions_manager.get_available_countries()
    total = sum(countries.values())
    
    text = "✅ Вопросы успешно перезагружены!\n\n"
    text += f"📚 Всего загружено: {total} вопросов\n\n"
    
    for country_code, count in countries.items():
        from config import COUNTRIES
        country_name = COUNTRIES.get(country_code, {}).get("name", country_code)
        text += f"• {country_name}: {count} вопросов\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_back_keyboard()
    )


@router.callback_query(F.data == "admin:export")
async def callback_admin_export(callback: CallbackQuery):
    """Экспорт статистики в CSV"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.answer("📥 Формирование файла...")
    
    # Генерируем CSV
    csv_data = await export_users_csv()
    
    # Добавляем BOM для корректного открытия в Excel
    csv_bytes = b'\xef\xbb\xbf' + csv_data.encode('utf-8')
    
    # Создаём файл
    file = BufferedInputFile(
        csv_bytes,
        filename="wine_quiz_stats.csv"
    )
    
    # Отправляем файл
    await callback.message.answer_document(
        file,
        caption="📊 Статистика пользователей Wine Quiz\n\nОткройте файл в Excel или Google Sheets"
    )
    
    # Обновляем сообщение с кнопкой назад
    await callback.message.edit_text(
        "✅ Файл отправлен!",
        reply_markup=get_admin_back_keyboard()
    )
