"""Specializuotos formos el. pašto veiksmams."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.urls import NoReverseMatch, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .services import EmailTemplateNotFound, send_templated_email

logger = logging.getLogger(__name__)


def _user_display(user) -> str:
    full_name = user.get_full_name()
    if full_name:
        return full_name
    email_field_name = user.__class__.get_email_field_name()
    email_value = getattr(user, email_field_name, "")
    if email_value:
        return email_value
    return user.get_username()


class TemplatedPasswordResetForm(PasswordResetForm):
    """Password reset forma, kuri naudoja DB saugomus šablonus."""

    def save(
        self,
        domain_override: str | None = None,
        subject_template_name: str | None = None,
        email_template_name: str | None = None,
        use_https: bool = False,
        token_generator=default_token_generator,
        from_email: str | None = None,
        request=None,
        html_email_template_name: str | None = None,
        extra_email_context: dict[str, Any] | None = None,
    ) -> str:
        email = self.cleaned_data["email"]
        UserModel = get_user_model()
        email_field_name = UserModel.get_email_field_name()
        protocol = "https" if (use_https or (
            request and request.is_secure())) else "http"
        domain = domain_override or (
            request.get_host() if request else settings.PRIMARY_DOMAIN)
        site_name = domain_override or settings.PRIMARY_DOMAIN
        frontend_base = (settings.FRONTEND_URL or "").rstrip(
            "/") or f"{protocol}://{domain}"
        reset_path_template = getattr(
            settings,
            "PASSWORD_RESET_FRONTEND_PATH",
            "/auth/reset-password/{uid}/{token}",
        )
        timeout_seconds = getattr(settings, "PASSWORD_RESET_TIMEOUT", 60 * 60)
        valid_minutes = max(1, int(timeout_seconds / 60))

        users = list(self.get_users(email))
        if not users:
            logger.debug(
                "Password reset requested for %s, but no active users found", email)
            return email

        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            try:
                backend_path = reverse(
                    "password_reset_confirm",
                    kwargs={"uidb64": uid, "token": token},
                )
                backend_reset_url = f"{protocol}://{domain}{backend_path}"
            except NoReverseMatch:
                backend_reset_url = ""

            formatted_path = reset_path_template.format(uid=uid, token=token)
            if not formatted_path.startswith("/"):
                formatted_path = f"/{formatted_path}"
            reset_url = f"{frontend_base}{formatted_path}"

            context = {
                "email": getattr(user, email_field_name),
                "domain": domain,
                "site_name": site_name,
                "uid": uid,
                "token": token,
                "protocol": protocol,
                "user_name": _user_display(user),
                "reset_url": reset_url,
                "backend_reset_url": backend_reset_url,
                "valid_minutes": valid_minutes,
            }
            if extra_email_context:
                context.update(extra_email_context)

            try:
                send_templated_email(
                    key="password_reset",
                    recipients=[context["email"]],
                    context=context,
                    from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                )
            except EmailTemplateNotFound:
                logger.warning(
                    "Nerastas slaptažodžio šablonas 'password_reset' – laiškas nesiųstas (user_id=%s)",
                    user.pk,
                )
            except Exception:  # pragma: no cover - gynybinis log'as
                logger.exception(
                    "Nepavyko išsiųsti slaptažodžio atkūrimo laiško (user_id=%s)",
                    user.pk,
                )

        return email
