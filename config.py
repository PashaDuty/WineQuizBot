"""
Конфигурация бота Wine Quiz
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ID администратора
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Время на ответ (секунды)
TIME_PER_QUESTION = int(os.getenv("TIME_PER_QUESTION", "10"))

# Минимальное количество вопросов
MIN_QUESTIONS = int(os.getenv("MIN_QUESTIONS", "10"))

# Путь к вопросам
QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "data", "questions")

# Путь к базе данных
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# Настройки стран и регионов
COUNTRIES = {
    "france": {
        "name": "🇫🇷 Франция",
        "flag": "🇫🇷",
        "regions": {
            "bordeaux": {"name": "🍷 Бордо", "file": "Bordeaux.json"},
            "burgundy": {"name": "🍇 Бургундия", "file": "burgundy.json"},
            "champagne": {"name": "🍾 Шампань", "file": "champagne.json"},
            "alsace": {"name": "🏔️ Эльзас", "file": "Alsace.json"},
            "loire": {"name": "🏰 Долина Луары", "file": "loire Valley.json"},
            "rhone": {"name": "☀️ Долина Роны", "file": "Rhone Valley.json"},
            "south": {"name": "🌊 Юг Франции", "file": "south of france.json"},
        },
        "random_label": "🎲 Случайно по всей Франции"
    },
    "italy": {
        "name": "🇮🇹 Италия",
        "flag": "🇮🇹",
        "regions": {
            "piedmont": {"name": "🍷 Пьемонт", "file": "Piedmont.json"},
            "lombardy": {"name": "🏔️ Ломбардия", "file": "Lombardy.json"},
            "veneto": {"name": "🥂 Венето", "file": "Veneto.json"},
            "trentino": {"name": "⛰️ Трентино-Альто-Адидже", "file": "Trentino Alto Adige.json"},
            "friuli": {"name": "🌿 Фриули-Венеция-Джулия", "file": "Friuli Venezia Giulia.json"},
            "tuscany": {"name": "🍇 Тоскана", "file": "Tuscany.json"},
            "central": {"name": "🏛️ Центральная Италия", "file": "Central Italy.json"},
            "sicily": {"name": "🏝️ Сицилия и Сардиния", "file": "Sicily and Sardinia.json"},
            "south": {"name": "🌋 Юг Италии", "file": "Campania,Calabria,Puglia,Basilicata.json"},
        },
        "random_label": "🎲 Случайно по всей Италии"
    },
    "spain": {
        "name": "🇪🇸 Испания",
        "flag": "🇪🇸",
        "regions": {
            "rioja": {"name": "🍷 Риоха", "file": "rioja.json"},
            "catalonia_levante": {"name": "🌞 Каталония и Леванте", "file": "Catalonia and Levante.json"},
            "castile_leon": {"name": "🏰 Кастилия и Леон", "file": "Castile Leon.json"},
            "other": {"name": "🏔️ Другие регионы Испании", "file": "Basque Country, Galicia, La Mancha.json"},
        },
        "random_label": "🎲 Случайно по всей Испании"
    },
    "germany": {
        "name": "🇩🇪 Германия",
        "flag": "🇩🇪",
        "regions": {
            "all": {"name": "🍷 Все регионы Германии", "file": "Germany.json"},
        },
        "random_label": "🎲 Случайно по Германии"
    },
    "austria": {
        "name": "🇦🇹 Австрия",
        "flag": "🇦🇹",
        "regions": {
            "all": {"name": "🍷 Все регионы Австрии", "file": "Austria.json"},
        },
        "random_label": "🎲 Случайно по Австрии"
    }
}

# Варианты количества вопросов
QUESTION_COUNTS = [10, 20, 30]

# Сообщения в зависимости от результата
RESULT_MESSAGES = {
    "excellent": "🏆 Ты — истинный энциклопедист вина! Браво!",
    "good": "👍 Отличный результат! Видно, что ты не просто пьёшь, но и изучаешь!",
    "average": "😊 Хорошая попытка! Каждый вопрос — шаг к экспертизе. Возвращайся за новыми знаниями!"
}

def get_result_message(percentage: float) -> str:
    """Получить напутственное сообщение по проценту правильных ответов"""
    if percentage >= 95:
        return RESULT_MESSAGES["excellent"]
    elif percentage >= 70:
        return RESULT_MESSAGES["good"]
    else:
        return RESULT_MESSAGES["average"]
