"""
Модуль управления групповыми сессиями викторины
"""
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime


@dataclass
class GroupParticipant:
    """Участник групповой викторины"""
    user_id: int
    username: str
    first_name: str
    correct_count: int = 0
    total_answered: int = 0
    answers: List[dict] = field(default_factory=list)  # История ответов
    current_answer: Optional[str] = None  # Ответ на текущий вопрос
    answer_time: Optional[float] = None  # Время ответа (для бонусов за скорость)
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя участника"""
        if self.username:
            return f"@{self.username}"
        return self.first_name or f"User {self.user_id}"
    
    @property
    def percentage(self) -> float:
        if self.total_answered == 0:
            return 0.0
        return round(self.correct_count * 100 / self.total_answered, 1)


@dataclass
class GroupQuizSession:
    """Сессия групповой викторины"""
    chat_id: int
    questions: List[dict]
    started_by: int  # ID пользователя, который начал викторину
    current_index: int = 0
    participants: Dict[int, GroupParticipant] = field(default_factory=dict)
    message_id: Optional[int] = None  # ID сообщения с текущим вопросом
    timer_task: Optional[asyncio.Task] = None  # Задача таймера
    is_question_active: bool = False  # Активен ли сейчас вопрос
    started_at: datetime = field(default_factory=datetime.now)
    question_start_time: Optional[float] = None  # Время начала вопроса
    answered_users: Set[int] = field(default_factory=set)  # Кто уже ответил на текущий вопрос
    
    @property
    def total_questions(self) -> int:
        return len(self.questions)
    
    @property
    def current_question(self) -> Optional[dict]:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None
    
    @property
    def is_finished(self) -> bool:
        return self.current_index >= len(self.questions)
    
    @property
    def participants_count(self) -> int:
        return len(self.participants)
    
    def add_participant(self, user_id: int, username: str, first_name: str) -> GroupParticipant:
        """Добавить участника в сессию"""
        if user_id not in self.participants:
            self.participants[user_id] = GroupParticipant(
                user_id=user_id,
                username=username or "",
                first_name=first_name or ""
            )
        return self.participants[user_id]
    
    def get_participant(self, user_id: int) -> Optional[GroupParticipant]:
        """Получить участника"""
        return self.participants.get(user_id)
    
    def record_answer(self, user_id: int, answer: str, is_correct: bool):
        """Записать ответ участника"""
        participant = self.participants.get(user_id)
        if not participant:
            return
        
        question = self.current_question
        if question:
            # Вычисляем время ответа
            answer_time = None
            if self.question_start_time:
                answer_time = asyncio.get_event_loop().time() - self.question_start_time
            
            participant.answers.append({
                "question": question,
                "user_answer": answer,
                "is_correct": is_correct,
                "answer_time": answer_time
            })
            participant.total_answered += 1
            if is_correct:
                participant.correct_count += 1
            
            self.answered_users.add(user_id)
    
    def start_question(self):
        """Начать новый вопрос"""
        self.is_question_active = True
        self.answered_users = set()
        self.question_start_time = asyncio.get_event_loop().time()
        # Сбрасываем текущие ответы участников
        for participant in self.participants.values():
            participant.current_answer = None
            participant.answer_time = None
    
    def end_question(self):
        """Завершить текущий вопрос"""
        self.is_question_active = False
        self.question_start_time = None
    
    def move_to_next(self):
        """Перейти к следующему вопросу"""
        self.current_index += 1
        self.end_question()
    
    def cancel_timer(self):
        """Отменить таймер если он запущен"""
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
            self.timer_task = None
    
    def get_leaderboard(self) -> List[GroupParticipant]:
        """Получить таблицу лидеров (отсортированную)"""
        return sorted(
            self.participants.values(),
            key=lambda p: (p.correct_count, -p.total_answered),
            reverse=True
        )
    
    def all_answered(self) -> bool:
        """Все ли участники ответили на текущий вопрос"""
        if not self.participants:
            return False
        return len(self.answered_users) >= len(self.participants)


class GroupSessionManager:
    """Менеджер групповых сессий"""
    
    def __init__(self):
        self._sessions: Dict[int, GroupQuizSession] = {}  # chat_id -> session
    
    def create_session(self, chat_id: int, questions: List[dict], started_by: int) -> GroupQuizSession:
        """Создать новую групповую сессию"""
        # Отменяем старую сессию, если есть
        self.end_session(chat_id)
        
        session = GroupQuizSession(
            chat_id=chat_id, 
            questions=questions,
            started_by=started_by
        )
        self._sessions[chat_id] = session
        return session
    
    def get_session(self, chat_id: int) -> Optional[GroupQuizSession]:
        """Получить сессию чата"""
        return self._sessions.get(chat_id)
    
    def end_session(self, chat_id: int) -> Optional[GroupQuizSession]:
        """Завершить сессию чата"""
        session = self._sessions.pop(chat_id, None)
        if session:
            session.cancel_timer()
        return session
    
    def has_active_session(self, chat_id: int) -> bool:
        """Проверить, есть ли активная сессия в чате"""
        session = self.get_session(chat_id)
        return session is not None and not session.is_finished


# Функции форматирования для групповой игры

def format_group_question(question: dict, current: int, total: int, 
                          remaining_time: Optional[int] = None,
                          total_time: Optional[int] = None,
                          answered_count: int = 0,
                          total_participants: int = 0) -> str:
    """Форматировать текст вопроса для группы"""
    from quiz_session import generate_progress_bar
    
    text = f"👥 *ГРУППОВАЯ ВИКТОРИНА*\n\n"
    text += f"❓ *Вопрос {current}/{total}:*\n\n"
    text += f"{question['question']}\n\n"
    
    options = question.get('options', {})
    text += f"a) {options.get('a', '—')}\n"
    text += f"b) {options.get('b', '—')}\n"
    text += f"c) {options.get('c', '—')}\n"
    text += f"d) {options.get('d', '—')}\n"
    
    if remaining_time is not None and total_time is not None:
        progress = generate_progress_bar(remaining_time, total_time)
        text += f"\n⏱ Осталось: {remaining_time} сек [{progress}]"
    
    if total_participants > 0:
        text += f"\n\n📊 Ответили: {answered_count}/{total_participants}"
    
    return text


def format_group_answer_result(question: dict, session: GroupQuizSession) -> str:
    """Форматировать результат ответа для группы"""
    correct_answer = question.get('correct_answer', '')
    options = question.get('options', {})
    
    text = f"⏱ *Время вышло!*\n\n"
    text += f"✅ Правильный ответ: *{correct_answer}) {options.get(correct_answer, '—')}*\n\n"
    
    # Показываем кто как ответил
    correct_users = []
    wrong_users = []
    no_answer_users = []
    
    for participant in session.participants.values():
        last_answer = participant.answers[-1] if participant.answers else None
        
        if participant.user_id not in session.answered_users:
            no_answer_users.append(participant.display_name)
        elif last_answer and last_answer.get('is_correct'):
            correct_users.append(participant.display_name)
        else:
            wrong_users.append(participant.display_name)
    
    if correct_users:
        text += f"✅ Правильно: {', '.join(correct_users)}\n"
    if wrong_users:
        text += f"❌ Неправильно: {', '.join(wrong_users)}\n"
    if no_answer_users:
        text += f"⏰ Не успели: {', '.join(no_answer_users)}\n"
    
    return text


def format_group_leaderboard(session: GroupQuizSession, is_final: bool = False) -> str:
    """Форматировать таблицу лидеров"""
    leaderboard = session.get_leaderboard()
    
    if is_final:
        text = "🏆 *ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ!*\n\n"
    else:
        text = "📊 *Текущий счёт:*\n\n"
    
    if not leaderboard:
        text += "_Пока нет участников_"
        return text
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, participant in enumerate(leaderboard):
        medal = medals[i] if i < 3 else f"{i + 1}."
        percentage = participant.percentage
        text += f"{medal} {participant.display_name}: "
        text += f"{participant.correct_count}/{participant.total_answered} "
        text += f"({percentage}%)\n"
    
    if is_final and leaderboard:
        winner = leaderboard[0]
        text += f"\n🎉 *Победитель: {winner.display_name}!*"
        
        if winner.percentage >= 90:
            text += "\n🏆 Великолепный результат!"
        elif winner.percentage >= 70:
            text += "\n👏 Отличная игра!"
        else:
            text += "\n🍷 Спасибо за участие!"
    
    return text


def format_group_quiz_result(session: GroupQuizSession) -> str:
    """Форматировать итоговый результат групповой викторины"""
    text = "🎉 *ВИКТОРИНА ЗАВЕРШЕНА!*\n\n"
    text += f"📊 Вопросов: {session.total_questions}\n"
    text += f"👥 Участников: {session.participants_count}\n\n"
    text += format_group_leaderboard(session, is_final=True)
    
    return text


def format_group_explanation(answer_record: dict, index: int, participant_name: str = None) -> str:
    """Форматировать пояснение к вопросу для группы"""
    question = answer_record['question']
    user_answer = answer_record.get('user_answer')
    is_correct = answer_record.get('is_correct', False)
    
    status = "✅" if is_correct else "❌"
    
    # Сокращаем текст вопроса если он слишком длинный
    question_text = question['question']
    if len(question_text) > 100:
        question_text = question_text[:97] + "..."
    
    text = f"*{index + 1}. {status}*\n"
    text += f"_{question_text}_\n\n"
    
    correct = question.get('correct_answer', '')
    options = question.get('options', {})
    
    text += f"📝 Правильный ответ: *{correct}) {options.get(correct, '—')}*\n"
    
    if user_answer and user_answer != correct:
        text += f"❌ Ваш ответ: {user_answer}) {options.get(user_answer, '—')}\n"
    
    explanation = question.get('explanation', 'Пояснение отсутствует.')
    text += f"\n📖 *Пояснение:*\n{explanation}"
    
    return text


def format_group_all_explanations(session: GroupQuizSession) -> str:
    """Форматировать все пояснения для групповой викторины"""
    text = "📚 *Пояснения к вопросам викторины:*\n\n"
    
    for i, question in enumerate(session.questions):
        correct = question.get('correct_answer', '')
        options = question.get('options', {})
        explanation = question.get('explanation', '')
        
        # Сокращаем текст вопроса
        question_text = question['question']
        if len(question_text) > 80:
            question_text = question_text[:77] + "..."
        
        # Сокращаем пояснение если оно слишком длинное
        if len(explanation) > 200:
            explanation = explanation[:197] + "..."
        
        text += f"*{i + 1}.* {question_text}\n"
        text += f"   ➡️ {correct}) {options.get(correct, '—')}\n"
        text += f"   _{explanation}_\n\n"
    
    return text


# Глобальный экземпляр менеджера групповых сессий
group_session_manager = GroupSessionManager()
