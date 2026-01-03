"""Pagalbinės funkcijos laiškų siuntimui."""

from collections.abc import Iterable, Sequence
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import EmailTemplate


class EmailTemplateNotFound(Exception):
    """Išmetama, kai nerandame aktyvaus šablono pagal raktažodį."""


def get_template(key: str) -> EmailTemplate:
    try:
        return EmailTemplate.objects.get(key=key, is_active=True)
    except EmailTemplate.DoesNotExist as exc:  # pragma: no cover - paprasta validacija
        raise EmailTemplateNotFound(
            f"Nerastas el. laiško šablonas '{key}'.") from exc


def render_email_parts(key: str, context: dict[str, Any] | None = None) -> tuple[str, str, str]:
    template = get_template(key)
    return (
        template.render_subject(context),
        template.render_text(context),
        template.render_html(context),
    )


def send_templated_email(
    *,
    key: str,
    recipients: Sequence[str] | Iterable[str],
    context: dict[str, Any] | None = None,
    from_email: str | None = None,
    attachments: Sequence[tuple[str, bytes, str]] | None = None,
    reply_to: Sequence[str] | None = None,
    bcc: Sequence[str] | None = None,
) -> EmailMultiAlternatives:
    subject, body_text, body_html = render_email_parts(key, context)
    body = body_text or body_html
    email = EmailMultiAlternatives(
        subject=subject or key,
        body=body,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=list(recipients),
        reply_to=list(reply_to or []),
        bcc=list(bcc or []),
    )
    if body_html:
        email.attach_alternative(body_html, "text/html")
    for attachment in attachments or []:
        email.attach(*attachment)
    email.send()
    return email
