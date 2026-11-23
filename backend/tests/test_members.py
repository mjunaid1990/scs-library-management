import pytest
from django.core import mail
from rest_framework import status

from apps.accounts.models import PatronProfile, User
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def create_payload(**overrides) -> dict:
    payload = {
        "email": "new.student@school.test",
        "full_name": "Hina Yousaf",
        "role": User.Role.STUDENT,
        "class_section": "9-A",
    }
    payload.update(overrides)
    return payload


def test_students_cannot_list_members(student_api):
    assert student_api.get("/api/members/").status_code == status.HTTP_403_FORBIDDEN


def test_students_cannot_create_members(student_api):
    response = student_api.post("/api/members/", create_payload(), format="json")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not User.objects.filter(email="new.student@school.test").exists()


def test_anonymous_cannot_list_members(api):
    assert api.get("/api/members/").status_code in {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }


def test_librarian_lists_members(staff_api, student):
    response = staff_api.get("/api/members/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["email"] == student.email


def test_member_search_matches_code(staff_api, student):
    response = staff_api.get("/api/members/", {"search": "STU-00001"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


def test_librarian_creates_a_member_with_an_invite(staff_api, django_capture_on_commit_callbacks):
    # Invites are queued with transaction.on_commit, so they only send after a real commit.
    with django_capture_on_commit_callbacks(execute=True):
        response = staff_api.post("/api/members/", create_payload(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["member_code"].startswith("STU-")
    assert response.data["status"] == PatronProfile.Status.GOOD_STANDING

    user = User.objects.get(email="new.student@school.test")
    assert user.must_change_password is True
    assert user.has_usable_password() is False
    assert user.patron_profile.class_section == "9-A"
    assert len(mail.outbox) == 1
    assert "reset-password" in mail.outbox[0].body


def test_member_code_can_be_supplied(staff_api):
    response = staff_api.post(
        "/api/members/", create_payload(member_code="LIB-2026-001"), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["member_code"] == "LIB-2026-001"


def test_duplicate_email_is_rejected(staff_api, student):
    response = staff_api.post(
        "/api/members/", create_payload(email=student.email.upper()), format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_duplicate_member_code_is_rejected(staff_api, student):
    response = staff_api.post("/api/members/", create_payload(member_code="STU-00001"), format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "member_code" in response.data


def test_staff_role_cannot_be_created_through_the_member_api(staff_api):
    response = staff_api.post("/api/members/", create_payload(role=User.Role.LIBRARIAN), format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "role" in response.data


def test_librarian_updates_member_details(staff_api, student):
    response = staff_api.patch(
        f"/api/members/{student.pk}/",
        {"class_section": "10-C", "status": PatronProfile.Status.SUSPENDED},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    student.patron_profile.refresh_from_db()
    assert student.patron_profile.class_section == "10-C"
    assert student.patron_profile.status == PatronProfile.Status.SUSPENDED


def test_role_change_is_rejected(staff_api, student):
    response = staff_api.patch(
        f"/api/members/{student.pk}/", {"role": User.Role.TEACHER}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "role" in response.data


def test_deactivate_blocks_sign_in_and_marks_the_profile(staff_api, student):
    response = staff_api.post(f"/api/members/{student.pk}/deactivate/")

    assert response.status_code == status.HTTP_200_OK
    student.refresh_from_db()
    assert student.is_active is False
    assert student.patron_profile.status == PatronProfile.Status.INACTIVE


def test_member_detail_is_not_visible_to_other_members(student_api, librarian):
    response = student_api.get(f"/api/members/{librarian.pk}/")

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_session_login_then_member_access(api, librarian, student):
    login = api.post(
        "/api/auth/login/", {"email": librarian.email, "password": PASSWORD}, format="json"
    )
    assert login.status_code == status.HTTP_200_OK

    response = api.get("/api/members/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
