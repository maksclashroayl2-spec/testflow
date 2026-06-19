import json
from .models import Question, Answer


def export_test_to_dict(test):
    data = {
        'title': test.title,
        'description': test.description,
        'time_limit': test.time_limit,
        'max_attempts': test.max_attempts,
        'category': test.category.name if test.category else None,
        'shuffle_questions': test.shuffle_questions,
        'shuffle_answers': test.shuffle_answers,
        'questions': [],
    }

    for question in test.questions.prefetch_related('answers').all():
        q_data = {
            'text': question.text,
            'type': 'text' if question.question_type == 'text' else 'single',
            'correct_text': question.correct_text,
            'answers': [],
        }

        correct_count = question.answers.filter(is_correct=True).count()
        if question.question_type != 'text' and correct_count > 1:
            q_data['type'] = 'multiple'

        for answer in question.answers.all():
            q_data['answers'].append({
                'text': answer.text,
                'is_correct': answer.is_correct,
            })

        data['questions'].append(q_data)

    return data


def import_questions_from_dict(test, payload):
    questions_data = payload.get('questions', [])
    created = 0

    for item in questions_data:
        q_type = item.get('type', 'single')
        question_type = 'text' if q_type == 'text' else 'multiple'

        question = Question.objects.create(
            test=test,
            text=item.get('text', '').strip(),
            question_type=question_type,
            correct_text=item.get('correct_text') if question_type == 'text' else None,
        )
        created += 1

        if question_type != 'text':
            for answer_item in item.get('answers', []):
                Answer.objects.create(
                    question=question,
                    text=answer_item.get('text', ''),
                    is_correct=bool(answer_item.get('is_correct')),
                )

    return created


def parse_test_json_file(uploaded_file):
    content = uploaded_file.read().decode('utf-8')
    return json.loads(content)
