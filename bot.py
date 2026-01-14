"""
Wine Quiz Bot - Telegram бот для викторины о винах
"""
import asyncio
import logging
import sys
import io

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import init_database
from questions_loader import questions_manager
from handlers import start_router, quiz_router, admin_router, group_quiz_router


# Исправление кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("[START] Zapusk bota Wine Quiz...")
    
    # Инициализация базы данных
    logger.info("[DB] Inicializaciya bazy dannyh...")
    await init_database()
    
    # Загрузка вопросов
    logger.info("[LOAD] Zagruzka voprosov iz JSON failov...")
    await questions_manager.load_all_questions()
    
    # Проверка загруженных вопросов
    total = questions_manager.get_questions_count()
    if total == 0:
        logger.warning("[WARN] Ne zagruzheno ni odnogo voprosa!")
    else:
        logger.info(f"[OK] Zagruzheno {total} voprosov")
    
    # Информация о боте
    bot_info = await bot.get_me()
    logger.info(f"[BOT] Bot zapushen: @{bot_info.username}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("[STOP] Bot ostanovlen")


async def main():
    """Главная функция"""
    # Проверка токена
    if not BOT_TOKEN:
        logger.error("[ERROR] BOT_TOKEN ne najden! Sozdajte fajl .env s tokenom bota.")
        sys.exit(1)
    
    # Создание бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    
    # Регистрация роутеров (group_quiz ПЕРВЫМ, чтобы перехватывать групповые callback'и)
    logger.info("[ROUTERS] Registering group_quiz_router first...")
    dp.include_router(group_quiz_router)  # Групповой роутер ПЕРВЫМ!
    logger.info("[ROUTERS] Registering other routers...")
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(admin_router)
    logger.info("[ROUTERS] All routers registered")
    
    # Регистрация событий
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Middleware для логирования всех update'ов
    @dp.update.middleware()
    async def log_updates_middleware(handler, event, data):
        """Логировать все update'и для отладки"""
        if hasattr(event, 'callback_query') and event.callback_query:
            logger.info(f"[UPDATE] Callback: {event.callback_query.data} in chat {event.callback_query.message.chat.id}")
        return await handler(event, data)
    
    # Запуск бота
    try:
        logger.info("[WINE] Wine Quiz Bot starting...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot ostanovlen polzovatelem")
    except Exception as e:
        logger.error(f"Kriticheskaya oshibka: {e}")
        sys.exit(1)
