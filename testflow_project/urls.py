from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from tests_app.api_views import TestViewSet, ResultViewSet, ProfileViewSet

router = DefaultRouter()
router.register(r'tests', TestViewSet, basename='api-test')
router.register(r'results', ResultViewSet, basename='api-result')
router.register(r'profiles', ProfileViewSet, basename='api-profile')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls')),
    path('', include('tests_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)