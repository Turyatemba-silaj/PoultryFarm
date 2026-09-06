"""
WSGI config for PoultryFarm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, ProgrammingError
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PoultryFarm.settings')


application = get_wsgi_application()


def serve_static_assets(application):
    if settings.DEBUG:
        return application

    static_application = WhiteNoise(application)
    static_application.add_files(
        settings.BUNDLE_DIR / 'FarmApplication' / 'static',
        prefix='static/',
    )
    static_application.add_files(
        Path(django_admin.__file__).resolve().parent / 'static' / 'admin',
        prefix='static/admin/',
    )
    return static_application


application = serve_static_assets(application)


def run_startup_tasks():
    if not settings.IS_VERCEL:
        return

    call_command('migrate', interactive=False, verbosity=0)
    bootstrap_superuser()
    load_initial_farm_data()


def bootstrap_superuser():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'Andrew')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'poultryFarm2026')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

    if not username or not password:
        return

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'is_staff': True,
            'is_superuser': True,
        },
    )
    user.email = email or user.email
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()
    print(f'Vercel admin bootstrap ready: {username}')


def load_initial_farm_data():
    from FarmApplication.models import EggProduction, FeedConsumption, FeedMix, Purchase, Sale

    has_farm_data = any(
        model.objects.exists()
        for model in (Purchase, FeedMix, FeedConsumption, EggProduction, Sale)
    )
    fixture_path = settings.BUNDLE_DIR / 'FarmApplication' / 'fixtures' / 'initial_data.json'

    if has_farm_data or not fixture_path.exists():
        return

    call_command('loaddata', str(fixture_path), interactive=False, verbosity=0)
    print('Loaded initial farm data fixture.')


try:
    run_startup_tasks()
except (OperationalError, ProgrammingError):
    pass


