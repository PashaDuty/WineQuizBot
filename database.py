"""
Модуль работы с базой данных SQLite для хранения статистики пользователей
"""
import aiosqlite
from datetime import datetime
from typing import Optional, List, Tuple
from config import DATABASE_PATH


async def init_database():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                total_questions INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                quizzes_completed INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица настроек (для админа)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Таблица групповых игр
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                total_questions INTEGER DEFAULT 0,
                participants_count INTEGER DEFAULT 0,
                winner_user_id INTEGER,
                winner_username TEXT,
                winner_score INTEGER DEFAULT 0,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица статистики участников групповых игр
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                correct_answers INTEGER DEFAULT 0,
                total_answered INTEGER DEFAULT 0,
                place INTEGER DEFAULT 0,
                FOREIGN KEY (game_id) REFERENCES group_games(id)
            )
        """)
        
        await db.commit()


async def get_or_create_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> dict:
    """Получить или создать пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Проверяем существование пользователя
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        user = await cursor.fetchone()
        
        if user:
            # Обновляем данные пользователя
            await db.execute("""
                UPDATE users 
                SET username = ?, first_name = ?, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, first_name, user_id))
            await db.commit()
            return dict(user)
        else:
            # Создаём нового пользователя
            await db.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (user_id, username, first_name))
            await db.commit()
            
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            return dict(user)


async def update_user_stats(user_id: int, total_questions: int, correct_answers: int):
    """Обновить статистику пользователя после викторины"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET total_questions = total_questions + ?,
                correct_answers = correct_answers + ?,
                quizzes_completed = quizzes_completed + 1,
                last_active = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (total_questions, correct_answers, user_id))
        await db.commit()


async def get_all_users_stats() -> List[dict]:
    """Получить статистику всех пользователей"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM users 
            ORDER BY correct_answers DESC, total_questions DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_user_stats(user_id: int) -> Optional[dict]:
    """Получить статистику конкретного пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT user_id, username, first_name, total_questions, correct_answers, quizzes_completed,
                   CASE WHEN total_questions > 0 
                        THEN ROUND(correct_answers * 100.0 / total_questions, 1) 
                        ELSE 0 
                   END as success_rate
            FROM users 
            WHERE user_id = ?
        """, (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_top_users(limit: int = 10) -> List[dict]:
    """Получить топ пользователей"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT user_id, username, first_name, total_questions, correct_answers,
                   CASE WHEN total_questions > 0 
                        THEN ROUND(correct_answers * 100.0 / total_questions, 1) 
                        ELSE 0 
                   END as success_rate
            FROM users 
            WHERE total_questions > 0
            ORDER BY success_rate DESC, total_questions DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_total_stats() -> Tuple[int, int]:
    """Получить общую статистику: всего пользователей и всего ответов"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT SUM(total_questions) FROM users")
        result = await cursor.fetchone()
        total_answers = result[0] if result[0] else 0
        
        return total_users, total_answers


async def get_setting(key: str, default: str = None) -> Optional[str]:
    """Получить настройку из базы данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        result = await cursor.fetchone()
        return result[0] if result else default


async def set_setting(key: str, value: str):
    """Установить настройку в базу данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        """, (key, value))
        await db.commit()


async def export_users_csv() -> str:
    """Экспортировать статистику пользователей в CSV формат"""
    users = await get_all_users_stats()
    
    # Заголовок CSV с понятными названиями (разделитель ;)
    csv_lines = ["ID пользователя;Username;Имя;Всего вопросов;Правильных ответов;Процент успеха;Викторин пройдено;Последняя активность"]
    
    for user in users:
        success_rate = 0.0
        if user['total_questions'] > 0:
            success_rate = round(user['correct_answers'] * 100.0 / user['total_questions'], 1)
        
        username = user['username'] if user['username'] else '-'
        first_name = user['first_name'] if user['first_name'] else '-'
        quizzes = user.get('quizzes_completed', 0)
        
        csv_lines.append(
            f"{user['user_id']};@{username};{first_name};{user['total_questions']};"
            f"{user['correct_answers']};{success_rate}%;{quizzes};{user['last_active']}"
        )
    
    return "\n".join(csv_lines)


# ============ ФУНКЦИИ ДЛЯ ГРУППОВЫХ ИГР ============

async def save_group_game(chat_id: int, chat_title: str, total_questions: int,
                          participants: list, winner: dict) -> int:
    """Сохранить результаты групповой игры"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Сохраняем игру
        cursor = await db.execute("""
            INSERT INTO group_games (chat_id, chat_title, total_questions, 
                                     participants_count, winner_user_id, 
                                     winner_username, winner_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            chat_title,
            total_questions,
            len(participants),
            winner.get('user_id') if winner else None,
            winner.get('username') if winner else None,
            winner.get('correct_count', 0) if winner else 0
        ))
        game_id = cursor.lastrowid
        
        # Сохраняем участников
        for i, participant in enumerate(participants):
            await db.execute("""
                INSERT INTO group_participants (game_id, user_id, username, 
                                                first_name, correct_answers,
                                                total_answered, place)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                participant['user_id'],
                participant.get('username'),
                participant.get('first_name'),
                participant.get('correct_count', 0),
                participant.get('total_answered', 0),
                i + 1  # Место (1, 2, 3...)
            ))
        
        await db.commit()
        return game_id


async def get_group_stats(chat_id: int) -> dict:
    """Получить статистику групповых игр для чата"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Общее количество игр
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM group_games WHERE chat_id = ?",
            (chat_id,)
        )
        result = await cursor.fetchone()
        total_games = result['count'] if result else 0
        
        # Топ победителей
        cursor = await db.execute("""
            SELECT winner_username, COUNT(*) as wins
            FROM group_games 
            WHERE chat_id = ? AND winner_username IS NOT NULL
            GROUP BY winner_user_id
            ORDER BY wins DESC
            LIMIT 5
        """, (chat_id,))
        top_winners = await cursor.fetchall()
        
        return {
            'total_games': total_games,
            'top_winners': [dict(row) for row in top_winners]
        }


async def get_user_group_stats(user_id: int) -> dict:
    """Получить статистику участия пользователя в групповых играх"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Статистика участия
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as games_played,
                SUM(correct_answers) as total_correct,
                SUM(total_answered) as total_questions,
                SUM(CASE WHEN place = 1 THEN 1 ELSE 0 END) as wins
            FROM group_participants
            WHERE user_id = ?
        """, (user_id,))
        result = await cursor.fetchone()
        
        return dict(result) if result else {
            'games_played': 0,
            'total_correct': 0,
            'total_questions': 0,
            'wins': 0
        }
