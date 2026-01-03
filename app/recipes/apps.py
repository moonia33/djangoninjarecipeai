"""Programėlės konfigūracija."""

from django.apps import AppConfig


class RecipesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recipes"
    verbose_name = "Receptai"

    def ready(self) -> None:
        from . import signals  # noqa: F401
