"""
WSGI config for PoultryFarm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.conf import settings
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PoultryFarm.settings')

application = get_wsgi_application()

if settings.IS_VERCEL and not os.environ.get('DATABASE_URL'):
    call_command('migrate', interactive=False, verbosity=0)

