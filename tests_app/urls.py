from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    # ГЛАВНАЯ
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('help/', views.help_page, name='help'),

    # АВТОРИЗАЦИЯ
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/', views.verify_email_view, name='verify_email'),

    # ТЕСТИРОВАНИЕ 
    path('tests/', views.tests_list, name='tests_list'),
    path('test/<int:test_id>/', views.test_detail, name='test_detail'),
    path('start/<int:test_id>/', views.start_test, name='start_test'),
    path('question/', views.question_view, name='question'),
    path('result/', views.result_view, name='result'),

    # ПРОФИЛЬ
    path('profile/', views.profile, name='profile'),
    path('review/<int:result_id>/', views.review_test, name='review_test'),

    # ПРЕПОДАВАТЕЛЬ
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/bulk-actions/', views.bulk_test_actions, name='bulk_test_actions'),
    path('teacher/export-results/', views.export_all_results, name='export_all_results'),
    path('teacher/test/<int:test_id>/save-template/', views.save_test_template, name='save_test_template'),
    path('teacher/template/<int:template_id>/use/', views.use_test_template, name='use_test_template'),
    path('teacher/template/<int:template_id>/delete/', views.delete_test_template, name='delete_test_template'),
    path('teacher/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('teacher/activity-log/export/', views.export_activity_log, name='export_activity_log'),
    path('teacher/tests/', views.teacher_tests, name='teacher_tests'),
    path('teacher/profile/', views.teacher_profile, name='teacher_profile'),
    path('teacher/groups/', views.teacher_groups, name='teacher_groups'),
    path('teacher/groups/<int:group_id>/', views.group_detail, name='group_detail'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/test/create/', views.create_test, name='create_test'),
    path('teacher/test/<int:test_id>/edit/', views.edit_test, name='edit_test'),
    path('teacher/test/<int:test_id>/delete/', views.delete_test, name='delete_test'),
    path('teacher/test/<int:test_id>/duplicate/', views.duplicate_test, name='duplicate_test'),
    path('teacher/test/<int:test_id>/toggle-status/', views.toggle_test_status, name='toggle_test_status'),
    path('teacher/test/<int:test_id>/results/', views.test_results, name='test_results'),
    path('teacher/test/<int:test_id>/results/export/', views.export_test_results, name='export_test_results'),
    path('teacher/test/<int:test_id>/import/', views.import_test_json, name='import_test_json'),
    path('teacher/test/<int:test_id>/export/', views.export_test_json, name='export_test_json'),
    path('teacher/edit/', views.edit_teacher_profile, name='edit_teacher_profile'),

    # ВОПРОСЫ
    path('teacher/test/<int:test_id>/questions/', views.manage_questions, name='manage_questions'),
    path('teacher/question/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('teacher/test/<int:test_id>/question/add/', views.add_question, name='add_question'),
    path('teacher/question/<int:question_id>/delete/', views.delete_question, name='delete_question'),

    # ОТВЕТЫ 
    path('teacher/question/<int:question_id>/answers/add/', views.add_answers, name='add_answers'),
    path('teacher/answer/<int:answer_id>/delete/', views.delete_answer, name='delete_answer'),
   
   # СБРОС ПАРОЛЯ 
    path('password-reset/', auth_views.PasswordResetView.as_view(
    template_name='tests_app/password_reset.html',
    email_template_name='tests_app/password_reset_email.html',
    subject_template_name='tests_app/password_reset_subject.txt',
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
    path(
    'teacher/result/<int:result_id>/review/',
    views.teacher_review_result,
    name='teacher_review_result'
    ),
    path(
    'teacher/result/<int:result_id>/delete/',
    views.delete_result,
    name='delete_result'
),

    # PDF ЭКСПОРТ
    path('teacher/test/<int:test_id>/results/pdf/', views.export_test_results_pdf, name='export_test_results_pdf'),
    path('teacher/result/<int:result_id>/pdf/', views.export_student_result_pdf, name='export_student_result_pdf'),
]
