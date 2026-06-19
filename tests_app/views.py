from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Avg, Count
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta
from .models import Test, Question, Answer, Result, Profile, StudentGroup, TestCategory, TestTemplate, Notification, ActivityLog
from .forms import TestForm, StudentGroupForm
from .grading import calculate_score, build_initial_text_reviews, apply_text_review_updates
from .access import student_can_access_test, get_visible_tests_for_student
from .import_export import export_test_to_dict, import_questions_from_dict, parse_test_json_file
import random
import secrets
import json
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import reverse
import csv
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django_ratelimit.decorators import ratelimit
from django.core.cache import cache
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme
logger = logging.getLogger(__name__)

ALLOWED_UPLOAD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


def validate_uploaded_file(uploaded_file):
    if not uploaded_file:
        return
    ext = '.' + uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(f"Допустимые форматы: {', '.join(ALLOWED_UPLOAD_EXTENSIONS)}")
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("Файл слишком большой (макс. 5 МБ)")


def log_activity(user, action, details=''):
    ActivityLog.objects.create(user=user, action=action, details=details)


def create_notification(user, title, message, link=''):
    Notification.objects.create(user=user, title=title, message=message, link=link)


#ГЛАВНАЯ 

def home(request):
    stats = cache.get('home_stats')
    if stats is None:
        stats = {
            'users': User.objects.count(),
            'tests': Test.objects.filter(is_active=True).count(),
            'attempts': Result.objects.count(),
        }
        cache.set('home_stats', stats, 300)
    return render(request, 'tests_app/home.html', stats)


def about(request):
    return render(request, 'tests_app/about.html')

def help_page(request):
    return render(request, 'tests_app/help.html')


def tests_list(request):
    if request.user.is_authenticated and request.user.profile.role == 'student':
        tests_qs = get_visible_tests_for_student(request.user)
    else:
        tests_qs = Test.objects.filter(is_active=True)

    category_id = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    if category_id.isdigit():
        tests_qs = tests_qs.filter(category_id=int(category_id))

    if query:
        tests_qs = tests_qs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )

    tests_qs = tests_qs.select_related('category', 'created_by__profile').annotate(
        questions_count=Count('questions'),
    ).order_by('-created_at')

    tests = list(tests_qs)
    user_results = {}

    if request.user.is_authenticated and request.user.profile.role == 'student':
        result_rows = Result.objects.filter(
            student=request.user,
            test_id__in=[t.id for t in tests],
        ).order_by('test_id', '-created_at')

        for row in result_rows:
            if row.test_id not in user_results:
                user_results[row.test_id] = row

    filtered_tests = []

    for test in tests:
        is_available, availability_message = get_test_availability(test)
        test.is_available_by_date = is_available
        test.availability_message = availability_message
        test.last_result = user_results.get(test.id)

        if status_filter == 'available':
            if not is_available or test.last_result:
                continue
        elif status_filter == 'completed':
            if not test.last_result or test.last_result.grading_status == 'pending_review':
                continue
        elif status_filter == 'pending':
            if not test.last_result or test.last_result.grading_status != 'pending_review':
                continue

        filtered_tests.append(test)

    paginator = Paginator(filtered_tests, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'tests_app/tests_list.html', {
        'tests': page_obj,
        'page_obj': page_obj,
        'categories': TestCategory.objects.all(),
        'selected_category': category_id,
        'status_filter': status_filter,
        'query': query,
    })

def get_test_availability(test):
    now = timezone.now()

    if test.available_from and now < test.available_from:
        available_from_local = timezone.localtime(test.available_from)
        return False, f"Тест будет доступен с {available_from_local.strftime('%d.%m.%Y %H:%M')}."

    if test.available_until and now > test.available_until:
        available_until_local = timezone.localtime(test.available_until)
        return False, f"Срок прохождения теста завершён {available_until_local.strftime('%d.%m.%Y %H:%M')}."

    return True, "Тест доступен для прохождения."

#ТЕСТИРОВАНИЕ

@login_required
def test_detail(request, test_id):
    if request.user.profile.role != 'student':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id)

    if not test.is_active:
        messages.warning(request, "Этот тест сейчас скрыт преподавателем.")
        return redirect('tests_list')

    if not student_can_access_test(request.user, test):
        messages.warning(request, "Этот тест недоступен для вашей группы.")
        return redirect('tests_list')

    is_available, availability_message = get_test_availability(test)

    questions = test.questions.all()

    q_stats = questions.aggregate(
        total=Count('id'),
        text_count=Count('id', filter=Q(question_type='text')),
    )
    total_questions = q_stats['total']
    text_questions = q_stats['text_count']
    choice_questions = total_questions - text_questions

    attempts_used = Result.objects.filter(
        student=request.user,
        test=test
    ).count()

    attempts_left = None
    attempts_limit_reached = False

    if test.max_attempts > 0:
        attempts_left = max(0, test.max_attempts - attempts_used)
        attempts_limit_reached = attempts_used >= test.max_attempts

    return render(request, 'tests_app/test_detail.html', {
        'test': test,
        'total_questions': total_questions,
        'text_questions': text_questions,
        'choice_questions': choice_questions,
        'attempts_used': attempts_used,
        'attempts_left': attempts_left,
        'attempts_limit_reached': attempts_limit_reached,
        'is_available': is_available,
        'availability_message': availability_message,
    })

@login_required
def start_test(request, test_id):
    if request.user.profile.role != 'student':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id)

    if not test.is_active:
        messages.warning(request, "Этот тест сейчас скрыт преподавателем.")
        return redirect('tests_list')

    is_available, availability_message = get_test_availability(test)

    if not is_available:
        messages.warning(request, availability_message)
        return redirect('test_detail', test_id=test.id)

    attempts_used = Result.objects.filter(
        student=request.user,
        test=test
    ).count()

    if test.max_attempts > 0 and attempts_used >= test.max_attempts:
        messages.warning(request, "Лимит попыток для этого теста исчерпан.")
        return redirect('test_detail', test_id=test.id)

    if not test.questions.exists():
        messages.warning(request, "Этот тест пока не содержит вопросов.")
        return redirect('test_detail', test_id=test.id)

    if not student_can_access_test(request.user, test):
        messages.warning(request, "Этот тест недоступен для вашей группы.")
        return redirect('tests_list')

    request.session.pop('test_id', None)
    request.session.pop('answers', None)
    request.session.pop('index', None)
    request.session.pop('start_time', None)
    request.session.pop('end_time', None)
    request.session.pop('question_order', None)
    request.session.pop('current_result_id', None)

    question_ids = list(test.questions.values_list('id', flat=True))
    if test.shuffle_questions:
        random.shuffle(question_ids)

    start_time = timezone.now()
    end_time = start_time + timedelta(minutes=test.time_limit)

    request.session['test_id'] = test.id
    request.session['answers'] = {}
    request.session['index'] = 0
    request.session['start_time'] = start_time.isoformat()
    request.session['end_time'] = end_time.isoformat()
    request.session['question_order'] = question_ids

    return redirect('question')


@login_required
def question_view(request):
    if request.user.profile.role != 'student':
        return redirect('home')

    test_id = request.session.get('test_id')
    answers_store = request.session.get('answers', {})
    index = request.session.get('index', 0)
    end_time_str = request.session.get('end_time')

    if not test_id:
        messages.warning(request, "Сначала начните тест.")
        return redirect('tests_list')

    test = get_object_or_404(Test, id=test_id)

    if not test.is_active:
        messages.warning(request, "Этот тест сейчас скрыт преподавателем.")
        return redirect('tests_list')

    questions = list(test.questions.prefetch_related('answers').all())
    question_order = request.session.get('question_order') or [q.id for q in questions]

    if question_order:
        order_map = {qid: idx for idx, qid in enumerate(question_order)}
        questions.sort(key=lambda q: order_map.get(q.id, 9999))

    if not questions:
        messages.warning(request, "В этом тесте пока нет вопросов.")
        return redirect('tests_list')

    if index >= len(questions):
        return redirect('result')

    end_time = None

    if end_time_str:
        end_time = timezone.datetime.fromisoformat(end_time_str)

        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time, timezone.get_current_timezone())

        if timezone.now() >= end_time:
            messages.warning(request, "Время на прохождение теста истекло.")
            return redirect('result')
    else:
        messages.warning(request, "Время теста не найдено. Начните тест заново.")
        return redirect('test_detail', test_id=test.id)

    question = questions[index]

    correct_count = sum(1 for a in question.answers.all() if a.is_correct)
    is_multiple = correct_count > 1

    if request.method == 'POST':
        action = request.POST.get('action')

        if question.question_type == 'text':
            text_answer = request.POST.get('text_answer', '').strip()
            if text_answer:
                answers_store[str(question.id)] = text_answer
            else:
                answers_store.pop(str(question.id), None)
        else:
            selected = request.POST.getlist('answers')
            if selected:
                answers_store[str(question.id)] = selected
            else:
                answers_store.pop(str(question.id), None)

        request.session['answers'] = answers_store
        request.session.modified = True

        if action == 'next':
            request.session['index'] = index + 1
        elif action == 'back':
            request.session['index'] = max(0, index - 1)
        elif action == 'goto':
            try:
                target = int(request.POST.get('target', index))
            except (ValueError, TypeError):
                target = index
            request.session['index'] = max(0, min(target, len(questions) - 1))

        return redirect('question')

    selected_answers = answers_store.get(str(question.id), [])
    selected_text_answer = answers_store.get(str(question.id), "")

    remaining_seconds = max(0, int((end_time - timezone.now()).total_seconds()))

    answers_qs = list(question.answers.all())
    if test.shuffle_answers and question.question_type != 'text':
        random.shuffle(answers_qs)

    answered_ids = [str(qid) for qid in question_order if str(qid) in answers_store]

    return render(request, 'tests_app/exam.html', {
        'test': test,
        'question': question,
        'answers': answers_qs,
        'index': index + 1,
        'total': len(questions),
        'is_multiple': is_multiple,
        'selected_answers': selected_answers,
        'selected_text_answer': selected_text_answer,
        'remaining_seconds': remaining_seconds,
        'question_ids': question_order,
        'answered_ids': answered_ids,
        'current_question_id': str(question.id),
    })

@login_required
def result_view(request):
    if request.user.profile.role != 'student':
        return redirect('home')

    existing_result_id = request.session.get('current_result_id')
    if existing_result_id:
        result = get_object_or_404(
            Result,
            id=existing_result_id,
            student=request.user,
        )
        return _render_result_page(request, result)

    test_id = request.session.get('test_id')
    answers = request.session.get('answers', {})

    if not test_id:
        return redirect('home')

    test = get_object_or_404(Test, id=test_id)
    text_reviews = build_initial_text_reviews(test, answers)
    metrics = calculate_score(test, answers, text_reviews)

    result = Result.objects.create(
        student=request.user,
        test=test,
        score=metrics['score'],
        percent=metrics['percent'],
        grade=metrics['grade'],
        grading_status=metrics['grading_status'],
        text_reviews=text_reviews,
        answers=answers,
    )

    request.session['current_result_id'] = result.id
    request.session.pop('test_id', None)
    request.session.pop('answers', None)
    request.session.pop('index', None)
    request.session.pop('start_time', None)
    request.session.pop('end_time', None)
    request.session.pop('question_order', None)

    cache.delete('home_stats')

    return _render_result_page(request, result, total_questions=test.questions.count())


def _render_result_page(request, result, total_questions=None):
    percent = result.percent
    status_text = (
        "На проверке преподавателем" if result.grading_status == 'pending_review' else
        "Отличный результат" if percent >= 85 else
        "Хороший результат" if percent >= 70 else
        "Минимальный проходной результат" if percent >= 50 else
        "Требуется повторная подготовка"
    )

    return render(request, 'tests_app/result.html', {
        'result': result,
        'test': result.test,
        'score': result.score,
        'total': total_questions if total_questions is not None else result.test.questions.count(),
        'percent': result.percent,
        'grade': result.grade,
        'status_text': status_text,
    })


#ПРОФИЛЬ

@login_required
def profile(request):
    profile = request.user.profile

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        if full_name is not None:
            profile.full_name = full_name.strip()

        bio = request.POST.get('bio')
        if bio is not None:
            profile.bio = bio.strip()

        if request.FILES.get('avatar'):
            try:
                validate_uploaded_file(request.FILES['avatar'])
                profile.avatar = request.FILES['avatar']
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect('profile')

        group_id = request.POST.get('student_group')
        if group_id:
            try:
                profile.student_group = StudentGroup.objects.get(id=int(group_id))
            except (StudentGroup.DoesNotExist, ValueError, TypeError):
                pass
        elif group_id == '':
            profile.student_group = None

        profile.save()
        return redirect('profile')

    if profile.role == 'teacher':
        return redirect('teacher_profile')

    results_qs = (
        Result.objects
        .filter(student=request.user)
        .select_related('test')
        .annotate(test_questions_count=Count('test__questions'))
        .order_by('-created_at')
    )

    total_tests = results_qs.count()

    avg_percent = round(
        results_qs.aggregate(avg=Avg('percent'))['avg'] or 0,
        1
    )

    best_result = results_qs.order_by('-percent').first()

    level = (
        "Эксперт" if avg_percent >= 85 else
        "Продвинутый" if avg_percent >= 70 else
        "Базовый" if avg_percent >= 50 else
        "Новичок"
    )

    grade_counts = dict(
        results_qs
        .values('grade')
        .annotate(cnt=Count('id'))
        .values_list('grade', 'cnt')
    )

    grade_5_count = grade_counts.get('5', 0)
    grade_4_count = grade_counts.get('4', 0)
    grade_3_count = grade_counts.get('3', 0)
    grade_2_count = grade_counts.get('2', 0)

    paginator = Paginator(results_qs, 10)
    results = paginator.get_page(request.GET.get('page'))

    notifications = Notification.objects.filter(user=request.user)[:10]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return render(request, 'tests_app/profile.html', {
        'profile': profile,
        'results': results,
        'page_obj': results,
        'student_groups': StudentGroup.objects.all().order_by('name'),
        'avg_percent': avg_percent,
        'total_tests': total_tests,
        'best_result': best_result,
        'level': level,
        'grade_5_count': grade_5_count,
        'grade_4_count': grade_4_count,
        'grade_3_count': grade_3_count,
        'grade_2_count': grade_2_count,
        'notifications': notifications,
        'unread_count': unread_count,
    })

#АВТОРИЗАЦИЯ

@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            messages.error(request, "Введите email и пароль")
            return redirect('login')

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Неверный email или пароль")
            return redirect('login')

        user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            messages.error(request, "Неверный email или пароль")
            return redirect('login')

        login(request, user)

        next_url = request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        if user.profile.role == 'teacher':
            return redirect('teacher_dashboard')

        return redirect('home')

    return render(request, 'tests_app/login.html')


@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def register_view(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        role = request.POST.get('role', 'student')
        secret = request.POST.get('teacher_secret', '').strip()

        if not full_name:
            messages.error(request, "Введите имя")
            return redirect('register')

        if not email:
            messages.error(request, "Введите email")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Пользователь с таким email уже существует")
            return redirect('register')

        if password != password2:
            messages.error(request, "Пароли не совпадают")
            return redirect('register')

        try:
            validate_password(password)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return redirect('register')

        if role == 'teacher' and secret != settings.TEACHER_SECRET_KEY:
            messages.error(request, "Неверный секретный код преподавателя")
            return redirect('register')

        code = str(secrets.randbelow(900000) + 100000)

        from django.contrib.auth.hashers import make_password
        request.session['pending_registration'] = {
            'full_name': full_name,
            'email': email,
            'password_hash': make_password(password),
            'role': role,
            'student_group_id': request.POST.get('student_group', '').strip(),
        }
        request.session['email_verification_code'] = code

        try:
            send_mail(
                subject='Код подтверждения TestFlow',
                message=f'Ваш код подтверждения: {code}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, "Код подтверждения отправлен на вашу почту")
        except Exception as e:
            logger.exception("Ошибка отправки email при регистрации")
            messages.warning(
                request,
                "Не удалось отправить письмо. Попробуйте позже."
            )

        return redirect('verify_email')

    return render(request, 'tests_app/register.html', {
        'student_groups': StudentGroup.objects.all().order_by('name'),
    })


def logout_view(request):
    logout(request)
    return redirect('home')


#ПРОСМОТР ТЕСТА 

@login_required
def review_test(request, result_id):
    result = get_object_or_404(Result, id=result_id, student=request.user)

    review_data = []

    for question in result.test.questions.prefetch_related('answers').all():
        if question.question_type == 'text':
            user_text = str(result.answers.get(str(question.id), "")).strip()
            correct_text = str(question.correct_text or "").strip()

            is_correct = (
                user_text.lower() == correct_text.lower()
                if user_text and correct_text
                else False
            )

            review_data.append({
                'question_text': question.text,
                'question_image': question.image,
                'question_type': 'text',
                'user_text': user_text,
                'correct_text': correct_text,
                'is_correct': is_correct,
                'status_label': 'Верно' if is_correct else 'Неверно',
                'status_class': 'status-correct' if is_correct else 'status-wrong',
            })

        else:
            selected_ids = result.answers.get(str(question.id), [])
            selected_ids = set(str(x) for x in selected_ids)

            correct_ids = set(
                str(a.id) for a in question.answers.all() if a.is_correct
            )

            if selected_ids == correct_ids:
                status_label = 'Верно'
                status_class = 'status-correct'
            elif selected_ids and selected_ids & correct_ids:
                status_label = 'Частично верно'
                status_class = 'status-partial'
            else:
                status_label = 'Неверно'
                status_class = 'status-wrong'

            answers_data = []

            for answer in question.answers.all():
                answer_id = str(answer.id)

                answers_data.append({
                    'id': answer.id,
                    'text': answer.text,
                    'is_correct': answer.is_correct,
                    'is_selected': answer_id in selected_ids,
                })

            review_data.append({
                'question_text': question.text,
                'question_image': question.image,
                'question_type': 'multiple',
                'answers': answers_data,
                'status_label': status_label,
                'status_class': status_class,
            })

    return render(request, 'tests_app/review_test.html', {
        'test': result.test,
        'review_data': review_data,
        'result': result,
    })
@login_required
def teacher_review_result(request, result_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    result = get_object_or_404(
        Result,
        id=result_id,
        test__created_by=request.user
    )

    if request.method == 'POST':
        apply_text_review_updates(result, request.POST)

        student_name = (
            result.student.profile.full_name
            if hasattr(result.student, 'profile') and result.student.profile.full_name
            else result.student.email
        )
        create_notification(
            result.student,
            'Результат проверки',
            f'Преподаватель проверил ваш ответ по тесту «{result.test.title}». Оценка: {result.grade} ({result.percent}%)',
            link=f'/review/{result.id}/',
        )

        messages.success(request, "Проверка текстовых ответов сохранена.")
        return redirect('teacher_review_result', result_id=result.id)

    review_data = []
    text_reviews = result.text_reviews or {}

    for question in result.test.questions.prefetch_related('answers').all():
        if question.question_type == 'text':
            review = text_reviews.get(str(question.id), {})
            user_text = review.get('user_text') or str(result.answers.get(str(question.id), "")).strip()
            correct_text = str(question.correct_text or "").strip()

            if review.get('reviewed'):
                is_correct = float(review.get('score', 0)) >= 1
                status_label = 'Верно' if is_correct else 'Неверно'
                status_class = 'status-correct' if is_correct else 'status-wrong'
            elif user_text and correct_text and user_text.lower() == correct_text.lower():
                is_correct = True
                status_label = 'Верно (авто)'
                status_class = 'status-correct'
            elif user_text:
                is_correct = False
                status_label = 'На проверке'
                status_class = 'status-partial'
            else:
                is_correct = False
                status_label = 'Нет ответа'
                status_class = 'status-wrong'

            review_data.append({
                'question_id': question.id,
                'question_text': question.text,
                'question_image': question.image,
                'question_type': 'text',
                'user_text': user_text,
                'correct_text': correct_text,
                'is_correct': is_correct,
                'status_label': status_label,
                'status_class': status_class,
                'needs_review': not review.get('reviewed') and bool(user_text),
                'review_score': review.get('score', 0),
                'review_comment': review.get('comment', ''),
            })

        else:
            selected_ids = result.answers.get(str(question.id), [])
            selected_ids = set(str(x) for x in selected_ids)

            correct_ids = set(
                str(a.id) for a in question.answers.all() if a.is_correct
            )

            if selected_ids == correct_ids:
                status_label = 'Верно'
                status_class = 'status-correct'
            elif selected_ids and selected_ids & correct_ids:
                status_label = 'Частично верно'
                status_class = 'status-partial'
            else:
                status_label = 'Неверно'
                status_class = 'status-wrong'

            answers_data = []

            for answer in question.answers.all():
                answer_id = str(answer.id)

                answers_data.append({
                    'id': answer.id,
                    'text': answer.text,
                    'is_correct': answer.is_correct,
                    'is_selected': answer_id in selected_ids,
                })

            review_data.append({
                'question_text': question.text,
                'question_image': question.image,
                'question_type': 'multiple',
                'answers': answers_data,
                'status_label': status_label,
                'status_class': status_class,
            })

    student_name = (
        result.student.profile.full_name
        or result.student.email
        or result.student.username
    )

    return render(request, 'tests_app/teacher_review_result.html', {
        'test': result.test,
        'result': result,
        'review_data': review_data,
        'student_name': student_name,
        'has_pending_text': result.grading_status == 'pending_review',
    })

#ПРЕПОДАВАТЕЛЬ

@login_required
def teacher_tests(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        time_limit = request.POST.get('time_limit')

        if title:
            try:
                time_limit_int = int(time_limit) if time_limit else 10
            except (ValueError, TypeError):
                time_limit_int = 10
            Test.objects.create(
                title=title,
                description=description,
                time_limit=time_limit_int,
                created_by=request.user,
                is_active=False
        )
            return redirect('teacher_dashboard')

    query = request.GET.get('q', '').strip()

    all_tests = request.user.created_tests.all().order_by('-created_at')
    tests = all_tests

    if query:
        tests = tests.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )

    category_id = request.GET.get('category', '').strip()
    if category_id.isdigit():
        tests = tests.filter(category_id=int(category_id))

    test_suggestions = all_tests.values_list('title', flat=True).distinct()
    paginator = Paginator(tests, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'tests_app/teacher_tests.html', {
        'tests': page_obj,
        'page_obj': page_obj,
        'query': query,
        'test_suggestions': test_suggestions,
        'categories': TestCategory.objects.all(),
        'selected_category': category_id,
    })

@login_required
def create_test(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    if request.method == 'POST':
        form = TestForm(request.POST, teacher=request.user)

        if form.is_valid():
            test = form.save(commit=False)
            test.created_by = request.user
            test.is_active = False
            test.save()
            form.save_m2m()

            messages.success(request, "Тест успешно создан")
            return redirect('teacher_dashboard')
        else:
            messages.error(request, "Не удалось создать тест. Проверьте правильность заполнения формы.")
    else:
        form = TestForm(teacher=request.user)

    return render(request, 'tests_app/create_test.html', {
        'form': form
    })


@login_required
def edit_test(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == "POST":
        form = TestForm(request.POST, instance=test, teacher=request.user)

        if form.is_valid():
            updated_test = form.save(commit=False)
            updated_test.created_by = request.user
            updated_test.save()
            form.save_m2m()

            messages.success(request, "Изменения теста успешно сохранены.")
            return redirect('edit_test', test_id=updated_test.id)
        else:
            error_list = []
            for field, errs in form.errors.items():
                error_list.append(f"{field}: {', '.join(errs)}")
            messages.error(request, "Ошибки: " + "; ".join(error_list))
    else:
        form = TestForm(instance=test, teacher=request.user)

    questions = list(
        test.questions
        .prefetch_related('answers')
        .all()
    )

    total_questions = len(questions)
    text_questions_count = 0
    choice_questions_count = 0
    problem_questions_count = 0

    for question in questions:
        answers = list(question.answers.all())

        question.answers_count = len(answers)
        question.correct_answers_count = sum(1 for answer in answers if answer.is_correct)

        if question.question_type == 'text':
            text_questions_count += 1
            question.type_label = "Текстовый ответ"
            question.is_ready = bool(question.correct_text and question.correct_text.strip())

            if question.is_ready:
                question.status_label = "Заполнен"
                question.status_class = "status-ready"
            else:
                question.status_label = "Нет правильного ответа"
                question.status_class = "status-warning"
                problem_questions_count += 1

        else:
            choice_questions_count += 1

            if question.correct_answers_count > 1:
                question.type_label = "Несколько ответов"
            else:
                question.type_label = "Один ответ"

            question.is_ready = (
                question.answers_count >= 2 and
                question.correct_answers_count >= 1
            )

            if question.answers_count == 0:
                question.status_label = "Нет вариантов ответа"
                question.status_class = "status-danger"
                problem_questions_count += 1
            elif question.correct_answers_count == 0:
                question.status_label = "Нет правильного ответа"
                question.status_class = "status-warning"
                problem_questions_count += 1
            elif question.answers_count < 2:
                question.status_label = "Мало вариантов"
                question.status_class = "status-warning"
                problem_questions_count += 1
            else:
                question.status_label = "Заполнен"
                question.status_class = "status-ready"

    return render(request, 'tests_app/edit_test.html', {
        'form': form,
        'test': test,
        'questions': questions,
        'total_questions': total_questions,
        'text_questions_count': text_questions_count,
        'choice_questions_count': choice_questions_count,
        'problem_questions_count': problem_questions_count,
    })


@login_required
def delete_test(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == 'POST':
        title = test.title
        test.delete()
        log_activity(request.user, 'Удаление теста', title)
        messages.success(request, "Тест удалён")
        return redirect('teacher_dashboard')

    return redirect('edit_test', test_id=test.id)


@login_required
def toggle_test_status(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == 'POST':

        # Если тест сейчас активен — просто скрываем его.
        # Для скрытия проверка заполненности не нужна.
        if test.is_active:
            test.is_active = False
            test.save()
            log_activity(request.user, 'Скрытие теста', test.title)

            messages.success(request, "Тест скрыт и больше не отображается у студентов.")
            return redirect(f"{reverse('teacher_dashboard')}#test-{test.id}")

        # Если тест сейчас скрыт — пытаемся опубликовать.
        # Перед публикацией проверяем готовность теста.
        questions = list(
            test.questions
            .prefetch_related('answers')
            .all()
        )

        problems = []

        if not questions:
            problems.append("в тесте нет ни одного вопроса")

        for number, question in enumerate(questions, start=1):

            if not question.text or not question.text.strip():
                problems.append(f"вопрос {number}: не указан текст вопроса")

            if question.question_type == 'text':
                if not question.correct_text or not question.correct_text.strip():
                    problems.append(f"вопрос {number}: не указан правильный текстовый ответ")

            else:
                answers = list(question.answers.all())
                correct_answers = [answer for answer in answers if answer.is_correct]

                if len(answers) == 0:
                    problems.append(f"вопрос {number}: нет вариантов ответа")
                elif len(answers) < 2:
                    problems.append(f"вопрос {number}: должно быть минимум два варианта ответа")

                if len(correct_answers) == 0:
                    problems.append(f"вопрос {number}: не отмечен правильный ответ")

        if problems:
            message = "Тест нельзя опубликовать. Исправьте ошибки: " + "; ".join(problems) + "."
            messages.error(request, message)
            return redirect('edit_test', test_id=test.id)

        test.is_active = True
        test.save()
        log_activity(request.user, 'Публикация теста', test.title)

        messages.success(request, "Тест опубликован и теперь виден студентам.")
        return redirect(f"{reverse('teacher_dashboard')}#test-{test.id}")

    return redirect('teacher_dashboard')


@login_required
def test_results(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    base_qs = Result.objects.filter(test=test)

    stats = base_qs.aggregate(
        attempts=Count('id'),
        avg_percent=Avg('percent'),
    )
    attempts_count = stats['attempts']
    avg_percent = round(stats['avg_percent'] or 0, 1)

    if attempts_count > 0:
        results = list(
            base_qs
            .select_related('student', 'student__profile')
            .order_by('-created_at')
        )
        best_percent = max(r.percent for r in results)
        worst_percent = min(r.percent for r in results)

        numeric_grades = []
        for r in results:
            try:
                numeric_grades.append(int(r.grade))
            except ValueError:
                pass

        avg_grade = round(sum(numeric_grades) / len(numeric_grades), 1) if numeric_grades else 0
    else:
        results = []
        best_percent = 0
        worst_percent = 0
        avg_grade = 0

    grade_counts = dict(
        base_qs
        .values('grade')
        .annotate(cnt=Count('id'))
        .values_list('grade', 'cnt')
    )

    grade_5_count = grade_counts.get('5', 0)
    grade_4_count = grade_counts.get('4', 0)
    grade_3_count = grade_counts.get('3', 0)
    grade_2_count = grade_counts.get('2', 0)

    question_stats = []
    all_results = list(
        base_qs.values_list('answers', flat=True)
    )
    for question in test.questions.prefetch_related('answers').all():
        total = len(all_results)
        correct = 0
        if question.question_type == 'text':
            correct_text = (question.correct_text or '').strip().lower()
            for ans in all_results:
                user_text = str(ans.get(str(question.id), '')).strip().lower()
                if user_text and correct_text and user_text == correct_text:
                    correct += 1
        else:
            correct_ids = set(str(a.id) for a in question.answers.all() if a.is_correct)
            for ans in all_results:
                selected = set(str(x) for x in ans.get(str(question.id), []))
                if selected == correct_ids:
                    correct += 1

        pct = round(correct / total * 100, 1) if total > 0 else 0
        question_stats.append({
            'text': question.text[:100],
            'type': question.get_question_type_display(),
            'total': total,
            'correct': correct,
            'percent': pct,
        })

    return render(request, 'tests_app/test_results.html', {
        'test': test,
        'results': results,
        'page_obj': None,
        'attempts_count': attempts_count,
        'avg_percent': avg_percent,
        'best_percent': best_percent,
        'worst_percent': worst_percent,
        'avg_grade': avg_grade,
        'grade_5_count': grade_5_count,
        'grade_4_count': grade_4_count,
        'grade_3_count': grade_3_count,
        'grade_2_count': grade_2_count,
        'question_stats': question_stats,
    })

@login_required
def export_test_results(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    results = (
        Result.objects
        .filter(test=test)
        .select_related('student', 'student__profile')
        .order_by('-created_at')
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="test_results_{test.id}.csv"'

    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')

    writer.writerow([
        'Студент',
        'Email',
        'Тест',
        'Баллы',
        'Процент',
        'Оценка',
        'Дата прохождения'
    ])

    for result in results:
        student_name = (
            result.student.profile.full_name
            or result.student.email
            or result.student.username
        )

        score = str(result.score).replace('.', ',')
        percent = str(result.percent).replace('.', ',') + '%'
        date_value = result.created_at.strftime('%d.%m.%Y %H:%M')

        writer.writerow([
            student_name,
            result.student.email or result.student.username,
            test.title,
            score,
            percent,
            result.grade,
            date_value
        ])

    return response

@login_required
def edit_teacher_profile(request):
    if request.user.profile.role != 'teacher':
        raise PermissionDenied()

    profile = request.user.profile

    if request.method == 'POST':
        bio = request.POST.get('bio')
        avatar = request.FILES.get('avatar')

        profile.bio = bio

        if avatar:
            try:
                validate_uploaded_file(avatar)
                profile.avatar = avatar
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect('edit_teacher_profile')

        profile.save()
        return redirect('teacher_profile')

    return render(request, 'tests_app/edit_teacher_profile.html', {
        'profile': profile
    })


@login_required
def manage_questions(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    questions = test.questions.all()

    return render(request, 'tests_app/manage_questions.html', {
        'test': test,
        'questions': questions
    })


@login_required
def add_question(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        question_type = request.POST.get("question_type", "multiple")
        correct_text = request.POST.get("correct_text", "").strip()
        image = request.FILES.get("image")

        if image:
            try:
                validate_uploaded_file(image)
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect('add_question', test_id=test.id)

        if not text:
            messages.error(request, "Введите текст вопроса.")
            return redirect('add_question', test_id=test.id)

        if question_type == 'text' and not correct_text:
            messages.error(request, "Введите правильный текстовый ответ.")
            return redirect('add_question', test_id=test.id)

        question = Question.objects.create(
            test=test,
            text=text,
            image=image,
            question_type=question_type,
            correct_text=correct_text if question_type == 'text' else None
        )

        if question_type == 'text':
            messages.success(request, "Текстовый вопрос добавлен.")
            return redirect('edit_test', test_id=test.id)

        messages.success(request, "Вопрос добавлен. Теперь добавьте варианты ответов.")
        return redirect('add_answers', question_id=question.id)

    return render(request, 'tests_app/add_question.html', {
        'test': test
    })

@login_required
def edit_question(request, question_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    question = get_object_or_404(
        Question,
        id=question_id,
        test__created_by=request.user
    )

    test = question.test

    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        question_type = request.POST.get("question_type", "multiple")
        correct_text = request.POST.get("correct_text", "").strip()

        new_image = request.FILES.get("image")
        delete_image = request.POST.get("delete_image")

        if new_image:
            try:
                validate_uploaded_file(new_image)
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect('edit_question', question_id=question.id)

        if not text:
            messages.error(request, "Введите текст вопроса.")
            return redirect('edit_question', question_id=question.id)

        if question_type == 'text' and not correct_text:
            messages.error(request, "Введите правильный текстовый ответ.")
            return redirect('edit_question', question_id=question.id)

        question.text = text
        question.question_type = question_type

        if question_type == 'text':
            question.correct_text = correct_text
            question.answers.all().delete()
        else:
            question.correct_text = None

        if delete_image and question.image:
            question.image.delete(save=False)
            question.image = None

        if new_image:
            if question.image:
                question.image.delete(save=False)

            question.image = new_image

        question.save()

        messages.success(request, "Вопрос успешно обновлён.")

        if question_type == 'multiple' and not question.answers.exists():
            return redirect('add_answers', question_id=question.id)

        return redirect('edit_test', test_id=test.id)

    return render(request, 'tests_app/edit_question.html', {
        'question': question,
        'test': test,
    })

@login_required
def add_answers(request, question_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    question = get_object_or_404(
        Question,
        id=question_id,
        test__created_by=request.user
    )

    if request.method == "POST":
        answers = request.POST.getlist("answers")
        correct_indexes = request.POST.getlist("correct")

        new_image = request.FILES.get("question_image")
        delete_image = request.POST.get("delete_image")

        if delete_image and question.image:
            question.image.delete(save=False)
            question.image = None
            question.save()

        if new_image:
            try:
                validate_uploaded_file(new_image)
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect('add_answers', question_id=question.id)
            if question.image:
                question.image.delete(save=False)

            question.image = new_image
            question.save()

        if not answers:
            messages.error(request, "Добавьте хотя бы один вариант ответа.")
            return redirect('add_answers', question_id=question.id)

        question.answers.all().delete()

        for i, text in enumerate(answers):
            text = text.strip()

            if text:
                Answer.objects.create(
                    question=question,
                    text=text,
                    is_correct=(str(i) in correct_indexes)
                )

        messages.success(request, "Ответы и изображение вопроса сохранены.")
        return redirect('edit_test', test_id=question.test.id)

    existing_answers = list(question.answers.all().order_by('id'))

    answer_slots = []

    for i in range(4):
        if i < len(existing_answers):
            answer_slots.append({
                'index': i,
                'number': i + 1,
                'text': existing_answers[i].text,
                'is_correct': existing_answers[i].is_correct,
                'required': i < 2,
            })
        else:
            answer_slots.append({
                'index': i,
                'number': i + 1,
                'text': '',
                'is_correct': False,
                'required': i < 2,
            })

    return render(request, 'tests_app/add_answers.html', {
        'question': question,
        'answer_slots': answer_slots,
    })


@login_required
def delete_question(request, question_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    question = get_object_or_404(
        Question,
        id=question_id,
        test__created_by=request.user
    )

    test_id = question.test.id

    if request.method == 'POST':
        question.delete()
        messages.success(request, "Вопрос удалён")
        return redirect('edit_test', test_id=test_id)

    return redirect('edit_test', test_id=test_id)


@login_required
def delete_answer(request, answer_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    answer = get_object_or_404(
        Answer,
        id=answer_id,
        question__test__created_by=request.user
    )

    test_id = answer.question.test.id

    if request.method == 'POST':
        answer.delete()
        messages.success(request, "Ответ удалён")
        return redirect('edit_test', test_id=test_id)

    return redirect('edit_test', test_id=test_id)


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def verify_email_view(request):
    pending_data = request.session.get('pending_registration')
    session_code = request.session.get('email_verification_code')

    if not pending_data or not session_code:
        messages.error(request, "Сессия подтверждения истекла. Зарегистрируйтесь заново.")
        return redirect('register')

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()

        if entered_code != session_code:
            messages.error(request, "Неверный код подтверждения")
            return redirect('verify_email')

        email = pending_data['email']
        password_hash = pending_data['password_hash']
        role = pending_data['role']
        full_name = pending_data['full_name']

        user = User.objects.create_user(
            username=email,
            email=email,
            password=None
        )
        user.password = password_hash
        user.save(update_fields=['password'])

        profile = user.profile
        profile.role = role
        profile.full_name = full_name

        group_id = pending_data.get('student_group_id')
        if role == 'student' and group_id:
            try:
                profile.student_group = StudentGroup.objects.get(id=int(group_id))
            except (StudentGroup.DoesNotExist, ValueError, TypeError):
                pass

        profile.save()

        login(request, user)

        del request.session['pending_registration']
        del request.session['email_verification_code']

        messages.success(request, "Email успешно подтверждён. Аккаунт создан.")
        return redirect('profile')

    show_code = 'console' in settings.EMAIL_BACKEND
    return render(request, 'tests_app/verify_email.html', {
        'dev_code': session_code if show_code else None,
    })

@login_required
def teacher_profile(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    profile = request.user.profile

    teacher_tests = Test.objects.filter(created_by=request.user)

    total_tests = teacher_tests.count()
    active_tests = teacher_tests.filter(is_active=True).count()
    hidden_tests = total_tests - active_tests

    teacher_results = Result.objects.filter(
        test__created_by=request.user
    ).select_related(
        'student',
        'student__profile',
        'test'
    ).order_by('-created_at')

    total_attempts = teacher_results.count()

    stats = teacher_results.aggregate(avg=Avg('percent'))
    avg_percent = round(stats['avg'] or 0, 1)

    grade_stats_raw = teacher_results.values('grade').annotate(cnt=Count('id'))
    grade_counts = {}
    for row in grade_stats_raw:
        grade_counts[row['grade']] = row['cnt']

    recent_results = teacher_results[:5]

    return render(request, 'tests_app/teacher_profile.html', {
        'profile': profile,
        'total_tests': total_tests,
        'active_tests': active_tests,
        'hidden_tests': hidden_tests,
        'total_attempts': total_attempts,
        'avg_percent': avg_percent,
        'grade_5_count': grade_counts.get('5', 0),
        'grade_4_count': grade_counts.get('4', 0),
        'grade_3_count': grade_counts.get('3', 0),
        'grade_2_count': grade_counts.get('2', 0),
        'recent_results': recent_results,
    })

@login_required
def delete_result(request, result_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    result = get_object_or_404(
        Result,
        id=result_id,
        test__created_by=request.user
    )

    test_id = result.test.id

    if request.method == 'POST':
        result.delete()
        messages.success(request, "Результат прохождения удалён.")
        return redirect('test_results', test_id=test_id)

    return redirect('test_results', test_id=test_id)

@login_required
def teacher_students(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    students = (
        User.objects
        .filter(profile__role='student')
        .select_related('profile', 'profile__student_group')
        .order_by('profile__full_name', 'email')
    )

    student_ids = list(students.values_list('id', flat=True))

    results_agg = (
        Result.objects
        .filter(student_id__in=student_ids, test__created_by=request.user)
        .values('student_id')
        .annotate(
            attempts_count=Count('id'),
            avg_percent=Avg('percent'),
        )
    )
    agg_map = {r['student_id']: r for r in results_agg}

    last_results = (
        Result.objects
        .filter(student_id__in=student_ids, test__created_by=request.user)
        .order_by('student_id', '-created_at')
        .select_related('test')
    )
    last_map = {}
    for r in last_results:
        if r.student_id not in last_map:
            last_map[r.student_id] = r

    students_data = []
    for student in students:
        agg = agg_map.get(student.id, {})
        students_data.append({
            'student': student,
            'attempts_count': agg.get('attempts_count', 0),
            'avg_percent': round(agg.get('avg_percent') or 0, 1),
            'last_result': last_map.get(student.id),
        })

    paginator = Paginator(students_data, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'tests_app/teacher_students.html', {
        'students_data': page_obj,
        'page_obj': page_obj,
    })


@login_required
def teacher_dashboard(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    teacher_tests_qs = Test.objects.filter(created_by=request.user)
    teacher_results = Result.objects.filter(
        test__created_by=request.user
    ).select_related('student', 'student__profile', 'test')

    total_tests = teacher_tests_qs.count()
    active_tests = teacher_tests_qs.filter(is_active=True).count()
    hidden_tests = total_tests - active_tests
    total_students = User.objects.filter(profile__role='student').count()
    total_attempts = teacher_results.count()
    pending_reviews = teacher_results.filter(grading_status='pending_review').count()

    stats = teacher_results.aggregate(avg=Avg('percent'))
    avg_percent = round(stats['avg'] or 0, 1)

    grade_stats_raw = teacher_results.values('grade').annotate(cnt=Count('id'))
    grade_stats = {'5': 0, '4': 0, '3': 0, '2': 0}
    for row in grade_stats_raw:
        if row['grade'] in grade_stats:
            grade_stats[row['grade']] = row['cnt']

    test_chart = list(
        teacher_tests_qs
        .annotate(avg_score=Avg('results__percent'))
        .order_by('-created_at')[:6]
        .values_list('title', 'avg_score')
    )
    test_chart = [{'title': t[:24], 'avg': round(a or 0, 1)} for t, a in test_chart]

    recent_results = teacher_results.order_by('-created_at')[:8]
    recent_tests = list(teacher_tests_qs.order_by('-created_at')[:6])

    top_students = list(
        teacher_results
        .values('student__id', 'student__email', 'student__profile__full_name', 'student__profile__student_group__name')
        .annotate(avg_percent=Avg('percent'), attempts_count=Count('id'))
        .order_by('-avg_percent')[:10]
    )
    top_students = [{
        'name': s['student__profile__full_name'] or s['student__email'],
        'group': s['student__profile__student_group__name'] or '—',
        'avg_percent': round(s['avg_percent'] or 0, 1),
        'attempts': s['attempts_count'],
    } for s in top_students]

    now = timezone.now()
    week_ago = now - timedelta(days=6)
    daily_counts = dict(
        teacher_results
        .filter(created_at__date__gte=week_ago.date(), created_at__date__lte=now.date())
        .values_list('created_at__date')
        .annotate(cnt=Count('id'))
        .values_list('created_at__date', 'cnt')
    )
    activity_chart = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        activity_chart.append({'date': day.strftime('%d.%m'), 'count': daily_counts.get(day, 0)})

    recent_logins = User.objects.filter(
        profile__role='student',
        last_login__isnull=False,
        results__test__created_by=request.user,
    ).select_related('profile').order_by('-last_login').distinct()[:10]

    upcoming_deadlines = teacher_tests_qs.filter(
        is_active=True,
        available_until__gte=now,
        available_until__lte=now + timedelta(days=7)
    ).order_by('available_until')[:5]

    notif_qs = Notification.objects.filter(user=request.user, is_read=False)
    notifications = notif_qs[:10]
    unread_count = notif_qs.count()

    activity_log = ActivityLog.objects.filter(user=request.user)[:10]
    templates_list = TestTemplate.objects.filter(created_by=request.user)[:10]

    groups = StudentGroup.objects.filter(created_by=request.user)
    group_comparison = list(
        teacher_results
        .filter(student__profile__student_group__in=groups)
        .values('student__profile__student_group__name')
        .annotate(
            avg=Avg('percent'),
            attempts=Count('id'),
        )
    )
    group_student_counts = dict(
        groups.annotate(cnt=Count('students')).values_list('name', 'cnt')
    )
    group_comparison = [{
        'name': g['student__profile__student_group__name'] or '—',
        'avg': round(g['avg'] or 0, 1),
        'students': group_student_counts.get(g['student__profile__student_group__name'], 0),
        'attempts': g['attempts'],
    } for g in group_comparison]

    return render(request, 'tests_app/teacher_dashboard.html', {
        'query': '',
        'status_filter': '',
        'total_tests': total_tests,
        'active_tests': active_tests,
        'hidden_tests': hidden_tests,
        'total_students': total_students,
        'total_attempts': total_attempts,
        'pending_reviews': pending_reviews,
        'avg_percent': avg_percent,
        'grade_stats': grade_stats,
        'test_chart': test_chart,
        'recent_results': recent_results,
        'recent_tests': recent_tests,
        'top_students': top_students,
        'activity_chart': activity_chart,
        'recent_logins': recent_logins,
        'upcoming_deadlines': upcoming_deadlines,
        'notifications': notifications,
        'unread_count': unread_count,
        'activity_log': activity_log,
        'templates_list': templates_list,
        'group_comparison': group_comparison,
    })


@login_required
def bulk_test_actions(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')
    if request.method != 'POST':
        return redirect('teacher_dashboard')

    action = request.POST.get('bulk_action')
    test_ids = request.POST.getlist('selected_tests')

    if not test_ids:
        messages.warning(request, 'Выберите хотя бы один тест.')
        return redirect('teacher_dashboard')

    tests = Test.objects.filter(id__in=test_ids, created_by=request.user)

    if action == 'bulk_publish':
        tests.update(is_active=True)
        log_activity(request.user, 'Массовая публикация', f'Опубликовано тестов: {tests.count()}')
        messages.success(request, f'Опубликовано тестов: {tests.count()}')
    elif action == 'bulk_hide':
        tests.update(is_active=False)
        log_activity(request.user, 'Массовое скрытие', f'Скрыто тестов: {tests.count()}')
        messages.success(request, f'Скрыто тестов: {tests.count()}')
    elif action == 'bulk_delete':
        count = tests.count()
        tests.delete()
        log_activity(request.user, 'Массовое удаление', f'Удалено тестов: {count}')
        messages.success(request, f'Удалено тестов: {count}')

    return redirect('teacher_dashboard')


@login_required
def export_all_results(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    results = Result.objects.filter(
        test__created_by=request.user
    ).select_related('student', 'student__profile', 'test').order_by('-created_at')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="results_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Студент', 'Группа', 'Тест', 'Баллы', 'Процент', 'Оценка', 'Статус', 'Дата'])
    for r in results:
        student_name = r.student.profile.full_name if hasattr(r.student, 'profile') and r.student.profile.full_name else r.student.email
        group = r.student.profile.student_group.name if hasattr(r.student, 'profile') and r.student.profile.student_group else '—'
        writer.writerow([
            student_name, group, r.test.title,
            r.score, f'{r.percent}%', r.grade,
            r.get_grading_status_display(),
            r.created_at.strftime('%d.%m.%Y %H:%M'),
        ])

    log_activity(request.user, 'Экспорт результатов', f'Экспортировано записей: {results.count()}')
    return response


@login_required
def save_test_template(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')
    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    template_data = export_test_to_dict(test)
    TestTemplate.objects.create(
        title=test.title,
        description=test.description or '',
        created_by=request.user,
        template_data=template_data,
    )
    log_activity(request.user, 'Сохранение шаблона', f'Шаблон из теста: {test.title}')
    messages.success(request, f'Шаблон «{test.title}» сохранён.')
    return redirect('teacher_dashboard')


@login_required
def use_test_template(request, template_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')
    tmpl = get_object_or_404(TestTemplate, id=template_id, created_by=request.user)

    try:
        test = Test.objects.create(
            title=tmpl.title + ' (копия)',
            description=tmpl.description,
            created_by=request.user,
            time_limit=10,
        )
        import_questions_from_dict(test, tmpl.template_data)
        log_activity(request.user, 'Создание из шаблона', f'Из шаблона: {tmpl.title}')
        messages.success(request, f'Тест создан из шаблона «{tmpl.title}».')
        return redirect('edit_test', test_id=test.id)
    except Exception as e:
        logger.exception("Ошибка создания теста из шаблона")
        messages.error(request, "Ошибка при создании теста из шаблона. Попробуйте позже.")
        return redirect('teacher_dashboard')


@login_required
def delete_test_template(request, template_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')
    tmpl = get_object_or_404(TestTemplate, id=template_id, created_by=request.user)
    title = tmpl.title
    tmpl.delete()
    log_activity(request.user, 'Удаление шаблона', f'Шаблон: {title}')
    messages.success(request, f'Шаблон «{title}» удалён.')
    return redirect('teacher_dashboard')


@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('teacher_dashboard')


@login_required
def export_activity_log(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    logs = ActivityLog.objects.filter(user=request.user)[:200]

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="activity_log.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Дата', 'Действие', 'Детали'])
    for log in logs:
        writer.writerow([
            log.created_at.strftime('%d.%m.%Y %H:%M'),
            log.action,
            log.details,
        ])
    return response


@login_required
def teacher_groups(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            form = StudentGroupForm(request.POST)
            if form.is_valid():
                group = form.save(commit=False)
                group.created_by = request.user
                group.save()
                messages.success(request, f'Группа «{group.name}» создана.')
            else:
                messages.error(request, 'Не удалось создать группу.')
        elif action == 'delete':
            group_id = request.POST.get('group_id')
            try:
                group = StudentGroup.objects.get(id=int(group_id), created_by=request.user)
                group.delete()
                messages.success(request, 'Группа удалена.')
            except (StudentGroup.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'Группа не найдена.')
        elif action == 'add_student':
            group_id = request.POST.get('group_id')
            student_id = request.POST.get('student_id')
            try:
                group = StudentGroup.objects.get(id=int(group_id), created_by=request.user)
                student = User.objects.get(id=int(student_id), profile__role='student')
                student.profile.student_group = group
                student.profile.save()
                messages.success(request, f'Студент добавлен в группу «{group.name}».')
            except (StudentGroup.DoesNotExist, User.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'Ошибка при добавлении студента.')
        elif action == 'remove_student':
            group_id = request.POST.get('group_id')
            student_id = request.POST.get('student_id')
            try:
                student = User.objects.get(id=int(student_id), profile__role='student', profile__student_group__id=int(group_id))
                student.profile.student_group = None
                student.profile.save()
                messages.success(request, 'Студент удалён из группы.')
            except (User.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'Ошибка при удалении студента.')

        return redirect('teacher_groups')

    groups = StudentGroup.objects.filter(
        created_by=request.user
    ).order_by('name')

    group_ids = list(groups.values_list('id', flat=True))

    student_counts = dict(
        User.objects.filter(
            profile__role='student',
            profile__student_group_id__in=group_ids,
        ).values('profile__student_group_id')
        .annotate(cnt=Count('id'))
        .values_list('profile__student_group_id', 'cnt')
    )

    test_counts = dict(
        Test.objects.filter(
            assigned_groups__id__in=group_ids,
            created_by=request.user,
        ).values('assigned_groups__id')
        .annotate(cnt=Count('id'))
        .values_list('assigned_groups__id', 'cnt')
    )

    groups_data = []
    for group in groups:
        students_in_group = User.objects.filter(
            profile__role='student',
            profile__student_group=group
        ).select_related('profile')
        groups_data.append({
            'group': group,
            'students_count': student_counts.get(group.id, 0),
            'tests_count': test_counts.get(group.id, 0),
            'students': students_in_group,
        })

    all_students = User.objects.filter(
        profile__role='student'
    ).select_related('profile').order_by('profile__full_name')

    return render(request, 'tests_app/teacher_groups.html', {
        'groups_data': groups_data,
        'form': StudentGroupForm(),
        'all_students': all_students,
    })


@login_required
def group_detail(request, group_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    group = get_object_or_404(StudentGroup, id=group_id, created_by=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete':
            group.delete()
            messages.success(request, f'Группа «{group.name}» удалена.')
            return redirect('teacher_groups')

        elif action == 'add_student':
            student_id = request.POST.get('student_id')
            try:
                student = User.objects.get(id=int(student_id), profile__role='student')
                student.profile.student_group = group
                student.profile.save()
                messages.success(request, f'Студент добавлен в группу.')
            except (User.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'Ошибка при добавлении студента.')

        elif action == 'remove_student':
            student_id = request.POST.get('student_id')
            try:
                student = User.objects.get(id=int(student_id), profile__role='student', profile__student_group=group)
                student.profile.student_group = None
                student.profile.save()
                messages.success(request, 'Студент удалён из группы.')
            except (User.DoesNotExist, ValueError, TypeError):
                messages.error(request, 'Ошибка при удалении студента.')

        return redirect('group_detail', group_id=group.id)

    students = list(
        User.objects
        .filter(profile__role='student', profile__student_group=group)
        .select_related('profile')
        .order_by('profile__full_name', 'email')
    )

    student_ids = [s.id for s in students]
    results_agg = (
        Result.objects
        .filter(student_id__in=student_ids, test__created_by=request.user)
        .values('student_id')
        .annotate(results_count=Count('id'), avg_percent=Avg('percent'))
    )
    agg_map = {r['student_id']: r for r in results_agg}

    for s in students:
        agg = agg_map.get(s.id, {})
        s.results_count = agg.get('results_count', 0)
        s.avg_percent = round(agg.get('avg_percent') or 0, 1)

    current_ids = set(student_ids)
    available_students = list(
        User.objects
        .filter(profile__role='student')
        .exclude(id__in=current_ids)
        .select_related('profile')
        .order_by('profile__full_name', 'email')
    )

    assigned_tests = Test.objects.filter(
        assigned_groups=group,
        created_by=request.user,
    ).order_by('-created_at')

    return render(request, 'tests_app/group_detail.html', {
        'group': group,
        'students': students,
        'available_students': available_students,
        'assigned_tests': assigned_tests,
    })


@login_required
def import_test_json(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == 'POST' and request.FILES.get('json_file'):
        try:
            payload = parse_test_json_file(request.FILES['json_file'])
            created = import_questions_from_dict(test, payload)
            messages.success(request, f'Импортировано вопросов: {created}.')
        except (json.JSONDecodeError, UnicodeDecodeError):
            messages.error(request, 'Некорректный JSON-файл.')
        except Exception as exc:
            logger.exception("Import error: %s", exc)
            messages.error(request, 'Ошибка при импорте теста.')

    return redirect('edit_test', test_id=test.id)


@login_required
def export_test_json(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    payload = export_test_to_dict(test)

    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8',
    )
    response['Content-Disposition'] = f'attachment; filename="test_{test.id}.json"'
    return response


@login_required
def duplicate_test(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    source = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == 'POST':
        copy = Test.objects.create(
            title=f'{source.title} (копия)',
            description=source.description,
            category=source.category,
            created_by=request.user,
            time_limit=source.time_limit,
            max_attempts=source.max_attempts,
            is_active=False,
            visibility=source.visibility,
            shuffle_questions=source.shuffle_questions,
            shuffle_answers=source.shuffle_answers,
            available_from=source.available_from,
            available_until=source.available_until,
        )
        copy.assigned_groups.set(source.assigned_groups.all())

        for question in source.questions.prefetch_related('answers').all():
            new_question = Question.objects.create(
                test=copy,
                text=question.text,
                image=question.image,
                question_type=question.question_type,
                correct_text=question.correct_text,
            )
            for answer in question.answers.all():
                Answer.objects.create(
                    question=new_question,
                    text=answer.text,
                    is_correct=answer.is_correct,
                )

        messages.success(request, 'Копия теста создана.')
        return redirect('edit_test', test_id=copy.id)

    return redirect('teacher_dashboard')


@login_required
def export_test_results_pdf(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    results = list(
        Result.objects
        .filter(test=test)
        .select_related('student', 'student__profile')
        .order_by('-created_at')
    )

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import os

    font_regular = os.path.join('C:\\Windows\\Fonts', 'arial.ttf')
    font_bold = os.path.join('C:\\Windows\\Fonts', 'arialbd.ttf')

    pdfmetrics.registerFont(TTFont('Arial', font_regular))
    pdfmetrics.registerFont(TTFont('ArialBold', font_bold))

    buffer = HttpResponse(content_type='application/pdf')
    buffer['Content-Disposition'] = f'attachment; filename="report_{test.id}.pdf"'

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm, leftMargin=15*mm, rightMargin=15*mm)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontName='ArialBold', fontSize=16, spaceAfter=10, textColor=HexColor('#0f172a'))
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Normal'], fontName='Arial', fontSize=11, textColor=HexColor('#64748b'), spaceAfter=6)
    heading_style = ParagraphStyle('HeadingCustom', parent=styles['Heading2'], fontName='ArialBold', fontSize=13, spaceAfter=8, spaceBefore=16, textColor=HexColor('#1d4ed8'))
    cell_style = ParagraphStyle('CellStyle', fontName='Arial', fontSize=9, leading=12)
    cell_bold_style = ParagraphStyle('CellBoldStyle', fontName='ArialBold', fontSize=9, leading=12)

    elements = []

    elements.append(Paragraph("Отчёт по результатам теста", title_style))
    elements.append(Paragraph(f"Тест: {test.title}", subtitle_style))
    elements.append(Paragraph(f"Дата составления: {timezone.now().strftime('%d.%m.%Y %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 8*mm))

    total = len(results)
    if total > 0:
        avg_percent = round(sum(r.percent for r in results) / total, 1)
        grade_5 = sum(1 for r in results if r.grade == '5')
        grade_4 = sum(1 for r in results if r.grade == '4')
        grade_3 = sum(1 for r in results if r.grade == '3')
        grade_2 = sum(1 for r in results if r.grade == '2')
    else:
        avg_percent = 0
        grade_5 = grade_4 = grade_3 = grade_2 = 0

    elements.append(Paragraph("Сводка", heading_style))

    summary_data = [
        [Paragraph('<b>Показатель</b>', cell_bold_style), Paragraph('<b>Значение</b>', cell_bold_style)],
        [Paragraph('Всего попыток', cell_style), Paragraph(str(total), cell_style)],
        [Paragraph('Средний балл', cell_style), Paragraph(f'{avg_percent}%', cell_style)],
        [Paragraph('Оценок «5»', cell_style), Paragraph(str(grade_5), cell_style)],
        [Paragraph('Оценок «4»', cell_style), Paragraph(str(grade_4), cell_style)],
        [Paragraph('Оценок «3»', cell_style), Paragraph(str(grade_3), cell_style)],
        [Paragraph('Оценок «2»', cell_style), Paragraph(str(grade_2), cell_style)],
    ]

    summary_table = Table(summary_data, colWidths=[100*mm, 60*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'ArialBold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("Результаты студентов", heading_style))

    header = [
        Paragraph('<b>#</b>', cell_bold_style),
        Paragraph('<b>Студент</b>', cell_bold_style),
        Paragraph('<b>Баллы</b>', cell_bold_style),
        Paragraph('<b>%</b>', cell_bold_style),
        Paragraph('<b>Оценка</b>', cell_bold_style),
        Paragraph('<b>Статус</b>', cell_bold_style),
        Paragraph('<b>Дата</b>', cell_bold_style),
    ]

    table_data = [header]

    for idx, r in enumerate(results, start=1):
        student_name = (
            r.student.profile.full_name
            if hasattr(r.student, 'profile') and r.student.profile.full_name
            else r.student.email
        )
        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(student_name, cell_style),
            Paragraph(str(r.score), cell_style),
            Paragraph(f'{r.percent}%', cell_style),
            Paragraph(r.grade, cell_style),
            Paragraph(r.get_grading_status_display(), cell_style),
            Paragraph(r.created_at.strftime('%d.%m.%Y'), cell_style),
        ])

    results_table = Table(table_data, colWidths=[12*mm, 48*mm, 18*mm, 18*mm, 18*mm, 28*mm, 28*mm])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'ArialBold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
    ]))
    elements.append(results_table)

    doc.build(elements)
    log_activity(request.user, 'Экспорт PDF', f'Тест: {test.title}')
    return buffer


@login_required
def export_student_result_pdf(request, result_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    result = get_object_or_404(
        Result, id=result_id, test__created_by=request.user
    )

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import os

    font_regular = os.path.join('C:\\Windows\\Fonts', 'arial.ttf')
    font_bold = os.path.join('C:\\Windows\\Fonts', 'arialbd.ttf')
    pdfmetrics.registerFont(TTFont('Arial', font_regular))
    pdfmetrics.registerFont(TTFont('ArialBold', font_bold))

    buffer = HttpResponse(content_type='application/pdf')
    buffer['Content-Disposition'] = f'attachment; filename="result_{result.id}.pdf"'

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm, leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontName='ArialBold', fontSize=16, spaceAfter=10, textColor=HexColor('#0f172a'))
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Normal'], fontName='Arial', fontSize=11, textColor=HexColor('#64748b'), spaceAfter=6)
    heading_style = ParagraphStyle('HeadingCustom', parent=styles['Heading2'], fontName='ArialBold', fontSize=13, spaceAfter=8, spaceBefore=12, textColor=HexColor('#1d4ed8'))
    cell_style = ParagraphStyle('CellStyle', fontName='Arial', fontSize=9, leading=12)
    cell_bold_style = ParagraphStyle('CellBoldStyle', fontName='ArialBold', fontSize=9, leading=12)

    student_name = (
        result.student.profile.full_name
        if hasattr(result.student, 'profile') and result.student.profile.full_name
        else result.student.email
    )

    elements = []
    elements.append(Paragraph("Индивидуальный отчёт", title_style))
    elements.append(Paragraph(f"Студент: {student_name}", subtitle_style))
    elements.append(Paragraph(f"Тест: {result.test.title}", subtitle_style))
    elements.append(Paragraph(f"Дата: {result.created_at.strftime('%d.%m.%Y %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 6*mm))

    summary_data = [
        [Paragraph('<b>Показатель</b>', cell_bold_style), Paragraph('<b>Значение</b>', cell_bold_style)],
        [Paragraph('Баллы', cell_style), Paragraph(str(result.score), cell_style)],
        [Paragraph('Процент', cell_style), Paragraph(f'{result.percent}%', cell_style)],
        [Paragraph('Оценка', cell_style), Paragraph(result.grade, cell_style)],
    ]

    summary_table = Table(summary_data, colWidths=[80*mm, 80*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'ArialBold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph("Ответы на вопросы", heading_style))

    q_header = [
        Paragraph('<b>#</b>', cell_bold_style),
        Paragraph('<b>Вопрос</b>', cell_bold_style),
        Paragraph('<b>Ответ студента</b>', cell_bold_style),
        Paragraph('<b>Результат</b>', cell_bold_style),
    ]

    q_data = [q_header]
    for idx, question in enumerate(result.test.questions.prefetch_related('answers').all(), start=1):
        user_answer = result.answers.get(str(question.id), '')
        is_correct = False

        if question.question_type == 'text':
            user_text = str(user_answer).strip()
            correct_text = str(question.correct_text or '').strip()
            display_answer = user_text or '—'
            is_correct = user_text.lower() == correct_text.lower() if user_text and correct_text else False
        else:
            selected = set(str(x) for x in user_answer)
            correct_ids = set(str(a.id) for a in question.answers.all() if a.is_correct)
            answer_texts = []
            for a in question.answers.all():
                if str(a.id) in selected:
                    answer_texts.append(a.text)
            display_answer = ', '.join(answer_texts) if answer_texts else '—'
            is_correct = selected == correct_ids

        result_text = 'Верно' if is_correct else 'Неверно'
        result_color = HexColor('#166534') if is_correct else HexColor('#991b1b')

        q_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(question.text[:80], cell_style),
            Paragraph(display_answer[:60], cell_style),
            Paragraph(f'<font color="{result_color.hexval()}">{result_text}</font>', cell_style),
        ])

    q_table = Table(q_data, colWidths=[12*mm, 60*mm, 50*mm, 38*mm])
    q_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'ArialBold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#ffffff'), HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
    ]))
    elements.append(q_table)

    doc.build(elements)
    return buffer