import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

from apps.accounts.models import User
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_login_returns_user_and_opens_a_session(api, student):
    response = api.post(
        "/api/auth/login/",
        {"email": "Student@School.Test", "password": PASSWORD},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == "student@school.test"
    assert response.data["role"] == User.Role.STUDENT
    assert response.data["member_code"] == "STU-00001"
    assert api.get("/api/auth/me/").status_code == status.HTTP_200_OK


def test_login_rejects_a_wrong_password(api, student):
    response = api.post(
        "/api/auth/login/", {"email": student.email, "password": "wrong-pass"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid email or password" in str(response.data)


def test_inactive_user_cannot_sign_in(api, student):
    student.is_active = False
    student.save(update_fields=["is_active"])

    response = api.post(
        "/api/auth/login/", {"email": student.email, "password": PASSWORD}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_me_requires_authentication(api):
    assert api.get("/api/auth/me/").status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }


def test_logout_ends_the_session(api, student):
    api.post("/api/auth/login/", {"email": student.email, "password": PASSWORD}, format="json")

    assert api.post("/api/auth/logout/").status_code == status.HTTP_204_NO_CONTENT
    assert api.get("/api/auth/me/").status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }


def test_password_change_clears_the_first_login_flag(api, student):
    api.force_authenticate(student)

    response = api.post(
        "/api/auth/password/change/",
        {"current_password": PASSWORD, "new_password": "N3wSecure!pass"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    student.refresh_from_db()
    assert student.must_change_password is False
    assert student.check_password("N3wSecure!pass")
    # Session survives the password change.
    assert api.get("/api/auth/me/").status_code == status.HTTP_200_OK


def test_password_change_requires_the_current_password(api, student):
    api.force_authenticate(student)

    response = api.post(
        "/api/auth/password/change/",
        {"current_password": "not-my-password", "new_password": "N3wSecure!pass"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_password_change_rejects_a_weak_password(api, student):
    api.force_authenticate(student)

    response = api.post(
        "/api/auth/password/change/",
        {"current_password": PASSWORD, "new_password": "12345678"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "new_password" in response.data


def test_reset_request_does_not_reveal_unknown_addresses(api):
    response = api.post("/api/auth/password/reset/", {"email": "nobody@school.test"}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 0


def test_reset_request_emails_an_active_member(api, student):
    response = api.post(
        "/api/auth/password/reset/", {"email": "STUDENT@school.test"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1
    assert student.email in mail.outbox[0].to
    assert "reset-password" in mail.outbox[0].body


def test_reset_confirm_sets_a_new_password(api, student):
    uid = urlsafe_base64_encode(force_bytes(student.pk))
    token = default_token_generator.make_token(student)

    response = api.post(
        "/api/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "new_password": "R3set!SecurePass"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    student.refresh_from_db()
    assert student.check_password("R3set!SecurePass")
    assert student.must_change_password is False


def test_reset_confirm_rejects_a_bad_token(api, student):
    uid = urlsafe_base64_encode(force_bytes(student.pk))

    response = api.post(
        "/api/auth/password/reset/confirm/",
        {"uid": uid, "token": "not-a-token", "new_password": "R3set!SecurePass"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    student.refresh_from_db()
    assert student.check_password(PASSWORD)


def test_csrf_endpoint_sets_a_cookie(api):
    response = api.get("/api/auth/csrf/")

    assert response.status_code == status.HTTP_200_OK
    assert "csrftoken" in response.cookies


def test_health_endpoint_is_public(api):
    response = api.get("/api/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "ok"}
