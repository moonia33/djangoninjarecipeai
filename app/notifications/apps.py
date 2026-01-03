from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "El. pašto pranešimai"

    def ready(self) -> None:  # pragma: no cover - import side effect
        from . import signals  # noqa: F401
