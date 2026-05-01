import os

DJANGO_ENV = os.environ.get('DJANGO_ENV', 'dev').lower()

if DJANGO_ENV == 'prod':
    from .settings_prod import *  # noqa
else:
    from .settings_dev import *  # noqa
