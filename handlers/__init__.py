"""
Обработчики команд бота
"""
from .start import router as start_router
from .quiz import router as quiz_router
from .admin import router as admin_router

__all__ = ['start_router', 'quiz_router', 'admin_router']
