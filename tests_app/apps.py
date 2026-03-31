from django.apps import AppConfig


class TestsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tests_app'

    def ready(self):
        import tests_app.signals