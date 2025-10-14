import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SECURITY SETTINGS ---
# It is highly recommended to set these in your environment (e.g., in a .env file or
# directly in the PythonAnywhere "Environment variables" section).

# SECRET_KEY: Get from environment or use a default (default is insecure for production)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-h$s2zpd@rk9x_tcl!o5(v@n=mxby(0rl2=k)(t(tzzmc1rl=s2')

# DEBUG: Get from environment, defaulting to False for production safety.
# Set DJANGO_DEBUG=True in your .env file for local development.
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

# ALLOWED_HOSTS: Get from environment.
# On PythonAnywhere, set DJANGO_ALLOWED_HOSTS in the "Environment variables" section
# to your domain, e.g., 'your-username.pythonanywhere.com'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')


# --- APPLICATION DEFINITION ---

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'main',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tk_7.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'main.context_processors.tahun_ajaran',
            ],
        },
    },
]

WSGI_APPLICATION = 'tk_7.wsgi.application'


# --- DATABASE ---
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# --- PASSWORD VALIDATION ---
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- INTERNATIONALIZATION ---
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True


# --- STATIC & MEDIA FILES ---

# URL to use when referring to static files located in STATIC_ROOT
STATIC_URL = 'static/'
# Directory where `collectstatic` will gather all static files.
STATIC_ROOT = BASE_DIR / 'staticfiles'

# URL for user-uploaded media files
MEDIA_URL = '/media/'
# Directory where user-uploaded media files will be stored
MEDIA_ROOT = BASE_DIR / 'media'


# --- OTHER SETTINGS ---

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Gemini API Key - loaded from environment
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')