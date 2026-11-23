import pytest
from rest_framework.test import APIClient

from apps.accounts.models import PatronProfile, User

PASSWORD = "Str0ngPass!234"


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def librarian(db) -> User:
    return User.objects.create_user(
        email="librarian@school.test",
        password=PASSWORD,
        full_name="Ayesha Khan",
        role=User.Role.LIBRARIAN,
        must_change_password=False,
    )


@pytest.fixture
def student(db) -> User:
    user = User.objects.create_user(
        email="student@school.test",
        password=PASSWORD,
        full_name="Bilal Ahmed",
        role=User.Role.STUDENT,
        must_change_password=False,
    )
    PatronProfile.objects.create(user=user, member_code="STU-00001", class_section="8-B")
    return user


@pytest.fixture
def staff_api(api, librarian) -> APIClient:
    api.force_authenticate(librarian)
    return api


@pytest.fixture
def student_api(api, student) -> APIClient:
    api.force_authenticate(student)
    return api
