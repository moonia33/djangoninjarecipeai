"""Signalai, paleidžiantys automatinius pranešimus."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import EmailTemplateNotFound, send_templated_email

logger = logging.getLogger(__name__)
User = get_user_model()


def _user_name(user: User) -> str:
    return user.get_full_name() or user.get_username() or user.email


@receiver(post_save, sender=User)
def send_registration_email(sender, instance: User, created: bool, **kwargs):
    """Sveikinimo laiškas po registracijos arba admino sukurto vartotojo."""

    if not created:
        return
    if not instance.email:
        logger.debug(
            "Registracijos laiškas nepritaikytas, nes vartotojas neturi el. pašto (user_id=%s)",
            instance.pk,
        )
        return

    context = {"user_name": _user_name(instance)}

    try:
        send_templated_email(key="welcome", recipients=[
                             instance.email], context=context)
    except EmailTemplateNotFound:
        logger.warning(
            "Nerastas 'welcome' šablonas – praleidžiamas registracijos laiškas (user_id=%s)",
            instance.pk,
        )
    except Exception:  # pragma: no cover - ginybinis log'as
        logger.exception(
            "Nepavyko išsiųsti registracijos laiško (user_id=%s)",
            instance.pk,
        )
