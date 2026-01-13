"""
Обработчик групповой викторины
"""
import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.enums import ChatType

logger = logging.getLogger(__name__)

from keyboards import (
    get_group_answer_keyboard,
    get_group_result_keyboard,
    get_group_explanation_keyboard,
    get_group_start_keyboard,
    get_group_join_keyboard,
    get_group_countries_keyboard,
    get_group_regions_keyboard,
    get_group_question_count_keyboard
)
from questions_loader import questions_manager
from group_quiz_session import (
    group_session_manager,
    format_group_question,
    format_group_answer_result,
    format_group_quiz_result,
    format_group_explanation,
    format_group_all_explanations,
    format_group_leaderboard
)
from database import get_setting, save_group_game, update_user_stats, get_or_create_user
from config import TIME_PER_QUESTION, MIN_QUESTIONS, COUNTRIES

router = Router()

# Время ожидания присоединения участников (секунды)
JOIN_TIMEOUT = 30

# Минимум участников для старта
MIN_PARTICIPANTS = 1


async def get_time_per_question() -> int:
    """Получить текущее время на ответ из настроек"""
    setting = await get_setting("time_per_question")
    if setting:
        return int(setting)
    return TIME_PER_QUESTION


def is_group_chat(message: Message) -> bool:
    """Проверить, что сообщение из группового чата"""
    return message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]


# ============ КОМАНДЫ ДЛЯ ГРУППЫ ============

@router.message(Command("quiz"))
async def cmd_group_quiz(message: Message):
    """Начать групповую викторину командой /quiz"""
    if not is_group_chat(message):
        await message.answer(
            "⚠️ Эта команда работает только в групповых чатах!\n\n"
            "Добавьте меня в группу и напишите /quiz"
        )
        return
    
    # Проверяем, нет ли уже активной сессии
    if group_session_manager.has_active_session(message.chat.id):
        await message.answer("⚠️ В этом чате уже идёт викторина!")
        return
    
    await message.answer(
        "🍷 *Групповая викторина Wine Quiz!*\n\n"
        "Выберите страну для викторины:",
        reply_markup=get_group_countries_keyboard(),
        parse_mode="Markdown"
    )


@router.message(Command("stop_quiz"))
async def cmd_stop_quiz(message: Message):
    """Остановить текущую викторину"""
    if not is_group_chat(message):
        return
    
    session = group_session_manager.get_session(message.chat.id)
    if not session:
        await message.answer("⚠️ В этом чате нет активной викторины.")
        return
    
    # Только тот, кто начал, или админ может остановить
    # Для простоты разрешаем любому участнику
    group_session_manager.end_session(message.chat.id)
    await message.answer("🛑 Викторина остановлена.")


@router.message(Command("score"))
async def cmd_score(message: Message):
    """Показать текущий счёт"""
    if not is_group_chat(message):
        return
    
    session = group_session_manager.get_session(message.chat.id)
    if not session:
        await message.answer("⚠️ В этом чате нет активной викторины.")
        return
    
    text = format_group_leaderboard(session, is_final=False)
    await message.answer(text, parse_mode="Markdown")


# ============ ВЫБОР СТРАНЫ/РЕГИОНА ДЛЯ ГРУППЫ ============

@router.callback_query(F.data.startswith("gcountry:"))
async def callback_group_country(callback: CallbackQuery):
    """Выбор страны для групповой викторины"""
    if not is_group_chat(callback.message):
        await callback.answer("Только для групповых чатов!", show_alert=True)
        return
    
    country_code = callback.data.split(":")[1]
    
    if country_code == "all":
        # Рандом по всем странам
        available = questions_manager.get_questions_count()
        
        if available == 0:
            await callback.answer("❌ Нет доступных вопросов!", show_alert=True)
            return
        
        text = "🌍 *Викторина по всем странам*\n\n"
        text += f"📊 Доступно вопросов: {available}\n\n"
        text += "Выбери количество вопросов:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_group_question_count_keyboard("all", "all", available),
            parse_mode="Markdown"
        )
    else:
        # Конкретная страна
        if country_code not in COUNTRIES:
            await callback.answer("❌ Страна не найдена!", show_alert=True)
            return
        
        country_data = COUNTRIES[country_code]
        available = questions_manager.get_questions_count(country=country_code)
        
        text = f"{country_data['flag']} *Выберите регион для {country_data['name'].replace(country_data['flag'], '').strip()}:*\n\n"
        text += f"📊 Всего вопросов по стране: {available}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_group_regions_keyboard(country_code),
            parse_mode="Markdown"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("gregion:"))
async def callback_group_region(callback: CallbackQuery):
    """Выбор региона для групповой викторины"""
    parts = callback.data.split(":")
    country_code = parts[1]
    region_code = parts[2]
    
    if region_code == "all":
        available = questions_manager.get_questions_count(country=country_code)
        region_name = "всей стране"
    else:
        available = questions_manager.get_questions_count(country=country_code, region=region_code)
        region_data = COUNTRIES.get(country_code, {}).get("regions", {}).get(region_code, {})
        region_name = region_data.get("name", region_code)
    
    if available == 0:
        await callback.answer("❌ Нет доступных вопросов!", show_alert=True)
        return
    
    text = f"📊 *Групповая викторина*\n\n"
    text += f"📍 Регион: {region_name}\n"
    text += f"📚 Доступно вопросов: {available}\n\n"
    text += "Выбери количество вопросов:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_question_count_keyboard(country_code, region_code, available),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "gback:countries")
async def callback_group_back_countries(callback: CallbackQuery):
    """Вернуться к выбору страны"""
    await callback.message.edit_text(
        "🍷 *Групповая викторина Wine Quiz!*\n\n"
        "Выберите страну для викторины:",
        reply_markup=get_group_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gback:region:"))
async def callback_group_back_region(callback: CallbackQuery):
    """Вернуться к выбору региона"""
    country_code = callback.data.split(":")[2]
    
    if country_code not in COUNTRIES:
        await callback.answer("❌ Страна не найдена!", show_alert=True)
        return
    
    country_data = COUNTRIES[country_code]
    available = questions_manager.get_questions_count(country=country_code)
    
    text = f"{country_data['flag']} *Выберите регион для {country_data['name'].replace(country_data['flag'], '').strip()}:*\n\n"
    text += f"📊 Всего вопросов по стране: {available}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_regions_keyboard(country_code),
        parse_mode="Markdown"
    )
    await callback.answer()


# ============ СТАРТ ИГРЫ И ПРИСОЕДИНЕНИЕ ============

@router.callback_query(F.data.startswith("gcount:"))
async def callback_group_start(callback: CallbackQuery):
    """Начать набор участников после выбора количества вопросов"""
    parts = callback.data.split(":")
    country = parts[1]
    region = parts[2]
    count = int(parts[3])
    
    # Проверяем доступность вопросов
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
    session = group_session_manager.create_session(
        callback.message.chat.id, 
        questions,
        callback.from_user.id
    )
    
    # Добавляем инициатора как первого участника
    session.add_participant(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    # Показываем экран ожидания участников
    await callback.message.edit_text(
        f"🍷 *Групповая викторина начинается!*\n\n"
        f"📊 Вопросов: {len(questions)}\n"
        f"⏱ Ожидание участников: {JOIN_TIMEOUT} сек\n\n"
        f"👥 *Участники ({session.participants_count}):*\n"
        f"• {session.participants[callback.from_user.id].display_name}\n\n"
        f"_Нажмите кнопку ниже, чтобы присоединиться!_",
        reply_markup=get_group_join_keyboard(),
        parse_mode="Markdown"
    )
    
    await callback.answer("Вы присоединились к викторине!")
    
    # Запускаем таймер ожидания
    session.timer_task = asyncio.create_task(
        join_timer(callback.bot, callback.message.chat.id, callback.message.message_id, session)
    )


async def join_timer(bot: Bot, chat_id: int, message_id: int, session):
    """Таймер ожидания участников"""
    try:
        remaining = JOIN_TIMEOUT
        
        while remaining > 0:
            await asyncio.sleep(5)
            remaining -= 5
            
            # Проверяем, не была ли игра уже запущена
            if session.is_question_active or session.current_index > 0:
                logger.info(f"[GROUP] Join timer: game already started, exiting")
                return
            
            # Обновляем сообщение каждые 5 секунд
            participants_list = "\n".join([
                f"• {p.display_name}" for p in session.participants.values()
            ])
            
            try:
                await bot.edit_message_text(
                    f"🍷 *Групповая викторина начинается!*\n\n"
                    f"📊 Вопросов: {session.total_questions}\n"
                    f"⏱ Осталось: {remaining} сек\n\n"
                    f"👥 *Участники ({session.participants_count}):*\n"
                    f"{participants_list}\n\n"
                    f"_Нажмите кнопку ниже, чтобы присоединиться!_",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=get_group_join_keyboard(),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        
        # Проверяем ещё раз перед стартом
        if session.is_question_active or session.current_index > 0:
            logger.info(f"[GROUP] Join timer: game already started before auto-start")
            return
        
        # Время вышло - начинаем игру
        logger.info(f"[GROUP] Join timer finished, participants: {session.participants_count}")
        if session.participants_count >= MIN_PARTICIPANTS:
            await start_group_quiz(bot, chat_id, session)
        else:
            group_session_manager.end_session(chat_id)
            await bot.send_message(
                chat_id,
                f"⚠️ Недостаточно участников для начала викторины.\n"
                f"Минимум: {MIN_PARTICIPANTS}, присоединилось: {session.participants_count}"
            )
    
    except asyncio.CancelledError:
        logger.info(f"[GROUP] Join timer cancelled for chat {chat_id}")


@router.callback_query(F.data == "gjoin")
async def callback_join_quiz(callback: CallbackQuery):
    """Присоединиться к викторине"""
    session = group_session_manager.get_session(callback.message.chat.id)
    
    if not session:
        await callback.answer("❌ Викторина не найдена!", show_alert=True)
        return
    
    if session.is_question_active:
        await callback.answer("❌ Викторина уже началась!", show_alert=True)
        return
    
    # Добавляем участника
    participant = session.add_participant(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name
    )
    
    # Обновляем список участников
    participants_list = "\n".join([
        f"• {p.display_name}" for p in session.participants.values()
    ])
    
    try:
        await callback.message.edit_text(
            f"🍷 *Групповая викторина начинается!*\n\n"
            f"📊 Вопросов: {session.total_questions}\n"
            f"⏱ Ожидание участников...\n\n"
            f"👥 *Участники ({session.participants_count}):*\n"
            f"{participants_list}\n\n"
            f"_Нажмите кнопку ниже, чтобы присоединиться!_",
            reply_markup=get_group_join_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    await callback.answer(f"✅ {participant.display_name} присоединился!")


@router.callback_query(F.data == "gstart_now")
async def callback_start_now(callback: CallbackQuery):
    """Начать викторину немедленно"""
    session = group_session_manager.get_session(callback.message.chat.id)
    
    if not session:
        await callback.answer("❌ Викторина не найдена!", show_alert=True)
        return
    
    # Только инициатор может начать раньше
    if callback.from_user.id != session.started_by:
        await callback.answer("❌ Только организатор может начать раньше!", show_alert=True)
        return
    
    if session.participants_count < MIN_PARTICIPANTS:
        await callback.answer(
            f"❌ Минимум {MIN_PARTICIPANTS} участник(ов) для старта!",
            show_alert=True
        )
        return
    
    # Отменяем таймер ожидания
    session.cancel_timer()
    
    await callback.answer("🚀 Начинаем!")
    await start_group_quiz(callback.bot, callback.message.chat.id, session)


# ============ ИГРОВОЙ ПРОЦЕСС ============

async def start_group_quiz(bot: Bot, chat_id: int, session):
    """Начать групповую викторину"""
    logger.info(f"[GROUP] Starting quiz in chat {chat_id} with {session.participants_count} participants")
    
    participants_list = ", ".join([p.display_name for p in session.participants.values()])
    
    await bot.send_message(
        chat_id,
        f"🎮 *ВИКТОРИНА НАЧИНАЕТСЯ!*\n\n"
        f"👥 Участники: {participants_list}\n"
        f"📊 Вопросов: {session.total_questions}\n\n"
        f"_Первый вопрос через 3 секунды..._",
        parse_mode="Markdown"
    )
    
    await asyncio.sleep(3)
    await send_group_question(bot, chat_id, session)


async def send_group_question(bot: Bot, chat_id: int, session):
    """Отправить вопрос группе"""
    question = session.current_question
    if not question:
        return
    
    session.start_question()
    time_limit = await get_time_per_question()
    
    logger.info(f"[GROUP] Sending question {session.current_index + 1}/{session.total_questions} to chat {chat_id}, time_limit={time_limit}s")
    
    text = format_group_question(
        question,
        session.current_index + 1,
        session.total_questions,
        time_limit,
        time_limit,
        0,
        session.participants_count
    )
    
    msg = await bot.send_message(
        chat_id,
        text,
        reply_markup=get_group_answer_keyboard(session.current_index),
        parse_mode="Markdown"
    )
    session.message_id = msg.message_id
    
    # Запускаем таймер
    session.timer_task = asyncio.create_task(
        group_question_timer(bot, chat_id, session, time_limit)
    )


async def group_question_timer(bot: Bot, chat_id: int, session, total_time: int):
    """Таймер для вопроса в групповой игре"""
    question = session.current_question
    if not question:
        return
    
    remaining = total_time
    
    try:
        while remaining > 0:
            await asyncio.sleep(1)
            remaining -= 1
            
            # Проверяем, все ли ответили
            if session.all_answered():
                break
            
            # Обновляем сообщение каждые 2 секунды
            if remaining > 0 and remaining % 2 == 0:
                try:
                    text = format_group_question(
                        question,
                        session.current_index + 1,
                        session.total_questions,
                        remaining,
                        total_time,
                        len(session.answered_users),
                        session.participants_count
                    )
                    await bot.edit_message_text(
                        text,
                        chat_id=chat_id,
                        message_id=session.message_id,
                        reply_markup=get_group_answer_keyboard(session.current_index),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        
        # Время вышло или все ответили
        await handle_group_timeout(bot, chat_id, session)
    
    except asyncio.CancelledError:
        pass


async def handle_group_timeout(bot: Bot, chat_id: int, session):
    """Обработка окончания времени на вопрос"""
    session.end_question()
    question = session.current_question
    
    # Записываем неответивших как неправильные
    for user_id, participant in session.participants.items():
        if user_id not in session.answered_users:
            participant.answers.append({
                "question": question,
                "user_answer": None,
                "is_correct": False,
                "time_expired": True
            })
            participant.total_answered += 1
    
    # Показываем результаты
    text = format_group_answer_result(question, session)
    
    try:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=session.message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    # Показываем текущий счёт
    await bot.send_message(
        chat_id,
        format_group_leaderboard(session, is_final=False),
        parse_mode="Markdown"
    )
    
    # Пауза перед следующим вопросом
    await asyncio.sleep(4)
    
    # Переход к следующему вопросу
    session.move_to_next()
    
    if session.is_finished:
        await finish_group_quiz(bot, chat_id, session)
    else:
        await send_group_question(bot, chat_id, session)


async def finish_group_quiz(bot: Bot, chat_id: int, session):
    """Завершение групповой викторины"""
    text = format_group_quiz_result(session)
    
    await bot.send_message(
        chat_id,
        text,
        reply_markup=get_group_result_keyboard(),
        parse_mode="Markdown"
    )
    
    # Сохраняем статистику в БД
    try:
        leaderboard = session.get_leaderboard()
        
        # Обновляем ЛИЧНУЮ статистику каждого участника
        for participant in leaderboard:
            # Создаём/обновляем пользователя в БД
            await get_or_create_user(
                participant.user_id,
                participant.username,
                participant.first_name
            )
            # Добавляем результаты к личной статистике
            await update_user_stats(
                participant.user_id,
                participant.total_answered,  # всего вопросов
                participant.correct_count    # правильных ответов
            )
        
        logger.info(f"[GROUP] Updated personal stats for {len(leaderboard)} participants")
        
        # Сохраняем групповую игру
        participants_data = [
            {
                'user_id': p.user_id,
                'username': p.username,
                'first_name': p.first_name,
                'correct_count': p.correct_count,
                'total_answered': p.total_answered
            }
            for p in leaderboard
        ]
        
        winner_data = None
        if leaderboard:
            winner = leaderboard[0]
            winner_data = {
                'user_id': winner.user_id,
                'username': winner.username,
                'correct_count': winner.correct_count
            }
        
        # Получаем название чата
        chat_info = await bot.get_chat(chat_id)
        chat_title = chat_info.title or f"Chat {chat_id}"
        
        await save_group_game(
            chat_id=chat_id,
            chat_title=chat_title,
            total_questions=session.total_questions,
            participants=participants_data,
            winner=winner_data
        )
    except Exception as e:
        # Логируем ошибку, но не прерываем работу
        logger.error(f"Error saving group game stats: {e}")
    
    # НЕ удаляем сессию, чтобы можно было посмотреть пояснения


# ============ ОТВЕТЫ НА ВОПРОСЫ ============

@router.callback_query(F.data.startswith("ganswer:"))
async def callback_group_answer(callback: CallbackQuery):
    """Обработка ответа участника в групповой игре"""
    parts = callback.data.split(":")
    question_index = int(parts[1])
    answer = parts[2]
    
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    logger.info(f"[GROUP] Answer received: chat={chat_id}, user={user_id}, q_idx={question_index}, answer={answer}")
    
    session = group_session_manager.get_session(chat_id)
    
    if not session:
        logger.warning(f"[GROUP] Session not found for chat {chat_id}")
        await callback.answer("❌ Сессия не найдена! Начните новую викторину командой /quiz", show_alert=True)
        return
    
    logger.info(f"[GROUP] Session state: is_active={session.is_question_active}, current_idx={session.current_index}, answered={session.answered_users}")
    
    # Проверяем, активен ли вопрос
    if not session.is_question_active:
        logger.warning(f"[GROUP] Question not active for chat {chat_id}")
        await callback.answer("❌ Время на ответ истекло!", show_alert=True)
        return
    
    # Проверяем, что отвечаем на текущий вопрос
    if session.current_index != question_index:
        logger.warning(f"[GROUP] Wrong question index: got {question_index}, expected {session.current_index}")
        await callback.answer("❌ Этот вопрос уже не активен!", show_alert=True)
        return
    
    # Проверяем, не ответил ли уже
    if user_id in session.answered_users:
        await callback.answer("❌ Вы уже ответили!", show_alert=True)
        return
    
    # Проверяем, участник ли это
    participant = session.get_participant(callback.from_user.id)
    if not participant:
        # Автоматически добавляем как участника
        participant = session.add_participant(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name
        )
    
    question = session.current_question
    correct_answer = question.get('correct_answer', '')
    is_correct = answer == correct_answer
    
    # Записываем ответ
    session.record_answer(callback.from_user.id, answer, is_correct)
    
    if is_correct:
        await callback.answer("✅ Правильно!")
    else:
        await callback.answer(f"❌ Неправильно! Ответ: {correct_answer}")
    
    # Обновляем счётчик ответивших
    try:
        question = session.current_question
        time_limit = await get_time_per_question()
        
        text = format_group_question(
            question,
            session.current_index + 1,
            session.total_questions,
            None,  # Не показываем время, т.к. это промежуточное обновление
            time_limit,
            len(session.answered_users),
            session.participants_count
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_group_answer_keyboard(session.current_index),
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ============ ПОЯСНЕНИЯ ============

@router.callback_query(F.data == "gshow_explanations")
async def callback_group_show_explanations(callback: CallbackQuery):
    """Показать пояснения для группы"""
    session = group_session_manager.get_session(callback.message.chat.id)
    
    if not session:
        await callback.answer("❌ Сессия не найдена!", show_alert=True)
        return
    
    if not session.questions:
        await callback.answer("❌ Нет данных для отображения!", show_alert=True)
        return
    
    # Показываем пояснение к первому вопросу
    question = session.questions[0]
    correct = question.get('correct_answer', '')
    options = question.get('options', {})
    explanation = question.get('explanation', 'Пояснение отсутствует.')
    
    text = f"*1/{session.total_questions}*\n\n"
    text += f"❓ _{question['question']}_\n\n"
    text += f"✅ Правильный ответ: *{correct}) {options.get(correct, '—')}*\n\n"
    text += f"📖 *Пояснение:*\n{explanation}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_explanation_keyboard(0, session.total_questions),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gexplanation:"))
async def callback_group_explanation(callback: CallbackQuery):
    """Показать конкретное пояснение"""
    index = int(callback.data.split(":")[1])
    session = group_session_manager.get_session(callback.message.chat.id)
    
    if not session or index >= len(session.questions):
        await callback.answer("❌ Данные не найдены!", show_alert=True)
        return
    
    question = session.questions[index]
    correct = question.get('correct_answer', '')
    options = question.get('options', {})
    explanation = question.get('explanation', 'Пояснение отсутствует.')
    
    text = f"*{index + 1}/{session.total_questions}*\n\n"
    text += f"❓ _{question['question']}_\n\n"
    text += f"✅ Правильный ответ: *{correct}) {options.get(correct, '—')}*\n\n"
    text += f"📖 *Пояснение:*\n{explanation}"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_explanation_keyboard(index, session.total_questions),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "gall_explanations")
async def callback_group_all_explanations(callback: CallbackQuery):
    """Показать все пояснения списком"""
    session = group_session_manager.get_session(callback.message.chat.id)
    
    if not session:
        await callback.answer("❌ Сессия не найдена!", show_alert=True)
        return
    
    text = format_group_all_explanations(session)
    
    # Telegram имеет лимит на длину сообщения
    if len(text) > 4000:
        text = text[:3997] + "..."
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_result_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "gnew_quiz")
async def callback_group_new_quiz(callback: CallbackQuery):
    """Начать новую групповую викторину"""
    # Завершаем текущую сессию
    group_session_manager.end_session(callback.message.chat.id)
    
    await callback.message.edit_text(
        "🍷 *Групповая викторина Wine Quiz!*\n\n"
        "Выберите страну для викторины:",
        reply_markup=get_group_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
