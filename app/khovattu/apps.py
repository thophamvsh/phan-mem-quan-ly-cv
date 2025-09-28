from django.apps import AppConfig


class KhovattuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'khovattu'

    def ready(self):
        import khovattu.signals