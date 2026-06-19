# TestFlow

Веб-приложение для онлайн-тестирования студентов с автоматической проверкой ответов и сохранением результатов.

## Возможности

### Преподаватель
- Создание, редактирование и удаление тестов
- Добавление вопросов (с выбором ответа и текстовых) с изображениями
- Управление доступностью тестов (даты начала/окончания, количество попыток)
- Просмотр результатов студентов с аналитикой
- Экспорт результатов в CSV
- Управление списком студентов

### Студент
- Просмотр доступных тестов
- Прохождение тестов с таймером
- Навигация между вопросами с сохранением ответов
- Получение автоматической оценки (2-5)
- Разбор ответов с указанием правильных вариантов
- Профиль со статистикой и историей прохождений

### Общее
- Регистрация с email-подтверждением
- Вход по email и паролю
- Сброс пароля через email
- Разделение ролей (студент / преподаватель)
- REST API для интеграции с другими системами

## Технологии

- **Backend:** Django 6.0, Python 3.12
- **Database:** PostgreSQL (продакшн) / SQLite (разработка)
- **Frontend:** Bootstrap 5, кастомный CSS
- **API:** Django REST Framework
- **Деплой:** Docker, Gunicorn, WhiteNoise
- **Тестирование:** Django TestCase (39 тестов)

## Установка

### Локальная разработка

```bash
# Клонирование
git clone <url>
cd testflow             

# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Переменные окружения
cp .env.example .env
# Отредактируйте .env под своё окружение

# Зависимости
pip install -r requirements.txt

# Миграции
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Запуск
python manage.py runserver
```

### Docker

```bash
docker-compose up --build
```

Приложение будет доступно по адресу `http://127.0.0.1:8000`

## API

REST API доступен по адресу `/api/`:

| Endpoint | Описание |
|----------|----------|
| `GET /api/tests/` | Список тестов |
| `GET /api/tests/{id}/` | Детали теста с вопросами |
| `GET /api/tests/{id}/availability/` | Проверка доступности |
| `GET /api/results/` | Результаты прохождений |
| `GET /api/profiles/me/` | Профиль текущего пользователя |

## Тестирование

```bash
python manage.py test tests_app -v 2
```

## Структура проекта

```
testflow/
├── testflow_project/     # Настройки Django
├── tests_app/          # Основное приложение
│   ├── models.py       # Модели данных
│   ├── views.py        # Представления
│   ├── urls.py         # Маршруты
│   ├── forms.py        # Формы
│   ├── serializers.py  # DRF сериализаторы
│   ├── api_views.py    # API представления
│   ├── tests.py        # Тесты
│   ├── templates/      # HTML шаблоны
│   └── static/         # Статические файлы
├── test_loaders/       # Скрипты загрузки тестов
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
