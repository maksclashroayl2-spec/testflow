from django.db import models
from django.contrib.auth.models import User


class TestCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")

    class Meta:
        ordering = ['name']
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class StudentGroup(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название группы")
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='student_groups',
        verbose_name="Преподаватель",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [['name', 'created_by']]
        verbose_name = "Группа"
        verbose_name_plural = "Группы"

    def __str__(self):
        return self.name


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
        blank=True,
        null=True,
        verbose_name="Аватар"
    )

    bio = models.TextField(
        blank=True,
        null=True
    )

    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='students',
        verbose_name="Группа",
    )

    def __str__(self):
        return f"{self.user.email} ({self.get_role_display()})"


class Test(models.Model):

    VISIBILITY_CHOICES = (
        ('all', 'Для всех студентов'),
        ('groups', 'Только для выбранных групп'),
    )

    title = models.CharField(
        max_length=200,
        verbose_name="Название теста"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание теста"
    )

    category = models.ForeignKey(
        TestCategory,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='tests',
        verbose_name="Категория",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_tests',
        verbose_name="Преподаватель"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        db_index=True,
    )

    time_limit = models.PositiveIntegerField(
        default=10,
        verbose_name="Лимит времени (в минутах)"
    )

    is_active = models.BooleanField(
        default=False,
        verbose_name="Активен",
        db_index=True,
    )

    max_attempts = models.PositiveIntegerField(
        default=1,
        verbose_name="Количество попыток"
    )

    available_from = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Доступен с"
    )

    available_until = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Доступен до"
    )

    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='all',
        verbose_name="Видимость",
    )

    assigned_groups = models.ManyToManyField(
        StudentGroup,
        blank=True,
        related_name='assigned_tests',
        verbose_name="Группы",
    )

    shuffle_questions = models.BooleanField(
        default=False,
        verbose_name="Перемешивать вопросы",
    )

    shuffle_answers = models.BooleanField(
        default=False,
        verbose_name="Перемешивать ответы",
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"

    def __str__(self):
        teacher_name = (
            self.created_by.profile.full_name
            if hasattr(self.created_by, 'profile') and self.created_by.profile.full_name
            else self.created_by.email
        )
        return f"{self.title} — {teacher_name}"


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

    image = models.ImageField(
        upload_to='question_images/',
        blank=True,
        null=True,
        verbose_name="Изображение к вопросу"
    )

    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='multiple',
        verbose_name="Тип вопроса"
    )

    correct_text = models.TextField(
        blank=True,
        null=True,
        verbose_name="Правильный текстовый ответ"
    )

    def __str__(self):
        return f"Вопрос к тесту '{self.test.title}'"


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


class Result(models.Model):

    GRADING_STATUS_CHOICES = (
        ('graded', 'Проверено'),
        ('pending_review', 'На проверке'),
    )

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

    score = models.FloatField(
        verbose_name="Баллы"
    )

    percent = models.FloatField(
        verbose_name="Процент"
    )

    grade = models.CharField(
        max_length=2,
        verbose_name="Оценка"
    )

    grading_status = models.CharField(
        max_length=20,
        choices=GRADING_STATUS_CHOICES,
        default='graded',
        verbose_name="Статус проверки",
        db_index=True,
    )

    text_reviews = models.JSONField(
        default=dict,
        verbose_name="Проверка текстовых ответов",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    answers = models.JSONField(
        default=dict
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'test']),
            models.Index(fields=['test', 'created_at']),
        ]

    def __str__(self):
        student_name = (
            self.student.profile.full_name
            if hasattr(self.student, 'profile') and self.student.profile.full_name
            else self.student.email
        )
        return f"{student_name} — {self.test.title} ({self.percent}%)"


class TestTemplate(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название шаблона")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_templates', verbose_name="Преподаватель")
    template_data = models.JSONField(verbose_name="Данные шаблона")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Шаблон теста"
        verbose_name_plural = "Шаблоны тестов"

    def __str__(self):
        return self.title


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Текст")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=300, blank=True, verbose_name="Ссылка")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} для {self.user.email}"


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=300, verbose_name="Действие")
    details = models.TextField(blank=True, verbose_name="Детали")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Журнал действий"
        verbose_name_plural = "Журналы действий"
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.email}: {self.action}"
