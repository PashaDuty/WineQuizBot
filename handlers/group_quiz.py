"""
Обработчик групповой викторины
"""
import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ChatType

logger = logging.getLogger(__name__)

from keyboards import (
    get_group_answer_keyboard,
    get_group_result_keyboard,
    get_group_explanation_keyboard,
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
    format_group_all_explanations,
    format_group_leaderboard
)
from database import get_setting, save_group_game, update_user_stats, get_or_create_user
from config import TIME_PER_QUESTION, MIN_QUESTIONS, COUNTRIES

router = Router()

# Время ожидания присоединения участников (секунды)
JOIN_TIMEOUT = 60

# Минимум участников для старта
MIN_PARTICIPANTS = 1


def is_group_chat(message_or_callback) -> bool:
    """Проверить, что это групповой чат"""
    if isinstance(message_or_callback, Message):
        chat = message_or_callback.chat
    else:
        chat = message_or_callback.message.chat
    return chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]


async def get_time_per_question() -> int:
    """Получить текущее время на ответ из настроек"""
    setting = await get_setting("time_per_question")
    if setting:
        return int(setting)
    return TIME_PER_QUESTION


# ============ КОМАНДЫ ДЛЯ ГРУППЫ ============

@router.message(Command("quiz"))
async def cmd_group_quiz(message: Message):
    """Начать групповую викторину командой /quiz"""
    if not is_group_chat(message):
        await message.answer(
            "⚠️ Эта команда работает только в групповых чатах!\n\n"
            "Добавьте бота в группу и напишите /quiz"
        )
        return
    
    # Проверяем, нет ли уже активной сессии
    existing_session = group_session_manager.get_session(message.chat.id)
    if existing_session:
        await message.answer(
            "⚠️ В этом чате уже идёт викторина!\n"
            "Дождитесь окончания или используйте /stop_quiz"
        )
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
    if not is_group_chat(callback):
        await callback.answer("Только для групповых чатов!", show_alert=True)
        return
    
    # Проверяем, нет ли уже сессии
    if group_session_manager.get_session(callback.message.chat.id):
        await callback.answer("⚠️ Викторина уже запущена!", show_alert=True)
        return
    
    country_code = callback.data.split(":")[1]
    
    if country_code == "all":
        available = questions_manager.get_questions_count()
        
        if available == 0:
            await callback.answer("❌ Нет доступных вопросов!", show_alert=True)
            return
        
        text = "🌍 *Викторина по всем странам*\n\n"
        text += f"📊 Доступно вопросов: {available}\n\n"
        text += "Выберите количество вопросов:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_group_question_count_keyboard("all", "all", available),
            parse_mode="Markdown"
        )
    else:
        if country_code not in COUNTRIES:
            await callback.answer("❌ Страна не найдена!", show_alert=True)
            return
        
        country_data = COUNTRIES[country_code]
        available = questions_manager.get_questions_count(country=country_code)
        
        text = f"{country_data['flag']} *{country_data['name']}*\n\n"
        text += f"📊 Всего вопросов: {available}\n\n"
        text += "Выберите регион:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_group_regions_keyboard(country_code),
            parse_mode="Markdown"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("gregion:"))
async def callback_group_region(callback: CallbackQuery):
    """Выбор региона для групповой викторины"""
    if group_session_manager.get_session(callback.message.chat.id):
        await callback.answer("⚠️ Викторина уже запущена!", show_alert=True)
        return
    
    parts = callback.data.split(":")
    country_code = parts[1]
    region_code = parts[2]
    
    if region_code == "all":
        available = questions_manager.get_questions_count(country=country_code)
        region_name = "все регионы"
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
    text += "Выберите количество вопросов:"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_question_count_keyboard(country_code, region_code, available),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "gback:countries")
async def callback_group_back_countries(callback: CallbackQuery):
    """Вернуться к выбору страны"""
    if group_session_manager.get_session(callback.message.chat.id):
        await callback.answer("⚠️ Викторина уже запущена!", show_alert=True)
        return
    
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
    if group_session_manager.get_session(callback.message.chat.id):
        await callback.answer("⚠️ Викторина уже запущена!", show_alert=True)
        return
    
    country_code = callback.data.split(":")[2]
    
    if country_code not in COUNTRIES:
        await callback.answer("❌ Страна не найдена!", show_alert=True)
        return
    
    country_data = COUNTRIES[country_code]
    available = questions_manager.get_questions_count(country=country_code)
    
    text = f"{country_data['flag']} *{country_data['name']}*\n\n"
    text += f"📊 Всего вопросов: {available}\n\n"
    text += "Выберите регион:"
    
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
    try:
        chat_id = callback.message.chat.id
        user_id = callback.from_user.id
        
        logger.info(f"[GROUP] gcount: callback from user {user_id} in chat {chat_id}, data={callback.data}")
        
        # Проверяем тип чата
        if not is_group_chat(callback):
            await callback.answer("❌ Только для групповых чатов!", show_alert=True)
            return
        
        # Проверяем, нет ли уже сессии
        if group_session_manager.get_session(chat_id):
            await callback.answer("⚠️ Викторина уже запущена!", show_alert=True)
            return
        
        parts = callback.data.split(":")
        if len(parts) != 4:
            logger.error(f"[GROUP] Invalid callback data format: {callback.data}")
            await callback.answer("❌ Ошибка формата данных!", show_alert=True)
            return
        
        country = parts[1]
        region = parts[2]
        count = int(parts[3])
        
        logger.info(f"[GROUP] Selected: country={country}, region={region}, count={count}")
    
        # Получаем вопросы
        logger.info(f"[GROUP] Getting questions: country={country}, region={region}, count={count}")
        if country == "all":
            available = questions_manager.get_questions_count()
            questions = questions_manager.get_random_questions(count)
        elif region == "all":
            available = questions_manager.get_questions_count(country=country)
            questions = questions_manager.get_random_questions(count, country=country)
        else:
            available = questions_manager.get_questions_count(country=country, region=region)
            questions = questions_manager.get_random_questions(count, country=country, region=region)
        
        logger.info(f"[GROUP] Got {len(questions) if questions else 0} questions, available={available}")
        
        if available < MIN_QUESTIONS:
            await callback.answer(f"❌ Недостаточно вопросов! Минимум {MIN_QUESTIONS}.", show_alert=True)
            return
        
        if not questions:
            logger.error(f"[GROUP] No questions returned!")
            await callback.answer("❌ Не удалось загрузить вопросы!", show_alert=True)
            return
        
        # Создаём сессию
        logger.info(f"[GROUP] Creating session...")
        session = group_session_manager.create_session(chat_id, questions, callback.from_user.id)
        
        # Добавляем организатора как первого участника
        organizer = session.add_participant(
            callback.from_user.id,
            callback.from_user.username or "",
            callback.from_user.first_name or "Участник"
        )
        
        logger.info(f"[GROUP] Created session in chat {chat_id}, organizer: {organizer.display_name}, questions: {len(questions)}")
        
        # Отправляем новое сообщение с регистрацией
        registration_text = (
            f"🍷 *Регистрация на викторину!*\n\n"
            f"📊 Вопросов: {len(questions)}\n"
            f"⏱ Регистрация: {JOIN_TIMEOUT} сек\n\n"
            f"👥 *Участники ({session.participants_count}):*\n"
            f"• {organizer.display_name} (организатор)\n\n"
            f"_Нажмите «Участвую» чтобы присоединиться!_"
        )
        
        logger.info(f"[GROUP] Sending registration message to chat {chat_id}")
        msg = await callback.bot.send_message(
            chat_id,
            registration_text,
            reply_markup=get_group_join_keyboard(),
            parse_mode="Markdown"
        )
        session.registration_message_id = msg.message_id
        logger.info(f"[GROUP] Registration message sent successfully, msg_id={session.registration_message_id}")
        
        # Отвечаем на callback после успешной отправки
        await callback.answer("✅ Регистрация началась!")
        
        # Запускаем таймер регистрации
        session.timer_task = asyncio.create_task(
            registration_timer(callback.bot, chat_id, session.registration_message_id, session)
        )
        logger.info(f"[GROUP] Registration timer task created")
        
    except Exception as e:
        logger.error(f"[GROUP] CRITICAL ERROR in callback_group_start: {e}", exc_info=True)
        try:
            await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)
        except:
            pass
        # Очищаем сессию при ошибке
        group_session_manager.end_session(chat_id)


async def registration_timer(bot: Bot, chat_id: int, message_id: int, session):
    """Таймер регистрации участников (60 секунд)"""
    logger.info(f"[GROUP] Registration timer started for chat {chat_id}, msg_id={message_id}")
    try:
        remaining = JOIN_TIMEOUT
        
        while remaining > 0:
            await asyncio.sleep(5)
            remaining -= 5
            
            # Проверяем, не была ли игра уже запущена
            if session.is_question_active or session.current_index > 0:
                logger.info(f"[GROUP] Registration timer: game already started")
                return
            
            # Проверяем, существует ли ещё сессия
            current_session = group_session_manager.get_session(chat_id)
            if current_session is not session:
                logger.info(f"[GROUP] Registration timer: session changed or removed")
                return
            
            # Обновляем сообщение
            participants_list = "\n".join([
                f"• {p.display_name}" + (" (организатор)" if p.user_id == session.started_by else "")
                for p in session.participants.values()
            ])
            
            try:
                await bot.edit_message_text(
                    f"🍷 *Регистрация на викторину!*\n\n"
                    f"📊 Вопросов: {session.total_questions}\n"
                    f"⏱ Осталось: {remaining} сек\n\n"
                    f"👥 *Участники ({session.participants_count}):*\n"
                    f"{participants_list}\n\n"
                    f"_Нажмите «Участвую» чтобы присоединиться!_",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=get_group_join_keyboard(),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.debug(f"[GROUP] Failed to update registration message: {e}")
        
        # Время вышло - начинаем игру
        current_session = group_session_manager.get_session(chat_id)
        if current_session is not session:
            return
        
        if session.is_question_active or session.current_index > 0:
            return
        
        logger.info(f"[GROUP] Registration finished, participants: {session.participants_count}")
        
        if session.participants_count >= MIN_PARTICIPANTS:
            await start_group_quiz(bot, chat_id, session)
        else:
            group_session_manager.end_session(chat_id)
            await bot.send_message(
                chat_id,
                f"⚠️ Недостаточно участников.\n"
                f"Минимум: {MIN_PARTICIPANTS}, зарегистрировалось: {session.participants_count}"
            )
    
    except asyncio.CancelledError:
        logger.info(f"[GROUP] Registration timer cancelled for chat {chat_id}")
    except Exception as e:
        logger.error(f"[GROUP] Registration timer error: {e}")


@router.callback_query(F.data == "gjoin")
async def callback_join_quiz(callback: CallbackQuery):
    """Присоединиться к викторине"""
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    session = group_session_manager.get_session(chat_id)
    
    if not session:
        await callback.answer("❌ Регистрация завершена или викторина не найдена!", show_alert=True)
        return
    
    # Если игра уже идёт - нельзя присоединиться
    if session.is_question_active or session.current_index > 0:
        await callback.answer("❌ Викторина уже началась! Дождитесь следующей.", show_alert=True)
        return
    
    # Проверяем, уже ли участник зарегистрирован
    if user_id in session.participants:
        await callback.answer("✅ Вы уже зарегистрированы!", show_alert=True)
        return
    
    # Добавляем участника
    participant = session.add_participant(
        user_id,
        callback.from_user.username or "",
        callback.from_user.first_name or "Участник"
    )
    
    logger.info(f"[GROUP] Player joined: {participant.display_name} in chat {chat_id}")
    
    # Обновляем список участников
    participants_list = "\n".join([
        f"• {p.display_name}" + (" (организатор)" if p.user_id == session.started_by else "")
        for p in session.participants.values()
    ])
    
    # Обновляем сообщение регистрации
    if session.registration_message_id:
        try:
            await callback.bot.edit_message_text(
                f"🍷 *Регистрация на викторину!*\n\n"
                f"📊 Вопросов: {session.total_questions}\n"
                f"⏱ Ожидание участников...\n\n"
                f"👥 *Участники ({session.participants_count}):*\n"
                f"{participants_list}\n\n"
                f"_Нажмите «Участвую» чтобы присоединиться!_",
                chat_id=chat_id,
                message_id=session.registration_message_id,
                reply_markup=get_group_join_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"[GROUP] Failed to update registration message: {e}")
    
    await callback.answer(f"✅ {participant.display_name} присоединился!")


@router.callback_query(F.data == "gstart_now")
async def callback_start_now(callback: CallbackQuery):
    """Начать викторину досрочно (только организатор)"""
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    session = group_session_manager.get_session(chat_id)
    
    if not session:
        await callback.answer("❌ Викторина не найдена!", show_alert=True)
        return
    
    # Только организатор может начать досрочно
    if user_id != session.started_by:
        await callback.answer("❌ Только организатор может начать досрочно!", show_alert=True)
        return
    
    if session.is_question_active or session.current_index > 0:
        await callback.answer("❌ Викторина уже началась!", show_alert=True)
        return
    
    if session.participants_count < MIN_PARTICIPANTS:
        await callback.answer(f"❌ Нужно минимум {MIN_PARTICIPANTS} участник!", show_alert=True)
        return
    
    # Отменяем таймер регистрации
    session.cancel_timer()
    
    await callback.answer("🚀 Начинаем!")
    await start_group_quiz(callback.bot, chat_id, session)


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
    
    logger.info(f"[GROUP] Question {session.current_index + 1}/{session.total_questions} in chat {chat_id}")
    
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
    
    # Запускаем таймер вопроса
    session.timer_task = asyncio.create_task(
        question_timer(bot, chat_id, session, time_limit)
    )


async def question_timer(bot: Bot, chat_id: int, session, total_time: int):
    """Таймер для вопроса"""
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
                logger.info(f"[GROUP] All answered in chat {chat_id}")
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
        
        # Завершаем вопрос
        await finish_question(bot, chat_id, session)
    
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[GROUP] Question timer error: {e}")


async def finish_question(bot: Bot, chat_id: int, session):
    """Завершить вопрос и показать результаты"""
    session.end_question()
    question = session.current_question
    
    # Записываем неответивших
    for user_id, participant in session.participants.items():
        if user_id not in session.answered_users:
            participant.answers.append({
                "question": question,
                "user_answer": None,
                "is_correct": False,
                "time_expired": True
            })
            participant.total_answered += 1
    
    # Показываем правильный ответ
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
    
    await asyncio.sleep(4)
    
    # Следующий вопрос или финиш
    session.move_to_next()
    
    if session.is_finished:
        await finish_group_quiz(bot, chat_id, session)
    else:
        await send_group_question(bot, chat_id, session)


async def finish_group_quiz(bot: Bot, chat_id: int, session):
    """Завершение групповой викторины"""
    logger.info(f"[GROUP] Quiz finished in chat {chat_id}")
    
    text = format_group_quiz_result(session)
    
    await bot.send_message(
        chat_id,
        text,
        reply_markup=get_group_result_keyboard(),
        parse_mode="Markdown"
    )
    
    # Сохраняем статистику
    try:
        leaderboard = session.get_leaderboard()
        
        # Обновляем личную статистику каждого участника
        for participant in leaderboard:
            await get_or_create_user(
                participant.user_id,
                participant.username,
                participant.first_name
            )
            await update_user_stats(
                participant.user_id,
                participant.total_answered,
                participant.correct_count
            )
        
        logger.info(f"[GROUP] Saved stats for {len(leaderboard)} participants")
        
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
        logger.error(f"[GROUP] Error saving stats: {e}")
    
    # НЕ удаляем сессию - нужна для пояснений


# ============ ОТВЕТЫ НА ВОПРОСЫ ============

@router.callback_query(F.data.startswith("ganswer:"))
async def callback_group_answer(callback: CallbackQuery):
    """Обработка ответа участника"""
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    parts = callback.data.split(":")
    question_index = int(parts[1])
    answer = parts[2]
    
    session = group_session_manager.get_session(chat_id)
    
    if not session:
        await callback.answer("❌ Викторина не найдена!", show_alert=True)
        return
    
    # Проверяем, активен ли вопрос
    if not session.is_question_active:
        await callback.answer("❌ Время вышло!", show_alert=True)
        return
    
    # Проверяем индекс вопроса
    if session.current_index != question_index:
        await callback.answer("❌ Этот вопрос уже не активен!", show_alert=True)
        return
    
    # Проверяем, не ответил ли уже
    if user_id in session.answered_users:
        await callback.answer("❌ Вы уже ответили!", show_alert=True)
        return
    
    # Если участник не зарегистрирован - добавляем его
    participant = session.get_participant(user_id)
    if not participant:
        participant = session.add_participant(
            user_id,
            callback.from_user.username or "",
            callback.from_user.first_name or "Участник"
        )
        logger.info(f"[GROUP] Late join: {participant.display_name} in chat {chat_id}")
    
    # Записываем ответ
    question = session.current_question
    correct_answer = question.get('correct_answer', '')
    is_correct = answer == correct_answer
    
    session.record_answer(user_id, answer, is_correct)
    
    logger.info(f"[GROUP] Answer from {participant.display_name}: {answer}, correct={is_correct}")
    
    if is_correct:
        await callback.answer("✅ Правильно!")
    else:
        await callback.answer(f"❌ Неправильно! Ответ: {correct_answer}")
    
    # Обновляем счётчик
    try:
        time_limit = await get_time_per_question()
        text = format_group_question(
            question,
            session.current_index + 1,
            session.total_questions,
            None,
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
    """Показать пояснения (первый вопрос)"""
    session = group_session_manager.get_session(callback.message.chat.id)
    
    if not session or not session.questions:
        await callback.answer("❌ Данные не найдены!", show_alert=True)
        return
    
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
        await callback.answer("❌ Данные не найдены!", show_alert=True)
        return
    
    text = format_group_all_explanations(session)
    
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
    """Начать новую викторину"""
    group_session_manager.end_session(callback.message.chat.id)
    
    await callback.message.edit_text(
        "🍷 *Групповая викторина Wine Quiz!*\n\n"
        "Выберите страну для викторины:",
        reply_markup=get_group_countries_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
