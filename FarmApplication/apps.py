from django.apps import AppConfig


class FarmapplicationConfig(AppConfig):
    name = 'FarmApplication'
    verbose_name = 'Farm Operations'

    def ready(self):
        from . import checks  # noqa: F401
