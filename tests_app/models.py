from django.db import models
from django.contrib.auth.models import User


# ================== ПРОФИЛЬ ==================
class Profile(models.Model):

    ROLE_CHOICES = (
        ('student', 'Студент'),
        ('teacher', 'Преподаватель'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    full_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Имя"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student'
    )

    avatar = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.png',
        blank=True,
        null=True
    )

    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} ({self.get_role_display()})"


# ================== ТЕСТ ==================
class Test(models.Model):

    title = models.CharField(
        max_length=200,
        verbose_name="Название теста"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание теста"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_tests',
        verbose_name="Преподаватель"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    time_limit = models.PositiveIntegerField(
        default=10,
        verbose_name="Лимит времени (в минутах)"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"

    def __str__(self):
        return f"{self.title} — {self.created_by.username}"


# ================== ВОПРОС ==================
class Question(models.Model):

    QUESTION_TYPES = (
        ('multiple', 'С выбором ответа'),
        ('text', 'Письменный ответ'),
    )

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    text = models.TextField(
        verbose_name="Текст вопроса"
    )

    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='multiple',
        verbose_name="Тип вопроса"
    )

    # Для письменных вопросов
    correct_text = models.TextField(
        blank=True,
        null=True,
        verbose_name="Правильный текстовый ответ"
    )

    def __str__(self):
        return f"Вопрос к тесту '{self.test.title}'"


# ================== ОТВЕТ ==================
class Answer(models.Model):

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    text = models.CharField(
        max_length=300,
        verbose_name="Ответ"
    )

    is_correct = models.BooleanField(
        default=False,
        verbose_name="Правильный ответ"
    )

    def __str__(self):
        return f"{self.text} ({'✔' if self.is_correct else '✘'})"


# ================== РЕЗУЛЬТАТ ==================
class Result(models.Model):

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='results'
    )

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='results'
    )

    score = models.FloatField(verbose_name="Баллы")
    percent = models.FloatField(verbose_name="Процент")
    grade = models.CharField(max_length=2, verbose_name="Оценка")

    created_at = models.DateTimeField(auto_now_add=True)

    # {question_id: [answers]}
    answers = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.username} — {self.test.title} ({self.percent}%)"