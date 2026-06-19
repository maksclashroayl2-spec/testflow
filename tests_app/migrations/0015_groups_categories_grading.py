from django.db import migrations, models
import django.db.models.deletion


DEFAULT_CATEGORIES = [
    'Информатика',
    'ПМ.01',
    'ПМ.02',
    'ПМ.11',
    'Алгоритмы',
    'Сети',
    'HTML',
    'ООП',
    'Операционные системы',
    'Графика',
    'ТСИ',
]


def seed_categories(apps, schema_editor):
    TestCategory = apps.get_model('tests_app', 'TestCategory')
    for name in DEFAULT_CATEGORIES:
        TestCategory.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0014_add_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='TestCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Категория',
                'verbose_name_plural': 'Категории',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='StudentGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название группы')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_groups', to='auth.user', verbose_name='Преподаватель')),
            ],
            options={
                'verbose_name': 'Группа',
                'verbose_name_plural': 'Группы',
                'ordering': ['name'],
                'unique_together': {('name', 'created_by')},
            },
        ),
        migrations.AddField(
            model_name='profile',
            name='student_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to='tests_app.studentgroup', verbose_name='Группа'),
        ),
        migrations.AddField(
            model_name='test',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tests', to='tests_app.testcategory', verbose_name='Категория'),
        ),
        migrations.AddField(
            model_name='test',
            name='shuffle_answers',
            field=models.BooleanField(default=False, verbose_name='Перемешивать ответы'),
        ),
        migrations.AddField(
            model_name='test',
            name='shuffle_questions',
            field=models.BooleanField(default=False, verbose_name='Перемешивать вопросы'),
        ),
        migrations.AddField(
            model_name='test',
            name='visibility',
            field=models.CharField(choices=[('all', 'Для всех студентов'), ('groups', 'Только для выбранных групп')], default='all', max_length=20, verbose_name='Видимость'),
        ),
        migrations.AddField(
            model_name='result',
            name='grading_status',
            field=models.CharField(choices=[('graded', 'Проверено'), ('pending_review', 'На проверке')], default='graded', max_length=20, verbose_name='Статус проверки'),
        ),
        migrations.AddField(
            model_name='result',
            name='text_reviews',
            field=models.JSONField(default=dict, verbose_name='Проверка текстовых ответов'),
        ),
        migrations.AddField(
            model_name='test',
            name='assigned_groups',
            field=models.ManyToManyField(blank=True, related_name='assigned_tests', to='tests_app.studentgroup', verbose_name='Группы'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/', verbose_name='Аватар'),
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
