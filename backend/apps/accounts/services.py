"""Member lifecycle helpers: code generation, invites, account creation."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import PatronProfile, User

ROLE_CODE_PREFIX = {
    User.Role.STUDENT: "STU",
    User.Role.TEACHER: "TCH",
}


def generate_member_code(user: User) -> str:
    """Member codes are readable and stable: STU-00042, TCH-00007."""
    prefix = ROLE_CODE_PREFIX.get(user.role, "MEM")
    return f"{prefix}-{user.pk:05d}"


def build_password_reset_link(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uid}&token={token}"


def send_invite_email(user: User) -> None:
    send_mail(
        subject="Your school library account",
        message=(
            f"Hello {user.full_name},\n\n"
            "A library account has been created for you. Choose your password here:\n"
            f"{build_password_reset_link(user)}\n\n"
            "The link is valid for 24 hours. If it has expired, ask the librarian to send a new one.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@transaction.atomic
def create_member(
    *,
    email: str,
    full_name: str,
    role: str,
    member_code: str = "",
    class_section: str = "",
    department: str = "",
) -> User:
    """Create a student or teacher with an unusable password and send an invite.

    The invite is sent after the transaction commits so a mail failure cannot
    roll back a correctly created member.
    """
    user = User.objects.create_user(
        email=email,
        password=None,
        full_name=full_name,
        role=role,
        must_change_password=True,
    )
    PatronProfile.objects.create(
        user=user,
        member_code=member_code or generate_member_code(user),
        class_section=class_section,
        department=department,
    )
    transaction.on_commit(lambda: send_invite_email(user))
    return user
