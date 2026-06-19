from django.contrib import admin
from .models import Test, Question, Answer, Profile, Result, StudentGroup, TestCategory


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(TestCategory)
class TestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name',)


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'is_active', 'visibility', 'time_limit', 'created_at')
    list_filter = ('is_active', 'visibility', 'category', 'created_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('assigned_groups',)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test', 'question_type')
    list_filter = ('question_type',)
    inlines = [AnswerInline]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'role', 'student_group')
    list_filter = ('role', 'student_group')


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'test', 'score', 'percent', 'grade', 'grading_status', 'created_at')
    list_filter = ('grade', 'grading_status', 'created_at')
    search_fields = ('student__email', 'test__title')
