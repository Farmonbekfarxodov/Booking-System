"""Booking System settings. Barcha maxfiy qiymatlar .env dan olinadi."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",      # ExclusionConstraint, range maydonlar uchun
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    # loyiha app'lari
    "accounts",
    "catalog",
    "scheduling",
    "bookings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "booking"),
        "USER": os.getenv("POSTGRES_USER", "booking"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "booking"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Vaqtlar bazada doim UTC da saqlanadi; TIME_ZONE faqat admin panel ko'rinishi uchun
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Booking System API",
    "DESCRIPTION": "Appointment booking system: services, providers, availability, bookings.",
    "VERSION": "0.1.0",
    "ENUM_NAME_OVERRIDES": {"BookingStatusEnum": "bookings.models.Booking.Status"},
}

# ---------- Booking biznes qoidalari ----------
BOOKING_SLOT_STEP_MINUTES = int(os.getenv("BOOKING_SLOT_STEP_MINUTES", 15))   # slotlar orasidagi qadam
BOOKING_MIN_NOTICE_MINUTES = int(os.getenv("BOOKING_MIN_NOTICE_MINUTES", 60))  # kamida shuncha oldin band qilinadi
BOOKING_MAX_ADVANCE_DAYS = int(os.getenv("BOOKING_MAX_ADVANCE_DAYS", 60))      # eng ko'pi shuncha kun oldinga
BOOKING_CANCEL_DEADLINE_HOURS = int(os.getenv("BOOKING_CANCEL_DEADLINE_HOURS", 2))  # mijoz shundan kech bekor qila olmaydi
