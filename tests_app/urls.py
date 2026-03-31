from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    # ===================== ГЛАВНАЯ =====================
    path('', views.home, name='home'),

    # ===================== АВТОРИЗАЦИЯ =====================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/', views.verify_email_view, name='verify_email'),

    # ===================== ТЕСТИРОВАНИЕ =====================
    path('tests/', views.tests_list, name='tests_list'),
    path('start/<int:test_id>/', views.start_test, name='start_test'),
    path('question/', views.question_view, name='question'),
    path('result/', views.result_view, name='result'),

    # ===================== ПРОФИЛЬ =====================
    path('profile/', views.profile, name='profile'),
    path('review/<int:result_id>/', views.review_test, name='review_test'),

    # ===================== ПРЕПОДАВАТЕЛЬ =====================
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/test/create/', views.create_test, name='create_test'),
    path('teacher/test/<int:test_id>/edit/', views.edit_test, name='edit_test'),
    path('teacher/test/<int:test_id>/delete/', views.delete_test, name='delete_test'),
    path('teacher/test/<int:test_id>/results/', views.test_results, name='test_results'),
    path('teacher/edit/', views.edit_teacher_profile, name='edit_teacher_profile'),

    # ===================== ВОПРОСЫ =====================
    path('teacher/test/<int:test_id>/question/add/', views.add_question, name='add_question'),
    path('teacher/question/<int:question_id>/delete/', views.delete_question, name='delete_question'),

    # ===================== ОТВЕТЫ =====================
    path('teacher/question/<int:question_id>/answers/add/', views.add_answers, name='add_answers'),
    path('teacher/answer/<int:answer_id>/delete/', views.delete_answer, name='delete_answer'),
   
    # Сброс пароля
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='tests_app/password_reset.html'
    ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='tests_app/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='tests_app/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='tests_app/password_reset_complete.html'
    ), name='password_reset_complete'),
]
