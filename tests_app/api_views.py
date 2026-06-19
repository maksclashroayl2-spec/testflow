from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Test, Question, Answer, Result, Profile
from .serializers import (
    TestListSerializer, TestDetailSerializer, TestDetailStudentSerializer,
    QuestionSerializer, AnswerSerializer,
    ResultSerializer, ProfileSerializer,
)


class IsTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.role == 'teacher'
        )


class TestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.profile.role == 'teacher':
            return Test.objects.filter(created_by=user).order_by('-created_at')
        return Test.objects.filter(is_active=True).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            if self.request.user.profile.role == 'teacher':
                return TestDetailSerializer
            return TestDetailStudentSerializer
        return TestListSerializer

    @action(detail=True, methods=['get'], url_path='availability')
    def availability(self, request, pk=None):
        test = self.get_object()
        now = timezone.now()

        if test.available_from and now < test.available_from:
            return Response({
                'available': False,
                'message': f'Тест будет доступен с {test.available_from.strftime("%d.%m.%Y %H:%M")}.',
            })

        if test.available_until and now > test.available_until:
            return Response({
                'available': False,
                'message': 'Срок прохождения теста завершён.',
            })

        return Response({'available': True, 'message': 'Тест доступен.'})


class ResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.profile.role == 'teacher':
            return Result.objects.filter(
                test__created_by=user
            ).select_related('student', 'student__profile', 'test').order_by('-created_at')
        return Result.objects.filter(
            student=user
        ).select_related('test').order_by('-created_at')


class ProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        profile = request.user.profile

        if request.method == 'PATCH':
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        serializer = ProfileSerializer(profile)
        return Response(serializer.data)
