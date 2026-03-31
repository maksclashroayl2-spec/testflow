import os
import django

# Настройка окружения Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diplom_project.settings")
django.setup()

from tests_app.models import Test, Question, Answer

# Удаляем старые данные, если нужно
Test.objects.all().delete()
Question.objects.all().delete()
Answer.objects.all().delete()

# Создаем тест
test = Test.objects.create(
    title="Операционные системы",
    description="Экзаменационный тест по дисциплине 'Операционные системы' (15 вопросов)."
)

# Вопросы
questions = [
    {
        "text": "Что такое операционная система?",
        "answers": [
            ("Программа, управляющая аппаратными ресурсами компьютера", True),
            ("Только средство для запуска игр", False),
            ("Программа для написания текста", False),
            ("Антивирус", False),
        ],
    },
    {
        "text": "Какая из перечисленных систем является операционной?",
        "answers": [
            ("MS-DOS", True),
            ("Google Chrome", False),
            ("Visual Studio Code", False),
            ("Mozilla Firefox", False),
        ],
    },
    {
        "text": "Какая ОС является мобильной?",
        "answers": [
            ("Android", True),
            ("Windows 7", False),
            ("Linux Mint", False),
            ("macOS", False),
        ],
    },
    {
        "text": "Что выполняет загрузка BIOS?",
        "answers": [
            ("Проверку оборудования и запуск ОС", True),
            ("Установку драйверов", False),
            ("Удаление файлов", False),
            ("Вывод изображений", False),
        ],
    },
    {
        "text": "Какая из ОС является многопользовательской?",
        "answers": [
            ("Linux", True),
            ("MS-DOS", False),
            ("Windows 95", False),
            ("Android", False),
        ],
    },
    {
        "text": "Что означает аббревиатура GUI?",
        "answers": [
            ("Графический интерфейс пользователя", True),
            ("Главный универсальный интерфейс", False),
            ("Общий интерфейс сети", False),
            ("Интерфейс командной строки", False),
        ],
    },
    {
        "text": "Какую функцию выполняет планировщик задач в ОС?",
        "answers": [
            ("Распределяет ресурсы между процессами", True),
            ("Удаляет ненужные программы", False),
            ("Обновляет драйверы", False),
            ("Создаёт резервные копии", False),
        ],
    },
    {
        "text": "Какая из ОС имеет открытый исходный код?",
        "answers": [
            ("Linux", True),
            ("Windows", False),
            ("macOS", False),
            ("Android", False),
        ],
    },
    {
        "text": "Какой компонент отвечает за взаимодействие программ с оборудованием?",
        "answers": [
            ("Драйвер", True),
            ("Командная строка", False),
            ("Текстовый редактор", False),
            ("Файловый менеджер", False),
        ],
    },
    {
        "text": "Что такое ядро ОС?",
        "answers": [
            ("Основная часть системы, управляющая ресурсами", True),
            ("Текстовый файл настроек", False),
            ("Модуль антивируса", False),
            ("Система шифрования данных", False),
        ],
    },
    {
        "text": "Какая ОС используется в серверах?",
        "answers": [
            ("Linux", True),
            ("Android", False),
            ("Windows XP", False),
            ("MS-DOS", False),
        ],
    },
    {
        "text": "Какой тип интерфейса имеет MS-DOS?",
        "answers": [
            ("Командная строка", True),
            ("Графический интерфейс", False),
            ("Голосовое управление", False),
            ("Тактильный интерфейс", False),
        ],
    },
    {
        "text": "Что делает файловая система?",
        "answers": [
            ("Организует хранение и доступ к данным на диске", True),
            ("Удаляет вирусы", False),
            ("Проверяет интернет-соединение", False),
            ("Отвечает за питание компьютера", False),
        ],
    },
    {
        "text": "Какая из систем является UNIX-подобной?",
        "answers": [
            ("macOS", True),
            ("Windows", False),
            ("MS-DOS", False),
            ("ReactOS", False),
        ],
    },
    {
        "text": "Что делает процессорное планирование?",
        "answers": [
            ("Определяет, какой процесс будет выполняться дальше", True),
            ("Удаляет старые процессы", False),
            ("Создаёт резервные копии", False),
            ("Перезагружает компьютер", False),
        ],
    },
]

# Добавляем вопросы и ответы
for q in questions:
    question = Question.objects.create(test=test, text=q["text"])
    for answer_text, is_correct in q["answers"]:
        Answer.objects.create(question=question, text=answer_text, is_correct=is_correct)

print("✅ Тест 'Операционные системы' успешно создан с 15 вопросами!")
