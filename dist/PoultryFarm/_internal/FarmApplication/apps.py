from django.apps import AppConfig


class FarmapplicationConfig(AppConfig):
    name = 'FarmApplication'

    def ready(self):
        from . import checks  # noqa: F401
