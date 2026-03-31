from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Avg
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta
from .models import Test, Question, Answer, Result, Profile
from .forms import TestForm
import random
from django.conf import settings
from django.core.mail import send_mail
TEACHER_SECRET = "TEACHER2026"


# ===================== ГЛАВНАЯ =====================

def home(request):
    stats = {
        'users': User.objects.count(),
        'tests': Test.objects.count(),
        'attempts': Result.objects.count()
    }
    return render(request, 'tests_app/home.html', stats)


def tests_list(request):
    tests = Test.objects.all()
    return render(request, 'tests_app/tests_list.html', {'tests': tests})


# ===================== ТЕСТИРОВАНИЕ =====================

@login_required
def start_test(request, test_id):
    test = get_object_or_404(Test, id=test_id)

    request.session['test_id'] = test_id
    request.session['answers'] = {}
    request.session['index'] = 0
    request.session['start_time'] = timezone.now().isoformat()
    request.session['end_time'] = (
        timezone.now() + timedelta(minutes=test.time_limit)
    ).isoformat()

    return redirect('question')


@login_required
def question_view(request):
    test_id = request.session.get('test_id')
    answers_store = request.session.get('answers', {})
    index = request.session.get('index', 0)
    end_time_str = request.session.get('end_time')

    if not test_id:
        return redirect('home')

    if end_time_str:
        end_time = timezone.datetime.fromisoformat(end_time_str)
        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time, timezone.get_current_timezone())

        if timezone.now() >= end_time:
            messages.warning(request, "Время на прохождение теста истекло.")
            return redirect('result')

    test = get_object_or_404(Test, id=test_id)
    questions = list(test.questions.all())

    if index >= len(questions):
        return redirect('result')

    question = questions[index]

    correct_count = question.answers.filter(is_correct=True).count()
    is_multiple = correct_count > 1

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'next':
            selected = request.POST.getlist('answers')
            answers_store[str(question.id)] = selected
            request.session['answers'] = answers_store
            request.session['index'] = index + 1

        elif action == 'back':
            request.session['index'] = max(0, index - 1)

        return redirect('question')

    selected_answers = answers_store.get(str(question.id), [])

    remaining_seconds = 0
    if end_time_str:
        end_time = timezone.datetime.fromisoformat(end_time_str)
        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time, timezone.get_current_timezone())
        remaining_seconds = max(0, int((end_time - timezone.now()).total_seconds()))

    return render(request, 'tests_app/exam.html', {
        'test': test,
        'question': question,
        'answers': question.answers.all(),
        'index': index + 1,
        'total': len(questions),
        'is_multiple': is_multiple,
        'selected_answers': selected_answers,
        'remaining_seconds': remaining_seconds,
    })


@login_required
def result_view(request):
    test_id = request.session.get('test_id')
    answers = request.session.get('answers', {})

    if not test_id:
        return redirect('home')

    test = get_object_or_404(Test, id=test_id)
    questions = test.questions.all()

    score = 0

    for q in questions:
        correct_ids = set(q.answers.filter(is_correct=True).values_list('id', flat=True))
        user_ids = set(map(int, answers.get(str(q.id), [])))

        if correct_ids:
            score += len(correct_ids & user_ids) / len(correct_ids)

    total = questions.count()
    percent = (score / total) * 100 if total else 0

    grade = (
        "5" if percent >= 85 else
        "4" if percent >= 70 else
        "3" if percent >= 50 else
        "2"
    )

    Result.objects.create(
        student=request.user,
        test=test,
        score=round(score, 2),
        percent=round(percent, 1),
        grade=grade,
        answers=answers
    )

    request.session.pop('test_id', None)
    request.session.pop('answers', None)
    request.session.pop('index', None)
    request.session.pop('start_time', None)
    request.session.pop('end_time', None)

    return render(request, 'tests_app/result.html', {
        'score': round(score, 2),
        'total': total,
        'percent': round(percent, 1),
        'grade': grade
    })


# ===================== ПРОФИЛЬ =====================

@login_required
def profile(request):
    profile = request.user.profile

    if request.method == 'POST':
        profile.full_name = request.POST.get('full_name', '').strip()
        profile.bio = request.POST.get('bio') or ""

        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']

        profile.save()
        return redirect('profile')

    if profile.role == 'teacher':
        return redirect('teacher_dashboard')

    results = Result.objects.filter(student=request.user)

    total_tests = results.count()

    avg_percent = round(
        results.aggregate(avg=Avg('percent'))['avg'] or 0,
        1
    )

    best_result = results.order_by('-grade').first()

    level = (
        "Эксперт" if avg_percent >= 85 else
        "Продвинутый" if avg_percent >= 70 else
        "Новичок"
    )

    return render(request, 'tests_app/profile.html', {
        'profile': profile,
        'results': results,
        'avg_percent': avg_percent,
        'total_tests': total_tests,
        'best_result': best_result,
        'level': level
    })


# ===================== АВТОРИЗАЦИЯ =====================

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
            messages.error(request, "Пользователь с таким email не найден")
            return redirect('login')

        user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            messages.error(request, "Неверный email или пароль")
            return redirect('login')

        login(request, user)

        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)

        if user.profile.role == 'teacher':
            return redirect('teacher_dashboard')

        return redirect('home')

    return render(request, 'tests_app/login.html')


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

        if role == 'teacher' and secret != settings.TEACHER_SECRET_KEY:
            messages.error(request, "Неверный секретный код преподавателя")
            return redirect('register')

        code = str(random.randint(100000, 999999))

        request.session['pending_registration'] = {
            'full_name': full_name,
            'email': email,
            'password': password,
            'role': role,
        }
        request.session['email_verification_code'] = code

        try:
            send_mail(
                subject='Код подтверждения TestFlow',
                message=f'Ваш код подтверждения: {code}',
                from_email=None,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, "Код подтверждения отправлен на вашу почту")
        except Exception:
            print("КОД ПОДТВЕРЖДЕНИЯ:", code)
            messages.warning(
                request,
                "Не удалось отправить письмо автоматически. Код выведен в консоли сервера."
            )

        return redirect('verify_email')

    return render(request, 'tests_app/register.html')


def logout_view(request):
    logout(request)
    return redirect('home')


# ===================== ПРОСМОТР ТЕСТА =====================

@login_required
def review_test(request, result_id):
    result = get_object_or_404(Result, id=result_id, student=request.user)

    review_data = []

    for question in result.test.questions.prefetch_related('answers').all():
        selected_ids = result.answers.get(str(question.id), [])
        selected_ids = [str(x) for x in selected_ids]

        answers_data = []
        for answer in question.answers.all():
            answers_data.append({
                'id': answer.id,
                'text': answer.text,
                'is_correct': answer.is_correct,
                'is_selected': str(answer.id) in selected_ids,
            })

        review_data.append({
            'question_text': question.text,
            'answers': answers_data,
        })

    return render(request, 'tests_app/review_test.html', {
        'test': result.test,
        'review_data': review_data,
        'result': result,
    })


# ===================== ПРЕПОДАВАТЕЛЬ =====================

@login_required
def teacher_dashboard(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        time_limit = request.POST.get('time_limit')

        if title:
            Test.objects.create(
                title=title,
                description=description,
                time_limit=int(time_limit) if time_limit else 10,
                created_by=request.user
            )
            return redirect('teacher_dashboard')

    tests = request.user.created_tests.all().order_by('-created_at')

    return render(request, 'tests_app/teacher_dashboard.html', {
        'tests': tests
    })


@login_required
def create_test(request):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        time_limit = request.POST.get('time_limit')

        Test.objects.create(
            title=title,
            description=description,
            time_limit=int(time_limit) if time_limit else 10,
            created_by=request.user
        )

        return redirect('teacher_dashboard')

    return render(request, 'tests_app/create_test.html')


@login_required
def edit_test(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)

    if request.method == "POST":
        form = TestForm(request.POST, instance=test)
        if form.is_valid():
            form.save()
            return redirect('edit_test', test_id=test.id)
    else:
        form = TestForm(instance=test)

    questions = test.questions.prefetch_related('answers')

    return render(request, 'tests_app/edit_test.html', {
        'form': form,
        'test': test,
        'questions': questions
    })


@login_required
def delete_test(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    test.delete()
    return redirect('teacher_dashboard')


@login_required
def test_results(request, test_id):
    if request.user.profile.role != 'teacher':
        return redirect('home')

    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    results = Result.objects.filter(test=test)

    return render(request, 'tests_app/test_results.html', {
        'test': test,
        'results': results
    })


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
            profile.avatar = avatar

        profile.save()
        return redirect('teacher_dashboard')

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
        text = request.POST.get("text")

        if text:
            Question.objects.create(
                test=test,
                text=text
            )
            return redirect('edit_test', test_id=test.id)

    return render(request, 'tests_app/add_question.html', {
        'test': test
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

        if not answers:
            return redirect('add_answers', question_id=question.id)

        question.answers.all().delete()

        for i, text in enumerate(answers):
            if text.strip():
                Answer.objects.create(
                    question=question,
                    text=text,
                    is_correct=(str(i) in correct_indexes)
                )

        return redirect('edit_test', test_id=question.test.id)

    return render(request, 'tests_app/add_answers.html', {
        'question': question
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
    question.delete()

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
    answer.delete()

    return redirect('edit_test', test_id=test_id)
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

        user = User.objects.create_user(
            username=pending_data['email'],
            email=pending_data['email'],
            password=pending_data['password']
        )

        profile = user.profile
        profile.full_name = pending_data['full_name']
        profile.role = pending_data['role']
        profile.save()

        request.session.pop('pending_registration', None)
        request.session.pop('email_verification_code', None)

        messages.success(request, "Email подтверждён. Теперь войдите в систему.")
        return redirect('login')

    return render(request, 'tests_app/verify_email.html')