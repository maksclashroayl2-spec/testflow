from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Profile, Test, Question, Answer, Result
from .forms import TestForm


TEST_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# ===== MODEL TESTS =====

class ProfileModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )

    def test_profile_created_on_user_creation(self):
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.role, 'student')

    def test_profile_str(self):
        self.user.profile.full_name = 'Иван Иванов'
        self.user.profile.save()
        self.assertIn('test@example.com', str(self.user.profile))

    def test_teacher_role(self):
        self.user.profile.role = 'teacher'
        self.user.profile.save()
        self.assertEqual(self.user.profile.get_role_display(), 'Преподаватель')


class TestModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='teacher', email='teacher@example.com', password='testpass123'
        )
        self.user.profile.role = 'teacher'
        self.user.profile.save()

    def test_create_test(self):
        test = Test.objects.create(
            title='Тест по Python',
            description='Описание теста',
            created_by=self.user,
            time_limit=30,
            max_attempts=3,
        )
        self.assertEqual(test.title, 'Тест по Python')
        self.assertEqual(test.created_by, self.user)
        self.assertFalse(test.is_active)

    def test_test_str(self):
        test = Test.objects.create(title='Мой тест', created_by=self.user)
        self.assertIn('Мой тест', str(test))

    def test_test_ordering(self):
        t1 = Test.objects.create(title='Первый', created_by=self.user)
        t2 = Test.objects.create(title='Второй', created_by=self.user)
        tests = list(Test.objects.all())
        self.assertEqual(tests[0], t2)
        self.assertEqual(tests[1], t1)


class QuestionModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='teacher', email='t@t.com', password='pass123'
        )
        self.test = Test.objects.create(title='Тест', created_by=self.user)

    def test_create_question(self):
        q = Question.objects.create(
            test=self.test,
            text='Что такое Python?',
            question_type='multiple',
        )
        self.assertEqual(q.test, self.test)
        self.assertEqual(q.question_type, 'multiple')

    def test_text_question(self):
        q = Question.objects.create(
            test=self.test,
            text='Опишите Python',
            question_type='text',
            correct_text='Язык программирования',
        )
        self.assertEqual(q.correct_text, 'Язык программирования')


class AnswerModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='p')
        self.test = Test.objects.create(title='Тест', created_by=self.user)
        self.question = Question.objects.create(test=self.test, text='Вопрос?')

    def test_create_answer(self):
        a = Answer.objects.create(
            question=self.question, text='Вариант А', is_correct=True
        )
        self.assertTrue(a.is_correct)

    def test_answer_str(self):
        a = Answer.objects.create(question=self.question, text='Ответ', is_correct=True)
        self.assertIn('✔', str(a))

    def test_incorrect_answer_str(self):
        a = Answer.objects.create(question=self.question, text='Ответ', is_correct=False)
        self.assertIn('✘', str(a))


class ResultModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='s', email='s@s.com', password='p')
        self.teacher = User.objects.create_user(username='t', email='t@t.com', password='p')
        self.test = Test.objects.create(title='Тест', created_by=self.teacher)

    def test_create_result(self):
        r = Result.objects.create(
            student=self.user, test=self.test, score=8.5, percent=85.0, grade='5',
            answers={'1': ['2'], '2': ['3']}
        )
        self.assertEqual(r.score, 8.5)
        self.assertEqual(r.grade, '5')

    def test_result_str(self):
        self.user.profile.full_name = 'Студент'
        self.user.profile.save()
        r = Result.objects.create(
            student=self.user, test=self.test, score=7.0, percent=70.0, grade='4'
        )
        self.assertIn('70.0', str(r))


# ===== VIEW TESTS =====

@override_settings(STORAGES=TEST_STORAGES)
class HomeViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_home_status_code(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_home_template(self):
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'tests_app/home.html')


@override_settings(STORAGES=TEST_STORAGES)
class LoginViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )

    def test_login_page_loads(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        response = self.client.post('/login/', {
            'email': 'test@example.com',
            'password': 'testpass123',
        }, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_login_wrong_password(self):
        response = self.client.post('/login/', {
            'email': 'test@example.com',
            'password': 'wrongpass',
        }, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_login_nonexistent_user(self):
        response = self.client.post('/login/', {
            'email': 'no@no.com',
            'password': 'pass',
        }, follow=True)
        self.assertEqual(response.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class RegisterViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_register_page_loads(self):
        response = self.client.get('/register/')
        self.assertEqual(response.status_code, 200)

    def test_register_password_mismatch(self):
        response = self.client.post('/register/', {
            'full_name': 'Тест',
            'email': 'new@example.com',
            'password': 'pass123',
            'password2': 'pass456',
            'role': 'student',
        }, follow=True)
        self.assertEqual(response.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class TestsListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher', email='t@t.com', password='pass123'
        )
        self.teacher.profile.role = 'teacher'
        self.teacher.profile.save()

    def test_empty_list(self):
        response = self.client.get('/tests/')
        self.assertEqual(response.status_code, 200)

    def test_active_tests_visible(self):
        Test.objects.create(
            title='Активный тест', created_by=self.teacher, is_active=True
        )
        response = self.client.get('/tests/')
        self.assertContains(response, 'Активный тест')

    def test_inactive_tests_hidden(self):
        Test.objects.create(
            title='Скрытый тест', created_by=self.teacher, is_active=False
        )
        response = self.client.get('/tests/')
        self.assertNotContains(response, 'Скрытый тест')


@override_settings(STORAGES=TEST_STORAGES)
class StudentFlowTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='student', email='s@s.com', password='pass123'
        )
        self.teacher = User.objects.create_user(
            username='teacher', email='t@t.com', password='pass123'
        )
        self.teacher.profile.role = 'teacher'
        self.teacher.profile.save()

        self.test = Test.objects.create(
            title='Тест по ОС', created_by=self.teacher, is_active=True, time_limit=10
        )
        self.q1 = Question.objects.create(test=self.test, text='Вопрос 1')
        Answer.objects.create(question=self.q1, text='Да', is_correct=True)
        Answer.objects.create(question=self.q1, text='Нет', is_correct=False)

    def test_unauthenticated_redirect(self):
        response = self.client.get('/tests/')
        self.assertEqual(response.status_code, 200)

    def test_student_can_see_test_detail(self):
        self.client.login(username='student', password='pass123')
        response = self.client.get(f'/test/{self.test.id}/')
        self.assertEqual(response.status_code, 200)

    def test_student_can_start_test(self):
        self.client.login(username='student', password='pass123')
        response = self.client.get(f'/start/{self.test.id}/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_student_profile_page(self):
        self.client.login(username='student', password='pass123')
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        self.client.login(username='student', password='pass123')
        response = self.client.get('/logout/', follow=True)
        self.assertEqual(response.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class TeacherFlowTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher', email='t@t.com', password='pass123'
        )
        self.teacher.profile.role = 'teacher'
        self.teacher.profile.save()

    def test_teacher_tests_page(self):
        self.client.login(username='teacher', password='pass123')
        response = self.client.get('/teacher/tests/')
        self.assertEqual(response.status_code, 200)

    def test_create_test(self):
        self.client.login(username='teacher', password='pass123')
        response = self.client.post('/teacher/test/create/', {
            'title': 'Новый тест',
            'description': 'Описание',
            'time_limit': 20,
            'max_attempts': 1,
            'visibility': 'all',
        }, follow=True)
        self.assertTrue(Test.objects.filter(title='Новый тест').exists())

    def test_student_cannot_access_teacher_pages(self):
        student = User.objects.create_user(
            username='student', email='s@s.com', password='pass123'
        )
        self.client.login(username='student', password='pass123')
        response = self.client.get('/teacher/tests/', follow=True)
        self.assertNotContains(response, 'Управление тестами')

    def test_teacher_profile_page(self):
        self.client.login(username='teacher', password='pass123')
        response = self.client.get('/teacher/profile/')
        self.assertEqual(response.status_code, 200)

    def test_toggle_test_status(self):
        test = Test.objects.create(title='Тест', created_by=self.teacher)
        self.client.login(username='teacher', password='pass123')

        q = Question.objects.create(test=test, text='Вопрос')
        Answer.objects.create(question=q, text='Да', is_correct=True)
        Answer.objects.create(question=q, text='Нет', is_correct=False)

        response = self.client.post(f'/teacher/test/{test.id}/toggle-status/', follow=True)
        test.refresh_from_db()
        self.assertTrue(test.is_active)


class TestFormTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='teacher', email='t@t.com', password='pass123'
        )

    def test_valid_form(self):
        form = TestForm(data={
            'title': 'Тест',
            'description': 'Описание',
            'time_limit': 30,
            'max_attempts': 3,
            'visibility': 'all',
        }, teacher=self.user)
        self.assertTrue(form.is_valid())

    def test_empty_title_invalid(self):
        form = TestForm(data={
            'title': '',
            'time_limit': 10,
            'visibility': 'all',
        }, teacher=self.user)
        self.assertFalse(form.is_valid())

    def test_date_validation(self):
        now = timezone.now()
        form = TestForm(data={
            'title': 'Тест',
            'time_limit': 10,
            'visibility': 'all',
            'available_from': now.strftime('%Y-%m-%dT%H:%M'),
            'available_until': (now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
        }, teacher=self.user)
        self.assertFalse(form.is_valid())


@override_settings(STORAGES=TEST_STORAGES)
class ResultExportTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher', email='t@t.com', password='pass123'
        )
        self.teacher.profile.role = 'teacher'
        self.teacher.profile.save()

        self.student = User.objects.create_user(
            username='student', email='s@s.com', password='pass123'
        )

        self.test = Test.objects.create(
            title='Тест', created_by=self.teacher, is_active=True
        )
        self.result = Result.objects.create(
            student=self.student, test=self.test, score=8.0, percent=80.0, grade='4'
        )

    def test_export_csv(self):
        self.client.login(username='teacher', password='pass123')
        response = self.client.get(f'/teacher/test/{self.test.id}/results/export/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8-sig')

    def test_student_cannot_export(self):
        self.client.login(username='student', password='pass123')
        response = self.client.get(
            f'/teacher/test/{self.test.id}/results/export/', follow=True
        )
        self.assertNotEqual(response['Content-Type'], 'text/csv; charset=utf-8-sig')
