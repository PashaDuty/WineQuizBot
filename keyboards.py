"""
Клавиатуры и меню для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import COUNTRIES, QUESTION_COUNTS


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню с постоянными кнопками"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🍷 Начать викторину"),
        KeyboardButton(text="📊 Моя статистика")
    )
    return builder.as_markup(resize_keyboard=True)


def get_countries_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора страны"""
    builder = InlineKeyboardBuilder()
    
    # Кнопки стран
    for country_code, country_data in COUNTRIES.items():
        builder.row(InlineKeyboardButton(
            text=country_data["name"],
            callback_data=f"country:{country_code}"
        ))
    
    # Кнопка "Рандом по всем странам"
    builder.row(InlineKeyboardButton(
        text="🌍 Рандом по всем странам",
        callback_data="country:all"
    ))
    
    return builder.as_markup()


def get_regions_keyboard(country_code: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора региона для страны"""
    builder = InlineKeyboardBuilder()
    
    if country_code not in COUNTRIES:
        return builder.as_markup()
    
    country_data = COUNTRIES[country_code]
    
    # Кнопки регионов
    for region_code, region_data in country_data["regions"].items():
        builder.row(InlineKeyboardButton(
            text=region_data["name"],
            callback_data=f"region:{country_code}:{region_code}"
        ))
    
    # Кнопка "Случайно по всей стране"
    builder.row(InlineKeyboardButton(
        text=country_data["random_label"],
        callback_data=f"region:{country_code}:all"
    ))
    
    # Кнопка "Назад"
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к выбору страны",
        callback_data="back:countries"
    ))
    
    return builder.as_markup()


def get_question_count_keyboard(country: str, region: str, available_count: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора количества вопросов"""
    builder = InlineKeyboardBuilder()
    
    for count in QUESTION_COUNTS:
        # Показываем реальное количество, если вопросов меньше
        label = f"{count} вопросов"
        if available_count < count:
            label = f"{count} вопросов (доступно {available_count})"
        
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"count:{country}:{region}:{count}"
        ))
    
    # Кнопка "Назад"
    back_callback = f"back:region:{country}" if region != "all" else "back:countries"
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=back_callback
    ))
    
    return builder.as_markup()


def get_answer_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с вариантами ответа"""
    builder = InlineKeyboardBuilder()
    
    # Варианты ответов в две колонки
    builder.row(
        InlineKeyboardButton(text="a", callback_data=f"answer:{question_id}:a"),
        InlineKeyboardButton(text="b", callback_data=f"answer:{question_id}:b")
    )
    builder.row(
        InlineKeyboardButton(text="c", callback_data=f"answer:{question_id}:c"),
        InlineKeyboardButton(text="d", callback_data=f"answer:{question_id}:d")
    )
    
    return builder.as_markup()


def get_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после завершения викторины"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="📖 ПОСМОТРЕТЬ ПОЯСНЕНИЯ КО ВСЕМ ВОПРОСАМ",
        callback_data="show_explanations"
    ))
    
    builder.row(InlineKeyboardButton(
        text="🔄 Начать новую викторину",
        callback_data="new_quiz"
    ))
    
    return builder.as_markup()


def get_explanation_keyboard(question_index: int, total_questions: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра пояснений"""
    builder = InlineKeyboardBuilder()
    
    buttons = []
    
    # Кнопка "Назад" если не первый вопрос
    if question_index > 0:
        buttons.append(InlineKeyboardButton(
            text="⬅️ Пред.",
            callback_data=f"explanation:{question_index - 1}"
        ))
    
    # Кнопка "Вперёд" если не последний вопрос
    if question_index < total_questions - 1:
        buttons.append(InlineKeyboardButton(
            text="След. ➡️",
            callback_data=f"explanation:{question_index + 1}"
        ))
    
    if buttons:
        builder.row(*buttons)
    
    # Кнопка "Все пояснения списком"
    builder.row(InlineKeyboardButton(
        text="📋 Все пояснения списком",
        callback_data="all_explanations"
    ))
    
    # Кнопка "Новая викторина"
    builder.row(InlineKeyboardButton(
        text="🔄 Начать новую викторину",
        callback_data="new_quiz"
    ))
    
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="🔄 Начать новую викторину",
        callback_data="new_quiz"
    ))
    
    return builder.as_markup()


# ============ АДМИН КЛАВИАТУРЫ ============

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="📊 ПОКАЗАТЬ СТАТИСТИКУ",
        callback_data="admin:stats"
    ))
    
    builder.row(InlineKeyboardButton(
        text="⚙️ ИЗМЕНИТЬ ВРЕМЯ НА ОТВЕТ",
        callback_data="admin:time"
    ))
    
    builder.row(InlineKeyboardButton(
        text="🔄 ПЕРЕЗАГРУЗИТЬ ВОПРОСЫ",
        callback_data="admin:reload"
    ))
    
    builder.row(InlineKeyboardButton(
        text="📥 ВЫГРУЗИТЬ СТАТИСТИКУ В CSV",
        callback_data="admin:export"
    ))
    
    return builder.as_markup()


def get_time_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора времени на ответ"""
    builder = InlineKeyboardBuilder()
    
    time_options = [5, 10, 15, 20, 30]
    
    for seconds in time_options:
        builder.row(InlineKeyboardButton(
            text=f"⏱ {seconds} секунд",
            callback_data=f"admin:settime:{seconds}"
        ))
    
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад в админ-панель",
        callback_data="admin:back"
    ))
    
    return builder.as_markup()


def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата в админ-панель"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад в админ-панель",
        callback_data="admin:back"
    ))
    
    return builder.as_markup()
