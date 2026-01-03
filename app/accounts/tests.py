import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@pytest.mark.django_db
def test_password_reset_confirm_changes_password():
    User = get_user_model()
    user = User.objects.create_user(username="u1", email="u1@example.com", password="OldPassword123!")

    client = Client(enforce_csrf_checks=True)

    # Prime CSRF cookie
    session_resp = client.get("/api/auth/session")
    assert session_resp.status_code == 200
    csrf_cookie = client.cookies.get("csrftoken")
    assert csrf_cookie is not None

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    resp = client.post(
        "/api/auth/password-reset-confirm",
        data=json.dumps({"uid": uid, "token": token, "new_password": "NewPassword123!"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_cookie.value,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["changed"] is True

    user.refresh_from_db()
    assert user.check_password("NewPassword123!")


@pytest.mark.django_db
def test_password_reset_confirm_rejects_invalid_token():
    User = get_user_model()
    user = User.objects.create_user(username="u2", email="u2@example.com", password="OldPassword123!")

    client = Client(enforce_csrf_checks=True)
    client.get("/api/auth/session")
    csrf_cookie = client.cookies.get("csrftoken")
    assert csrf_cookie is not None

    uid = urlsafe_base64_encode(force_bytes(user.pk))

    resp = client.post(
        "/api/auth/password-reset-confirm",
        data=json.dumps({"uid": uid, "token": "bad-token", "new_password": "NewPassword123!"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_cookie.value,
    )
    assert resp.status_code == 400
