"""Pagrindiniai Django nustatymai pagal projekto gaires."""

from pathlib import Path
from urllib.parse import urlparse

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(env_file)

PRIMARY_DOMAIN = env("PRIMARY_DOMAIN", default="apetitas.lt")
API_HOST = env("API_HOST", default=f"api.{PRIMARY_DOMAIN}")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-development-key")
DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", API_HOST]
)
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", default=[f"https://{API_HOST}"]
)

COOKIE_DOMAIN = env("DJANGO_COOKIE_DOMAIN", default=None)
if COOKIE_DOMAIN:
    SESSION_COOKIE_DOMAIN = COOKIE_DOMAIN
    CSRF_COOKIE_DOMAIN = COOKIE_DOMAIN

SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=not DEBUG)

SITE_URL = env("SITE_URL", default=f"https://{PRIMARY_DOMAIN}")
FRONTEND_URL = env("FRONTEND_URL", default=SITE_URL)

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "django_filters",
    "storages",
    "imagekit",
]

LOCAL_APPS = [
    "accounts.apps.AccountsConfig",
    "recipes.apps.RecipesConfig",
    "ai.apps.AiConfig",
    "notifications",
    "sitecontent",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "recipe_platform.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "recipe_platform.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "lt"
TIME_ZONE = "Europe/Vilnius"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR /
                    "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = env("MEDIA_URL", default="/media/")
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_S3 = env.bool("DJANGO_USE_S3", default=False)
if USE_S3:
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default=None)
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
    AWS_QUERYSTRING_AUTH = False

    custom_domain_url = None
    if AWS_S3_CUSTOM_DOMAIN:
        parsed = urlparse(AWS_S3_CUSTOM_DOMAIN)
        if parsed.scheme and parsed.netloc:
            custom_domain_url = f"{parsed.scheme}://{parsed.netloc}/"
            AWS_S3_CUSTOM_DOMAIN = parsed.netloc
        else:
            AWS_S3_CUSTOM_DOMAIN = AWS_S3_CUSTOM_DOMAIN.strip().strip("/")
            custom_domain_url = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = custom_domain_url or f"https://{AWS_S3_CUSTOM_DOMAIN}/"
    elif AWS_S3_ENDPOINT_URL:
        MEDIA_URL = f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{AWS_STORAGE_BUCKET_NAME}/"
    else:
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[FRONTEND_URL])
CORS_ALLOW_CREDENTIALS = True

EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("DJANGO_EMAIL_USE_SSL", default=False)
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False

DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default=f"no-reply@{PRIMARY_DOMAIN}",
)
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[Gero Apetito] ",
)
PASSWORD_RESET_FRONTEND_PATH = env(
    "PASSWORD_RESET_FRONTEND_PATH",
    default="/auth/reset-password/{uid}/{token}",
)
COMMENT_NOTIFICATION_RECIPIENTS = env.list(
    "COMMENT_NOTIFICATION_RECIPIENTS",
    default=[SERVER_EMAIL] if SERVER_EMAIL else [],
)

# OpenAI (AI generation, nutrition)
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_NUTRITION_MODEL = env("OPENAI_NUTRITION_MODEL", default="gpt-4o-mini")
OPENAI_META_MODEL = env("OPENAI_META_MODEL", default="gpt-4o-mini")
OPENAI_RECIPE_MODEL = env("OPENAI_RECIPE_MODEL", default="gpt-4o-mini")
OPENAI_IMAGE_MODEL = env("OPENAI_IMAGE_MODEL", default="gpt-image-1")
OPENAI_IMAGE_FALLBACK_MODEL = env("OPENAI_IMAGE_FALLBACK_MODEL", default="dall-e-3")
OPENAI_IMAGE_SIZE = env("OPENAI_IMAGE_SIZE", default="1024x1024")
OPENAI_REQUEST_TIMEOUT_SECONDS = env.int("OPENAI_REQUEST_TIMEOUT_SECONDS", default=60)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

NINJA_BASE_PATH = env("NINJA_BASE_PATH", default="api/").strip("/")

# Ninja OpenAPI/Swagger docs
# Production default is disabled; enable explicitly via env when needed.
NINJA_ENABLE_DOCS = env.bool("NINJA_ENABLE_DOCS", default=DEBUG)
# When docs are enabled in production, restrict access to Django staff users.
NINJA_DOCS_REQUIRE_STAFF = env.bool("NINJA_DOCS_REQUIRE_STAFF", default=not DEBUG)
