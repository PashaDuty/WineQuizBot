"""
Модуль управления сессиями викторины
"""
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime


@dataclass
class QuizSession:
    """Сессия викторины пользователя"""
    user_id: int
    questions: List[dict]
    current_index: int = 0
    correct_count: int = 0
    answers: List[dict] = field(default_factory=list)  # История ответов
    message_id: Optional[int] = None  # ID сообщения с текущим вопросом
    timer_task: Optional[asyncio.Task] = None  # Задача таймера
    is_answered: bool = False  # Флаг, что на текущий вопрос уже ответили
    started_at: datetime = field(default_factory=datetime.now)
    
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
    def percentage(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return round(self.correct_count * 100 / self.total_questions, 1)
    
    def record_answer(self, user_answer: Optional[str], is_correct: bool, time_expired: bool = False):
        """Записать ответ пользователя"""
        question = self.current_question
        if question:
            self.answers.append({
                "question": question,
                "user_answer": user_answer,
                "is_correct": is_correct,
                "time_expired": time_expired
            })
            if is_correct:
                self.correct_count += 1
    
    def move_to_next(self):
        """Перейти к следующему вопросу"""
        self.current_index += 1
        self.is_answered = False
    
    def cancel_timer(self):
        """Отменить таймер если он запущен"""
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
            self.timer_task = None


class SessionManager:
    """Менеджер сессий всех пользователей"""
    
    def __init__(self):
        self._sessions: Dict[int, QuizSession] = {}
    
    def create_session(self, user_id: int, questions: List[dict]) -> QuizSession:
        """Создать новую сессию викторины"""
        # Отменяем старую сессию, если есть
        self.end_session(user_id)
        
        session = QuizSession(user_id=user_id, questions=questions)
        self._sessions[user_id] = session
        return session
    
    def get_session(self, user_id: int) -> Optional[QuizSession]:
        """Получить сессию пользователя"""
        return self._sessions.get(user_id)
    
    def end_session(self, user_id: int) -> Optional[QuizSession]:
        """Завершить сессию пользователя"""
        session = self._sessions.pop(user_id, None)
        if session:
            session.cancel_timer()
        return session
    
    def has_active_session(self, user_id: int) -> bool:
        """Проверить, есть ли активная сессия"""
        session = self.get_session(user_id)
        return session is not None and not session.is_finished


def generate_progress_bar(remaining: int, total: int, length: int = 10) -> str:
    """Генерировать прогресс-бар для таймера"""
    filled = int((remaining / total) * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def format_question_text(question: dict, current: int, total: int, 
                         remaining_time: Optional[int] = None, 
                         total_time: Optional[int] = None) -> str:
    """Форматировать текст вопроса"""
    text = f"❓ *Вопрос {current}/{total}:*\n\n"
    text += f"{question['question']}\n\n"
    
    options = question.get('options', {})
    text += f"a) {options.get('a', '—')}\n"
    text += f"b) {options.get('b', '—')}\n"
    text += f"c) {options.get('c', '—')}\n"
    text += f"d) {options.get('d', '—')}\n"
    
    if remaining_time is not None and total_time is not None:
        progress = generate_progress_bar(remaining_time, total_time)
        text += f"\n⏱ Осталось: {remaining_time} сек [{progress}]"
    
    return text


def format_answer_result(question: dict, user_answer: Optional[str], 
                        is_correct: bool, time_expired: bool = False) -> str:
    """Форматировать результат ответа"""
    correct_answer = question.get('correct_answer', '')
    options = question.get('options', {})
    
    text = f"{'✅' if is_correct else '❌'} "
    
    if time_expired:
        text += "*Время вышло!*\n\n"
    elif is_correct:
        text += "*Правильно!*\n\n"
    else:
        text += "*Неправильно!*\n\n"
    
    text += f"{question['question']}\n\n"
    
    # Показываем варианты с отметками
    for key in ['a', 'b', 'c', 'd']:
        option_text = options.get(key, '—')
        marker = ""
        
        if key == correct_answer:
            marker = " ✅"
        elif key == user_answer and not is_correct:
            marker = " ❌"
        
        text += f"{key}) {option_text}{marker}\n"
    
    return text


def format_quiz_result(session: QuizSession) -> str:
    """Форматировать итоговый результат викторины"""
    from config import get_result_message
    
    text = "🎉 *ВИКТОРИНА ЗАВЕРШЕНА!*\n\n"
    text += f"✅ Правильных ответов: {session.correct_count} из {session.total_questions} "
    text += f"({session.percentage}%)\n\n"
    text += f"{get_result_message(session.percentage)}"
    
    return text


def format_explanation(answer_record: dict, index: int) -> str:
    """Форматировать пояснение к вопросу"""
    question = answer_record['question']
    user_answer = answer_record['user_answer']
    is_correct = answer_record['is_correct']
    time_expired = answer_record['time_expired']
    
    status = "✅" if is_correct else "❌"
    if time_expired:
        status += " (время вышло)"
    
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


def format_all_explanations(session: QuizSession) -> str:
    """Форматировать все пояснения списком"""
    text = "📚 *Пояснения к вопросам викторины:*\n\n"
    
    for i, answer_record in enumerate(session.answers):
        question = answer_record['question']
        is_correct = answer_record['is_correct']
        
        status = "✅" if is_correct else "❌"
        
        # Сокращаем текст вопроса
        question_text = question['question']
        if len(question_text) > 80:
            question_text = question_text[:77] + "..."
        
        correct = question.get('correct_answer', '')
        options = question.get('options', {})
        explanation = question.get('explanation', '')
        
        # Сокращаем пояснение если оно слишком длинное
        if len(explanation) > 200:
            explanation = explanation[:197] + "..."
        
        text += f"*{i + 1}.* {status} {question_text}\n"
        text += f"   ➡️ {correct}) {options.get(correct, '—')}\n"
        text += f"   _{explanation}_\n\n"
    
    return text


# Глобальный экземпляр менеджера сессий
session_manager = SessionManager()
