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
    
    # Заголовок CSV
    csv_lines = ["user_id,username,total_questions,correct_answers,success_rate,last_active"]
    
    for user in users:
        success_rate = 0.0
        if user['total_questions'] > 0:
            success_rate = round(user['correct_answers'] * 100.0 / user['total_questions'], 1)
        
        username = user['username'] if user['username'] else ''
        csv_lines.append(
            f"{user['user_id']},{username},{user['total_questions']},"
            f"{user['correct_answers']},{success_rate},{user['last_active']}"
        )
    
    return "\n".join(csv_lines)
