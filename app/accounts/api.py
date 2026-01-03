"""Autentifikacijos susiję API maršrutai."""

import re

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.http import urlsafe_base64_decode
from ninja import Router
from ninja.errors import HttpError

from notifications.forms import TemplatedPasswordResetForm

from .models import UserConsents
from .schemas import (
    LoginRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetConfirmRequestSchema,
    PasswordResetConfirmResponseSchema,
    PasswordResetResponseSchema,
    RegisterRequestSchema,
    SessionSchema,
    UpdateConsentsRequestSchema,
    UpdateConsentsResponseSchema,
    UserConsentsSchema,
    UserPublicWithConsentsSchema,
)

router = Router(tags=["Auth"])
User = get_user_model()


def _serialize_user(user) -> UserPublicWithConsentsSchema:
    consents_obj = None
    try:
        consents_obj = getattr(user, "consents", None)
    except Exception:
        consents_obj = None

    if consents_obj is None and user and getattr(user, "pk", None):
        consents_obj, _ = UserConsents.objects.get_or_create(user=user)

    consents_schema = None
    if consents_obj is not None:
        consents_schema = UserConsentsSchema(
            newsletter_consent=bool(consents_obj.newsletter_consent),
            privacy_policy_consent=bool(consents_obj.privacy_policy_consent),
            terms_of_service_consent=bool(consents_obj.terms_of_service_consent),
            newsletter_consent_at=consents_obj.newsletter_consent_at,
            privacy_policy_consent_at=consents_obj.privacy_policy_consent_at,
            terms_of_service_consent_at=consents_obj.terms_of_service_consent_at,
        )

    return UserPublicWithConsentsSchema(
        id=user.id,
        email=user.email or "",
        username=user.get_username(),
        full_name=user.get_full_name() or None,
        consents=consents_schema,
    )


def _authenticate_credentials(request, identifier: str, password: str):
    identity = (identifier or "").strip()
    user = authenticate(request, username=identity, password=password)
    if user:
        return user
    if "@" in identity:
        try:
            user_obj = User.objects.get(email__iexact=identity)
        except User.DoesNotExist:
            return None
        return authenticate(request, username=user_obj.get_username(), password=password)
    return None


def _session_payload(request, user=None) -> SessionSchema:
    current_user = user or (request.user if request.user.is_authenticated else None)
    return SessionSchema(
        is_authenticated=current_user is not None,
        csrf_token=get_token(request),
        user=_serialize_user(current_user) if current_user else None,
    )


def _schema_dump(schema) -> dict:
    if hasattr(schema, "model_dump"):
        return schema.model_dump()  # type: ignore[no-any-return]
    return schema.dict()  # type: ignore[no-any-return]


def _generate_username_from_email(email: str) -> str:
    base = (email.split("@", 1)[0] if "@" in email else email).strip().lower()
    base = re.sub(r"[^a-z0-9_\.\-]+", "-", base).strip("-._")
    base = base or "user"

    username = base
    counter = 1
    while User.objects.filter(username__iexact=username).exists():
        counter += 1
        username = f"{base}-{counter}"
    return username


@router.get("/session", response=SessionSchema)
@ensure_csrf_cookie
def get_session(request):
    """Grąžina naudotojo sesijos būseną ir atnaujina CSRF slapuką."""

    payload = _session_payload(request)
    return JsonResponse(_schema_dump(payload))


@router.post("/login", response=SessionSchema)
@csrf_protect
def login_user(request, payload: LoginRequestSchema):
    """Autentikuoja naudotoją ir sukuria sesiją."""

    user = _authenticate_credentials(request, payload.identifier, payload.password)
    if not user:
        raise HttpError(401, "Neteisingi prisijungimo duomenys")
    if not user.is_active:
        raise HttpError(403, "Paskyra neaktyvi")

    login(request, user)
    session_payload = _session_payload(request, user)
    return JsonResponse(_schema_dump(session_payload))


@router.post("/logout", response=SessionSchema)
@csrf_protect
def logout_user(request):
    """Atsijungia ir sukuria naują CSRF tokeną naujam seansui."""

    logout(request)
    session_payload = _session_payload(request)
    return JsonResponse(_schema_dump(session_payload))


@router.post("/password-reset", response=PasswordResetResponseSchema)
@csrf_protect
def request_password_reset(request, payload: PasswordResetRequestSchema):
    """Priima el. paštą ir išsiunčia slaptažodžio atkūrimo laišką."""

    form = TemplatedPasswordResetForm(data={"email": payload.email})
    if not form.is_valid():
        raise HttpError(422, "Neteisingas el. pašto adresas")

    form.save(request=request, use_https=request.is_secure())
    return JsonResponse(_schema_dump(PasswordResetResponseSchema(sent=True)))


@router.post("/password-reset-confirm", response=PasswordResetConfirmResponseSchema)
@csrf_protect
def confirm_password_reset(request, payload: PasswordResetConfirmRequestSchema):
    """Patvirtina reset tokeną ir pakeičia slaptažodį."""

    try:
        uid = urlsafe_base64_decode(payload.uid).decode()
    except Exception:
        raise HttpError(400, "Netinkama slaptažodžio atkūrimo nuoroda")

    try:
        user = User.objects.get(pk=uid, is_active=True)
    except User.DoesNotExist:
        raise HttpError(400, "Netinkama slaptažodžio atkūrimo nuoroda")

    if not default_token_generator.check_token(user, payload.token):
        raise HttpError(400, "Slaptažodžio atkūrimo nuoroda nebegalioja")

    try:
        validate_password(payload.new_password, user=user)
    except ValidationError as exc:
        message = "; ".join(exc.messages) if exc.messages else "Neteisingas slaptažodis"
        raise HttpError(422, message)

    user.set_password(payload.new_password)
    user.save(update_fields=["password"])

    return JsonResponse(_schema_dump(PasswordResetConfirmResponseSchema(changed=True)))


@router.post("/register", response=SessionSchema)
@csrf_protect
def register_user(request, payload: RegisterRequestSchema):
    """Sukuria naudotoją ir prisijungia (sesija + CSRF)."""

    if request.user.is_authenticated:
        raise HttpError(400, "Jūs jau prisijungę")

    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HttpError(422, "Neteisingas el. pašto adresas")

    if User.objects.filter(email__iexact=email).exists():
        raise HttpError(400, "Naudotojas su tokiu el. paštu jau egzistuoja")

    username = (payload.username or "").strip()
    if not username:
        username = _generate_username_from_email(email)
    elif User.objects.filter(username__iexact=username).exists():
        raise HttpError(400, "Toks vartotojo vardas jau užimtas")

    # Password validation (Django validators)
    try:
        validate_password(payload.password)
    except ValidationError as exc:
        message = "; ".join(exc.messages) if exc.messages else "Neteisingas slaptažodis"
        raise HttpError(422, message)

    user = User.objects.create_user(username=username, email=email, password=payload.password)

    consents, _ = UserConsents.objects.get_or_create(user=user)
    consents.set_consent("newsletter_consent", payload.newsletter_consent)
    consents.set_consent("privacy_policy_consent", payload.privacy_policy_consent)
    consents.set_consent("terms_of_service_consent", payload.terms_of_service_consent)
    consents.save()

    full_name = (payload.full_name or "").strip()
    if full_name:
        parts = [p for p in full_name.split(" ") if p]
        if parts:
            user.first_name = parts[0]
            user.last_name = " ".join(parts[1:])
            user.save(update_fields=["first_name", "last_name"])

    login(request, user)
    session_payload = _session_payload(request, user)
    return JsonResponse(_schema_dump(session_payload))


@router.post("/consents", response=UpdateConsentsResponseSchema)
@csrf_protect
def update_consents(request, payload: UpdateConsentsRequestSchema):
    """Atnaujina prisijungusio naudotojo sutikimus."""

    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti")

    consents, _ = UserConsents.objects.get_or_create(user=request.user)

    updated = False
    for field_name in (
        "newsletter_consent",
        "privacy_policy_consent",
        "terms_of_service_consent",
    ):
        value = getattr(payload, field_name)
        if value is None:
            continue
        consents.set_consent(field_name, bool(value))
        updated = True

    if updated:
        consents.save()

    return UpdateConsentsResponseSchema(
        consents=UserConsentsSchema(
            newsletter_consent=bool(consents.newsletter_consent),
            privacy_policy_consent=bool(consents.privacy_policy_consent),
            terms_of_service_consent=bool(consents.terms_of_service_consent),
            newsletter_consent_at=consents.newsletter_consent_at,
            privacy_policy_consent_at=consents.privacy_policy_consent_at,
            terms_of_service_consent_at=consents.terms_of_service_consent_at,
        )
    )
