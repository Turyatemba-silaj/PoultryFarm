from django.conf import settings
from django.core.checks import Warning, register


@register()
def persistent_database_check(app_configs, **kwargs):
    if not settings.IS_VERCEL:
        return []

    engine = settings.DATABASES["default"]["ENGINE"]
    if "sqlite3" not in engine:
        return []

    return [
        Warning(
            "Vercel is using temporary SQLite storage; records will not persist reliably.",
            hint="Set DATABASE_URL, POSTGRES_URL, or POSTGRES_URL_NON_POOLING to a persistent Postgres database and redeploy.",
            id="FarmApplication.W001",
        )
    ]
