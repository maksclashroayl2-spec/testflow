from django.contrib import admin
from .models import Test, Question, Answer


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4  # сразу 4 варианта ответа


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True  # можно перейти в вопрос


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title',)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test')
    inlines = [AnswerInline]



