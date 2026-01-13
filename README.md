# 🍷 Wine Quiz Bot

Telegram бот для викторины о винах разных стран и регионов.

## 📋 Возможности

- 🇫🇷 Викторины по винам Франции (Бордо, Бургундия)
- 🇪🇸 Викторины по винам Испании (Риоха, Страна Басков, Галисия, Ла-Манча)
- 🌍 Случайные вопросы по всем странам
- ⏱ Таймер на ответ с визуальным прогресс-баром
- 📊 Статистика пользователей
- 📖 Подробные пояснения к каждому вопросу
- ⚙️ Админ-панель для управления ботом

## 🚀 Быстрый старт

### 1. Клонирование проекта

```bash
git clone https://github.com/your-username/WineQuizBot.git
cd WineQuizBot
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Настройка

1. Создайте бота у [@BotFather](https://t.me/BotFather) и получите токен
2. Узнайте свой Telegram ID у [@userinfobot](https://t.me/userinfobot)
3. Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

4. Заполните `.env`:

```env
BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_ID=ваш_telegram_id
TIME_PER_QUESTION=10
MIN_QUESTIONS=10
```

### 4. Запуск

```bash
python bot.py
```

## 📁 Структура проекта

```
WineQuizBot/
├── bot.py                  # Главный файл бота
├── config.py               # Конфигурация
├── database.py             # Работа с SQLite
├── keyboards.py            # Клавиатуры и меню
├── questions_loader.py     # Загрузка вопросов из JSON
├── quiz_session.py         # Логика сессий викторины
├── handlers/               # Обработчики команд
│   ├── __init__.py
│   ├── start.py           # /start и выбор страны/региона
│   ├── quiz.py            # Логика викторины
│   └── admin.py           # Админ-панель
├── data/questions/         # JSON файлы с вопросами
│   ├── France/
│   │   ├── Bordeaux.json
│   │   └── burgundy.json
│   └── spain/
│       ├── rioja.json
│       └── Basque Country, Galicia, La Mancha.json
├── requirements.txt
├── .env.example
└── .gitignore
```

## 📝 Формат вопросов

Вопросы хранятся в JSON файлах:

```json
[
  {
    "id": 1,
    "question": "Текст вопроса?",
    "options": {
      "a": "Вариант А",
      "b": "Вариант Б",
      "c": "Вариант В",
      "d": "Вариант Г"
    },
    "correct_answer": "a",
    "explanation": "Подробное пояснение...",
    "tags": ["тег1", "тег2"],
    "country": "Франция",
    "region": "Бордо"
  }
]
```

## 🎮 Команды бота

### Для пользователей:
- `/start` - Начать викторину

### Для администратора:
- `/admin` - Открыть админ-панель
  - 📊 Показать статистику
  - ⚙️ Изменить время на ответ
  - 🔄 Перезагрузить вопросы
  - 📥 Выгрузить статистику в CSV

## ➕ Добавление новых вопросов

1. Создайте или отредактируйте JSON файл в папке `data/questions/страна/`
2. Используйте команду `/admin` → "🔄 Перезагрузить вопросы"

## 🔧 Добавление новой страны/региона

1. Создайте папку страны в `data/questions/`
2. Добавьте JSON файлы с вопросами
3. Обновите `config.py` → словарь `COUNTRIES`
4. Перезагрузите вопросы через админ-панель

## 📜 Лицензия

MIT License

## 🤝 Вклад в проект

Pull requests приветствуются!
