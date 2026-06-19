from rest_framework import serializers
from .models import Test, Question, Answer, Result, Profile


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'text', 'is_correct']


class AnswerStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'image', 'question_type', 'correct_text', 'answers']


class QuestionStudentSerializer(serializers.ModelSerializer):
    answers = AnswerStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'image', 'question_type', 'answers']


class TestListSerializer(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'title', 'description', 'created_by_name',
            'created_at', 'time_limit', 'is_active', 'max_attempts',
            'available_from', 'available_until', 'questions_count',
            'category_name', 'visibility', 'shuffle_questions', 'shuffle_answers',
        ]

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_questions_count(self, obj):
        return obj.questions.count()

    def get_created_by_name(self, obj):
        return obj.created_by.profile.full_name or obj.created_by.email


class TestDetailSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'title', 'description', 'created_by_name',
            'created_at', 'time_limit', 'is_active', 'max_attempts',
            'available_from', 'available_until', 'questions',
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.profile.full_name or obj.created_by.email


class TestDetailStudentSerializer(serializers.ModelSerializer):
    questions = QuestionStudentSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'title', 'description', 'created_by_name',
            'created_at', 'time_limit', 'is_active', 'max_attempts',
            'available_from', 'available_until', 'questions',
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.profile.full_name or obj.created_by.email


class ResultSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    test_title = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = [
            'id', 'student_name', 'test_title', 'score',
            'percent', 'grade', 'grading_status', 'created_at',
        ]

    def get_student_name(self, obj):
        return obj.student.profile.full_name or obj.student.email

    def get_test_title(self, obj):
        return obj.test.title


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'username', 'email', 'full_name', 'role', 'bio', 'student_group']
