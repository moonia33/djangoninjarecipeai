from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserConsents(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="consents",
        on_delete=models.CASCADE,
    )

    newsletter_consent = models.BooleanField(default=False)
    newsletter_consent_at = models.DateTimeField(null=True, blank=True)

    privacy_policy_consent = models.BooleanField(default=False)
    privacy_policy_consent_at = models.DateTimeField(null=True, blank=True)

    terms_of_service_consent = models.BooleanField(default=False)
    terms_of_service_consent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_consent(self, field_name: str, value: bool) -> None:
        setattr(self, field_name, bool(value))
        at_field = f"{field_name}_at"
        if value:
            setattr(self, at_field, timezone.now())
        else:
            setattr(self, at_field, None)

    def __str__(self) -> str:  # pragma: no cover
        return f"Consents for user {self.user_id}"
