"""
Обработчик логики викторины (личный режим)
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.enums import ChatType

from keyboards import (
    get_answer_keyboard, 
    get_result_keyboard,
    get_explanation_keyboard,
    get_back_to_menu_keyboard
)
from questions_loader import questions_manager
from quiz_session import (
    session_manager, 
    format_question_text,
    format_answer_result,
    format_quiz_result,
    format_quiz_partial_result,
    format_explanation,
    format_all_explanations
)
from database import update_user_stats, get_setting
from config import TIME_PER_QUESTION, MIN_QUESTIONS

router = Router()


def is_private_chat(callback: CallbackQuery) -> bool:
    """Проверить, что это личный чат"""
    return callback.message.chat.type == ChatType.PRIVATE


async def get_time_per_question() -> int:
    """Получить текущее время на ответ из настроек"""
    setting = await get_setting("time_per_question")
    if setting:
        return int(setting)
    return TIME_PER_QUESTION


async def send_question(bot: Bot, chat_id: int, session):
    """Отправить вопрос пользователю"""
    question = session.current_question
    if not question:
        return
    
    time_limit = await get_time_per_question()
    
    text = format_question_text(
        question, 
        session.current_index + 1, 
        session.total_questions,
        time_limit,
        time_limit
    )
    
    # Отправляем вопрос
    msg = await bot.send_message(
        chat_id,
        text,
        reply_markup=get_answer_keyboard(session.current_index),
        parse_mode="Markdown"
    )
    session.message_id = msg.message_id
    
    # Запускаем таймер
    session.timer_task = asyncio.create_task(
        question_timer(bot, chat_id, session, time_limit)
    )


async def question_timer(bot: Bot, chat_id: int, session, total_time: int):
    """Таймер для вопроса с обновлением прогресс-бара"""
    question = session.current_question
    if not question:
        return
    
    remaining = total_time
    
    try:
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            
            # Проверяем, не ответили ли уже
            if session.is_answered:
                return
            
            # Обновляем сообщение с новым временем (не чаще чем раз в 2 секунды)
            if remaining > 0 and remaining % 2 == 0:
                try:
                    text = format_question_text(
                        question,
                        session.current_index + 1,
                        session.total_questions,
                        remaining,
                        total_time
                    )
                    await bot.edit_message_text(
                        text,
                        chat_id=chat_id,
                        message_id=session.message_id,
                        reply_markup=get_answer_keyboard(session.current_index),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass  # Игнорируем ошибки редактирования
        
        # Время вышло!
        if not session.is_answered:
            await handle_timeout(bot, chat_id, session)
            
    except asyncio.CancelledError:
        pass  # Таймер был отменён


async def handle_timeout(bot: Bot, chat_id: int, session):
    """Обработка истечения времени"""
    session.is_answered = True
    question = session.current_question
    
    # Записываем как неправильный ответ
    session.record_answer(None, False, time_expired=True)
    
    # Показываем правильный ответ
    text = format_answer_result(question, None, False, time_expired=True)
    
    try:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=session.message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    # Пауза перед следующим вопросом
    await asyncio.sleep(3)
    
    # Переход к следующему вопросу
    session.move_to_next()
    
    if session.is_finished:
        await finish_quiz(bot, chat_id, session)
    else:
        await send_question(bot, chat_id, session)


async def finish_quiz(bot: Bot, chat_id: int, session):
    """Завершение викторины"""
    # Сохраняем статистику в БД
    await update_user_stats(
        session.user_id, 
        session.total_questions, 
        session.correct_count
    )
    
    # Показываем результат
    text = format_quiz_result(session)
    
    await bot.send_message(
        chat_id,
        text,
        reply_markup=get_result_keyboard(),
        parse_mode="Markdown"
    )
    
    # НЕ удаляем сессию, чтобы сохранить данные для пояснений


@router.callback_query(F.data.startswith("count:"))
async def callback_start_quiz(callback: CallbackQuery):
    """Начало викторины после выбора количества вопросов (личный режим)"""
    # Этот обработчик только для личных чатов
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # В группе используется gcount:
    
    parts = callback.data.split(":")
    country = parts[1]
    region = parts[2]
    count = int(parts[3])
    
    # Проверяем минимальное количество вопросов
    if country == "all":
        available = questions_manager.get_questions_count()
    elif region == "all":
        available = questions_manager.get_questions_count(country=country)
    else:
        available = questions_manager.get_questions_count(country=country, region=region)
    
    if available < MIN_QUESTIONS:
        await callback.answer(
            f"❌ Недостаточно вопросов! Минимум {MIN_QUESTIONS}, доступно {available}.",
            show_alert=True
        )
        return
    
    # Получаем вопросы
    if country == "all":
        questions = questions_manager.get_random_questions(count)
    elif region == "all":
        questions = questions_manager.get_random_questions(count, country=country)
    else:
        questions = questions_manager.get_random_questions(count, country=country, region=region)
    
    if not questions:
        await callback.answer("❌ Не удалось загрузить вопросы!", show_alert=True)
        return
    
    # Создаём сессию
    session = session_manager.create_session(callback.from_user.id, questions)
    
    # Удаляем сообщение с выбором
    await callback.message.delete()
    
    # Отправляем первый вопрос
    await send_question(callback.bot, callback.message.chat.id, session)
    await callback.answer()


@router.callback_query(F.data.startswith("answer:"))
async def callback_answer(callback: CallbackQuery):
    """Обработка ответа на вопрос (личный режим)"""
    # Этот обработчик только для личных чатов
    if not is_private_chat(callback):
        await callback.answer()  # Отвечаем на колбэк, чтобы не было зависания
        return  # Пропускаем, пусть обработает group_quiz
    
    parts = callback.data.split(":")
    question_index = int(parts[1])
    answer = parts[2]
    
    user_id = callback.from_user.id
    session = session_manager.get_session(user_id)
    
    if not session:
        await callback.answer("❌ Сессия не найдена! Начните новую викторину.", show_alert=True)
        return
    
    # Проверяем, что отвечаем на текущий вопрос
    if session.current_index != question_index:
        await callback.answer("❌ Этот вопрос уже не активен!", show_alert=True)
        return
    
    # Проверяем, не отвечали ли уже
    if session.is_answered:
        await callback.answer("❌ Вы уже ответили на этот вопрос!", show_alert=True)
        return
    
    # Отмечаем, что ответили
    session.is_answered = True
    session.cancel_timer()
    
    question = session.current_question
    correct_answer = question.get('correct_answer', '')
    is_correct = answer == correct_answer
    
    # Записываем ответ
    session.record_answer(answer, is_correct)
    
    # Показываем результат
    text = format_answer_result(question, answer, is_correct)
    
    try:
        await callback.message.edit_text(text, parse_mode="Markdown")
    except Exception:
        pass
    
    await callback.answer("✅ Правильно!" if is_correct else "❌ Неправильно!")
    
    # Пауза перед следующим вопросом
    await asyncio.sleep(3)
    
    # Переход к следующему вопросу
    session.move_to_next()
    
    if session.is_finished:
        await finish_quiz(callback.bot, callback.message.chat.id, session)
    else:
        await send_question(callback.bot, callback.message.chat.id, session)


@router.message(Command("stop"))
async def cmd_stop_quiz(message: Message):
    """Остановить викторину (личный режим)"""
    if message.chat.type != ChatType.PRIVATE:
        return

    session = session_manager.get_session(message.from_user.id)
    if not session:
        await message.answer("⚠️ У вас нет активной викторины.")
        return

    session.cancel_timer()
    session.current_index = len(session.questions)
    session.is_answered = True

    # Сохраняем статистику по отвеченным вопросам
    answered = len(session.answers)
    await update_user_stats(message.from_user.id, answered, session.correct_count)

    text = format_quiz_partial_result(session)
    await message.answer(text, reply_markup=get_result_keyboard(), parse_mode="Markdown")


@router.callback_query(F.data == "stop_quiz")
async def callback_stop_quiz(callback: CallbackQuery):
    """Остановить викторину кнопкой (личный режим)"""
    if not is_private_chat(callback):
        await callback.answer()
        return

    session = session_manager.get_session(callback.from_user.id)
    if not session:
        await callback.answer("⚠️ Викторина не найдена!", show_alert=True)
        return

    session.cancel_timer()
    session.current_index = len(session.questions)
    session.is_answered = True

    answered = len(session.answers)
    await update_user_stats(callback.from_user.id, answered, session.correct_count)

    text = format_quiz_partial_result(session)
    await callback.message.edit_text(text, reply_markup=get_result_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "show_explanations")
async def callback_show_explanations(callback: CallbackQuery):
    """Показать пояснения к вопросам (первый вопрос)"""
    session = session_manager.get_session(callback.from_user.id)
    
    if not session or not session.answers:
        await callback.answer("❌ Нет данных для отображения!", show_alert=True)
        return
    
    # Показываем пояснение к первому вопросу
    text = format_explanation(session.answers[0], 0)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_explanation_keyboard(0, len(session.answers)),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("explanation:"))
async def callback_explanation(callback: CallbackQuery):
    """Показать пояснение к конкретному вопросу"""
    index = int(callback.data.split(":")[1])
    session = session_manager.get_session(callback.from_user.id)
    
    if not session or index >= len(session.answers):
        await callback.answer("❌ Данные не найдены!", show_alert=True)
        return
    
    text = format_explanation(session.answers[index], index)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_explanation_keyboard(index, len(session.answers)),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "all_explanations")
async def callback_all_explanations(callback: CallbackQuery):
    """Показать все пояснения списком"""
    session = session_manager.get_session(callback.from_user.id)
    
    if not session or not session.answers:
        await callback.answer("❌ Нет данных для отображения!", show_alert=True)
        return
    
    text = format_all_explanations(session)
    
    # Telegram имеет лимит на длину сообщения (4096 символов)
    if len(text) > 4000:
        text = text[:3997] + "..."
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
