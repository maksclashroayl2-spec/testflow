def _grade_from_percent(percent):
    if percent >= 85:
        return "5"
    if percent >= 70:
        return "4"
    if percent >= 50:
        return "3"
    return "2"


def _text_review_entry(question, user_text, text_reviews=None):
    text_reviews = text_reviews or {}
    review = text_reviews.get(str(question.id), {})

    if review.get('reviewed'):
        return float(review.get('score', 0))

    user_norm = user_text.strip().lower()
    correct_norm = str(question.correct_text or '').strip().lower()

    if user_norm and correct_norm and user_norm == correct_norm:
        return 1.0

    return 0.0


def calculate_score(test, answers, text_reviews=None):
    score = 0.0
    pending_text = False

    for question in test.questions.all():
        if question.question_type == 'text':
            user_text = str(answers.get(str(question.id), '')).strip()
            review = (text_reviews or {}).get(str(question.id), {})

            if review.get('reviewed'):
                score += float(review.get('score', 0))
                continue

            user_norm = user_text.lower()
            correct_norm = str(question.correct_text or '').strip().lower()

            if user_norm and correct_norm and user_norm == correct_norm:
                score += 1.0
            elif user_text:
                pending_text = True
        else:
            correct_ids = set(
                question.answers.filter(is_correct=True).values_list('id', flat=True)
            )
            raw_user_answers = answers.get(str(question.id), [])

            try:
                user_ids = set(map(int, raw_user_answers))
            except (TypeError, ValueError):
                user_ids = set()

            if correct_ids:
                score += len(correct_ids & user_ids) / len(correct_ids)

    total = test.questions.count()
    percent = round((score / total) * 100, 1) if total else 0.0

    return {
        'score': round(score, 2),
        'percent': percent,
        'grade': _grade_from_percent(percent),
        'grading_status': 'pending_review' if pending_text else 'graded',
    }


def build_initial_text_reviews(test, answers):
    reviews = {}

    for question in test.questions.filter(question_type='text'):
        user_text = str(answers.get(str(question.id), '')).strip()
        correct_norm = str(question.correct_text or '').strip().lower()
        user_norm = user_text.lower()
        auto_matched = bool(user_norm and correct_norm and user_norm == correct_norm)

        reviews[str(question.id)] = {
            'user_text': user_text,
            'auto_matched': auto_matched,
            'reviewed': auto_matched,
            'score': 1.0 if auto_matched else 0.0,
            'comment': '',
        }

    return reviews


def apply_text_review_updates(result, post_data):
    text_reviews = dict(result.text_reviews or {})

    for question in result.test.questions.filter(question_type='text'):
        qid = str(question.id)
        if qid not in text_reviews:
            continue

        field_name = f'review_score_{qid}'
        if field_name not in post_data:
            continue

        score_value = post_data.get(field_name, '0')
        try:
            score = 1.0 if score_value in ('1', '1.0', 'true', 'on') else 0.0
        except (TypeError, ValueError):
            score = 0.0

        text_reviews[qid]['score'] = score
        text_reviews[qid]['reviewed'] = True
        text_reviews[qid]['comment'] = post_data.get(f'review_comment_{qid}', '').strip()

    metrics = calculate_score(result.test, result.answers, text_reviews)
    has_pending = any(
        not item.get('reviewed')
        for item in text_reviews.values()
    )

    result.text_reviews = text_reviews
    result.score = metrics['score']
    result.percent = metrics['percent']
    result.grade = metrics['grade']
    result.grading_status = 'pending_review' if has_pending else 'graded'
    result.save()

    return result
