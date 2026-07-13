"""
WSGI config for PoultryFarm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import OperationalError, ProgrammingError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PoultryFarm.settings')

application = get_wsgi_application()

if settings.IS_VERCEL and not os.environ.get('DATABASE_URL'):
    call_command('migrate', interactive=False, verbosity=0)


def bootstrap_superuser():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
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


try:
    bootstrap_superuser()
except (OperationalError, ProgrammingError):
    pass
