"""
WSGI config for tk_7 project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

<<<<<<< HEAD
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tk_7.settings')

application = get_wsgi_application()
=======
print("\n!!!!!!!!!! WSGI FILE IS RUNNING !!!!!!!!!!!\n")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tk_7.settings')

application = get_wsgi_application()

print("\n!!!!!!!!!! WSGI APPLICATION CREATED !!!!!!!!!!!\n")

>>>>>>> 9b78fbe049163d23ecef90cfa98626ad3a8f1fa3
