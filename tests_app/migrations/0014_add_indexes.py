from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0013_test_available_from_test_available_until'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['student'], name='result_student_idx'),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['test'], name='result_test_idx'),
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['test'], name='question_test_idx'),
        ),
        migrations.AddIndex(
            model_name='answer',
            index=models.Index(fields=['question'], name='answer_question_idx'),
        ),
    ]
