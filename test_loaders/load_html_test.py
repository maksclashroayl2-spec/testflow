# -*- coding: utf-8 -*-

from django.contrib.auth.models import User
from tests_app.models import Test, Question, Answer
import random


# =========================
# 1. ПРЕПОДАВАТЕЛЬ
# =========================

TEACHER_EMAIL = "teacher@example.com"

teacher = User.objects.filter(
    email=TEACHER_EMAIL,
    profile__role="teacher"
).first()

if teacher is None:
    raise Exception("Преподаватель с таким email не найден или у него не роль teacher.")


# =========================
# 2. СОЗДАНИЕ ТЕСТА
# =========================

TEST_TITLE = "Основы гипертекстовой разметки"

Test.objects.filter(title=TEST_TITLE).delete()

test = Test.objects.create(
    title=TEST_TITLE,
    description=(
        "Итоговый тест по дисциплине ОП.12 «Основы гипертекстовой разметки». "
        "Проверяются знания по HTML, структуре HTML-документа, гиперссылкам, таблицам, "
        "формам, CSS, JavaScript, DOM, DHTML, XML, cookies, HTTP-заголовкам и публикации сайта."
    ),
    time_limit=80,
    created_by=teacher
)


# =========================
# 3. ДАННЫЕ ТЕСТА
# type = "single"    — один правильный ответ
# type = "multiple"  — два правильных ответа
# type = "text"      — текстовый ответ
# =========================

questions_data = [
    {
        "text": "Что такое HTML?",
        "type": "single",
        "answers": [
            ("Язык гипертекстовой разметки для создания структуры веб-страниц", True),
            ("Язык управления базами данных", False),
            ("Операционная система", False),
            ("Графический редактор", False),
        ],
    },
    {
        "text": "Какие понятия относятся к web-программированию?",
        "type": "multiple",
        "answers": [
            ("HTML", True),
            ("CSS", True),
            ("BIOS", False),
            ("Файловая система NTFS", False),
        ],
    },
    {
        "text": "Как расшифровывается HTML?",
        "type": "text",
        "correct_text": "HyperText Markup Language",
    },
    {
        "text": "Для чего используется тег <html>?",
        "type": "single",
        "answers": [
            ("Для обозначения корневого элемента HTML-документа", True),
            ("Для создания только изображения", False),
            ("Для подключения базы данных", False),
            ("Для запуска операционной системы", False),
        ],
    },
    {
        "text": "Какие основные части содержит HTML-документ?",
        "type": "multiple",
        "answers": [
            ("head", True),
            ("body", True),
            ("print", False),
            ("server", False),
        ],
    },
    {
        "text": "Как называется часть HTML-документа, в которой размещается видимое содержимое страницы?",
        "type": "text",
        "correct_text": "body",
    },
    {
        "text": "Для чего используется тег <head>?",
        "type": "single",
        "answers": [
            ("Для хранения служебной информации о документе", True),
            ("Для вывода основного текста страницы", False),
            ("Для создания таблицы", False),
            ("Для отправки формы", False),
        ],
    },
    {
        "text": "Какие элементы могут находиться внутри <head>?",
        "type": "multiple",
        "answers": [
            ("title", True),
            ("meta", True),
            ("p", False),
            ("table", False),
        ],
    },
    {
        "text": "Какой тег задаёт заголовок страницы во вкладке браузера?",
        "type": "text",
        "correct_text": "title",
    },
    {
        "text": "Для чего используется тег <p>?",
        "type": "single",
        "answers": [
            ("Для создания абзаца текста", True),
            ("Для создания таблицы", False),
            ("Для подключения JavaScript", False),
            ("Для загрузки сайта на хостинг", False),
        ],
    },

    {
        "text": "Какие теги используются для заголовков в HTML?",
        "type": "multiple",
        "answers": [
            ("h1", True),
            ("h2", True),
            ("div", False),
            ("form", False),
        ],
    },
    {
        "text": "Какой тег используется для переноса строки?",
        "type": "text",
        "correct_text": "br",
    },
    {
        "text": "Для чего используется тег <a>?",
        "type": "single",
        "answers": [
            ("Для создания гиперссылки", True),
            ("Для создания строки таблицы", False),
            ("Для описания цвета страницы", False),
            ("Для запуска цикла JavaScript", False),
        ],
    },
    {
        "text": "Какие атрибуты часто используются в HTML?",
        "type": "multiple",
        "answers": [
            ("href", True),
            ("src", True),
            ("while", False),
            ("return", False),
        ],
    },
    {
        "text": "Какой атрибут указывает адрес перехода в гиперссылке?",
        "type": "text",
        "correct_text": "href",
    },
    {
        "text": "Для чего используется тег <img>?",
        "type": "single",
        "answers": [
            ("Для вставки изображения на страницу", True),
            ("Для создания формы", False),
            ("Для создания заголовка", False),
            ("Для создания массива", False),
        ],
    },
    {
        "text": "Какие атрибуты относятся к тегу изображения?",
        "type": "multiple",
        "answers": [
            ("src", True),
            ("alt", True),
            ("method", False),
            ("action", False),
        ],
    },
    {
        "text": "Какой атрибут изображения хранит путь к файлу картинки?",
        "type": "text",
        "correct_text": "src",
    },
    {
        "text": "Для чего используется тег <ul>?",
        "type": "single",
        "answers": [
            ("Для создания маркированного списка", True),
            ("Для создания нумерованного списка", False),
            ("Для создания формы", False),
            ("Для подключения CSS-файла", False),
        ],
    },
    {
        "text": "Какие теги относятся к спискам HTML?",
        "type": "multiple",
        "answers": [
            ("ul", True),
            ("ol", True),
            ("table", False),
            ("input", False),
        ],
    },

    {
        "text": "Какой тег используется для отдельного пункта списка?",
        "type": "text",
        "correct_text": "li",
    },
    {
        "text": "Для чего используется тег <table>?",
        "type": "single",
        "answers": [
            ("Для создания таблицы", True),
            ("Для создания формы входа", False),
            ("Для подключения скрипта", False),
            ("Для создания гиперссылки", False),
        ],
    },
    {
        "text": "Какие теги относятся к структуре HTML-таблицы?",
        "type": "multiple",
        "answers": [
            ("tr", True),
            ("td", True),
            ("meta", False),
            ("body", False),
        ],
    },
    {
        "text": "Какой тег обозначает строку таблицы?",
        "type": "text",
        "correct_text": "tr",
    },
    {
        "text": "Для чего используется тег <form>?",
        "type": "single",
        "answers": [
            ("Для создания формы ввода и отправки данных", True),
            ("Для создания заголовка документа", False),
            ("Для создания таблицы истинности", False),
            ("Для форматирования жёсткого диска", False),
        ],
    },
    {
        "text": "Какие элементы могут использоваться внутри HTML-формы?",
        "type": "multiple",
        "answers": [
            ("input", True),
            ("button", True),
            ("head", False),
            ("title", False),
        ],
    },
    {
        "text": "Какой тег используется для поля ввода в форме?",
        "type": "text",
        "correct_text": "input",
    },
    {
        "text": "Для чего используется атрибут method в форме?",
        "type": "single",
        "answers": [
            ("Для указания способа передачи данных формы", True),
            ("Для задания цвета текста", False),
            ("Для создания нового тега", False),
            ("Для подключения изображения", False),
        ],
    },
    {
        "text": "Какие методы отправки формы часто используются?",
        "type": "multiple",
        "answers": [
            ("GET", True),
            ("POST", True),
            ("HTML", False),
            ("CSS", False),
        ],
    },
    {
        "text": "Какой атрибут формы указывает адрес, куда отправляются данные?",
        "type": "text",
        "correct_text": "action",
    },

    {
        "text": "Что такое CSS?",
        "type": "single",
        "answers": [
            ("Каскадные таблицы стилей для оформления веб-страниц", True),
            ("Язык создания баз данных", False),
            ("Система охлаждения процессора", False),
            ("Программа для архивации файлов", False),
        ],
    },
    {
        "text": "Какие способы подключения CSS существуют?",
        "type": "multiple",
        "answers": [
            ("Внешний CSS-файл", True),
            ("Встроенный стиль внутри HTML-документа", True),
            ("Через BIOS", False),
            ("Через форматирование диска", False),
        ],
    },
    {
        "text": "Какой тег используется для подключения внешнего CSS-файла?",
        "type": "text",
        "correct_text": "link",
    },
    {
        "text": "Для чего используется свойство color в CSS?",
        "type": "single",
        "answers": [
            ("Для задания цвета текста", True),
            ("Для задания адреса ссылки", False),
            ("Для отправки формы", False),
            ("Для создания массива", False),
        ],
    },
    {
        "text": "Какие CSS-свойства относятся к оформлению текста?",
        "type": "multiple",
        "answers": [
            ("font-size", True),
            ("color", True),
            ("method", False),
            ("action", False),
        ],
    },
    {
        "text": "Какое CSS-свойство задаёт цвет фона элемента?",
        "type": "text",
        "correct_text": "background-color",
    },
    {
        "text": "Для чего используется свойство border в CSS?",
        "type": "single",
        "answers": [
            ("Для задания границы элемента", True),
            ("Для создания формы", False),
            ("Для открытия нового окна", False),
            ("Для отправки cookie", False),
        ],
    },
    {
        "text": "Какие CSS-свойства относятся к блочной модели?",
        "type": "multiple",
        "answers": [
            ("margin", True),
            ("padding", True),
            ("href", False),
            ("src", False),
        ],
    },
    {
        "text": "Какое CSS-свойство задаёт внутренний отступ элемента?",
        "type": "text",
        "correct_text": "padding",
    },
    {
        "text": "Для чего используется CSS-свойство position?",
        "type": "single",
        "answers": [
            ("Для управления позиционированием элемента на странице", True),
            ("Для создания заголовка документа", False),
            ("Для подключения базы данных", False),
            ("Для проверки HTML-кода на ошибки", False),
        ],
    },

    {
        "text": "Что такое JavaScript?",
        "type": "single",
        "answers": [
            ("Язык программирования для создания интерактивности на веб-страницах", True),
            ("Только язык разметки таблиц", False),
            ("Формат изображения", False),
            ("Операционная система", False),
        ],
    },
    {
        "text": "Какие возможности даёт JavaScript на веб-странице?",
        "type": "multiple",
        "answers": [
            ("Обработка событий", True),
            ("Проверка данных формы", True),
            ("Физическое подключение монитора", False),
            ("Форматирование жёсткого диска", False),
        ],
    },
    {
        "text": "Какой тег используется для подключения или написания JavaScript-кода?",
        "type": "text",
        "correct_text": "script",
    },
    {
        "text": "Что такое событие в JavaScript?",
        "type": "single",
        "answers": [
            ("Действие пользователя или браузера, на которое может реагировать скрипт", True),
            ("Только ошибка в HTML-коде", False),
            ("Название CSS-файла", False),
            ("Тип таблицы", False),
        ],
    },
    {
        "text": "Какие события могут обрабатываться JavaScript?",
        "type": "multiple",
        "answers": [
            ("click", True),
            ("submit", True),
            ("table", False),
            ("style", False),
        ],
    },
    {
        "text": "Как называется объектная модель документа, через которую JavaScript работает со страницей?",
        "type": "text",
        "correct_text": "DOM",
    },
    {
        "text": "Для чего используется DOM?",
        "type": "single",
        "answers": [
            ("Для доступа к элементам HTML-документа и изменения их свойств", True),
            ("Для хранения файлов на сервере", False),
            ("Для выбора хостинга", False),
            ("Для создания доменного имени", False),
        ],
    },
    {
        "text": "Какие конструкции относятся к JavaScript?",
        "type": "multiple",
        "answers": [
            ("if", True),
            ("for", True),
            ("body", False),
            ("href", False),
        ],
    },
    {
        "text": "Как называется блок кода, который можно вызвать по имени?",
        "type": "text",
        "correct_text": "функция",
    },
    {
        "text": "Для чего используется условный оператор if?",
        "type": "single",
        "answers": [
            ("Для выполнения кода в зависимости от условия", True),
            ("Для создания HTML-таблицы", False),
            ("Для подключения CSS", False),
            ("Для задания адреса ссылки", False),
        ],
    },

    {
        "text": "Какие структуры данных используются в JavaScript?",
        "type": "multiple",
        "answers": [
            ("Массив", True),
            ("Объект", True),
            ("Блок питания", False),
            ("Фреймворк как устройство", False),
        ],
    },
    {
        "text": "Как называется структура данных для хранения упорядоченного набора значений?",
        "type": "text",
        "correct_text": "массив",
    },
    {
        "text": "Для чего используются циклы в JavaScript?",
        "type": "single",
        "answers": [
            ("Для многократного выполнения команд", True),
            ("Для создания только HTML-заголовка", False),
            ("Для изменения адреса сайта вручную", False),
            ("Для подключения клавиатуры", False),
        ],
    },
    {
        "text": "Какие встроенные объекты JavaScript изучаются при создании сценариев сайта?",
        "type": "multiple",
        "answers": [
            ("Date", True),
            ("Math", True),
            ("HTML", False),
            ("HTTP", False),
        ],
    },
    {
        "text": "Какой встроенный объект JavaScript используется для работы с датой и временем?",
        "type": "text",
        "correct_text": "Date",
    },
    {
        "text": "Что такое cookies?",
        "type": "single",
        "answers": [
            ("Небольшие данные, сохраняемые браузером для сайта", True),
            ("Только HTML-теги", False),
            ("Файлы операционной системы Windows", False),
            ("Тип монитора", False),
        ],
    },
    {
        "text": "Какие задачи могут решаться с помощью cookies?",
        "type": "multiple",
        "answers": [
            ("Хранение пользовательских настроек", True),
            ("Сохранение информации о сеансе", True),
            ("Подключение принтера", False),
            ("Создание процессора", False),
        ],
    },
    {
        "text": "Как называется динамическое изменение HTML и CSS с помощью сценариев?",
        "type": "text",
        "correct_text": "DHTML",
    },
    {
        "text": "Для чего используется XML?",
        "type": "single",
        "answers": [
            ("Для хранения и передачи структурированных данных", True),
            ("Для оформления цвета текста", False),
            ("Для создания только кнопок", False),
            ("Для управления питанием компьютера", False),
        ],
    },
    {
        "text": "Какие действия относятся к публикации сайта?",
        "type": "multiple",
        "answers": [
            ("Выбор доменного имени", True),
            ("Выбор хостинга", True),
            ("Удаление HTML-документа", False),
            ("Отключение браузера", False),
        ],
    },
]


# =========================
# 4. РАНДОМНЫЙ ПОРЯДОК ВОПРОСОВ
# =========================

random.shuffle(questions_data)


# =========================
# 5. СОЗДАНИЕ ВОПРОСОВ И ОТВЕТОВ
# =========================

for q_data in questions_data:
    if q_data["type"] == "text":
        Question.objects.create(
            test=test,
            text=q_data["text"],
            question_type="text",
            correct_text=q_data["correct_text"]
        )
    else:
        question = Question.objects.create(
            test=test,
            text=q_data["text"],
            question_type="multiple"
        )

        answers = q_data["answers"][:]
        random.shuffle(answers)

        for answer_text, is_correct in answers:
            Answer.objects.create(
                question=question,
                text=answer_text,
                is_correct=is_correct
            )


# =========================
# 6. ПРОВЕРКА
# =========================

questions_count = Question.objects.filter(test=test).count()
answers_count = Answer.objects.filter(question__test=test).count()
text_questions_count = Question.objects.filter(test=test, question_type="text").count()
choice_questions_count = Question.objects.filter(test=test).exclude(question_type="text").count()

print("Готово!")
print("Тест:", test.title)
print("Владелец теста:", test.created_by.email)
print("Вопросов всего:", questions_count)
print("Вопросов с вариантами:", choice_questions_count)
print("Текстовых вопросов:", text_questions_count)
print("Вариантов ответов создано:", answers_count)

first_choice_question = Question.objects.filter(test=test).exclude(question_type="text").first()

if first_choice_question:
    print("Проверка первого вопроса с вариантами:")
    print(first_choice_question.text)
    for answer in first_choice_question.answers.all():
        print("-", answer.text, "| правильный:", answer.is_correct)