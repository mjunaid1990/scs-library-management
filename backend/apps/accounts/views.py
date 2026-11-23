"""Authentication and member management API."""

from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.core.mail import send_mail
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import PatronProfile, User
from .permissions import IsLibrarianOrAdmin
from .serializers import (
    LoginSerializer,
    MemberSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserSerializer,
)
from .services import build_password_reset_link


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_cookie(request):
    """Give the SPA a CSRF cookie before it posts credentials."""
    return Response({"detail": "CSRF cookie set."})


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        update_session_auth_hash(request, user)  # keep the current session valid
        return Response(UserSerializer(user).data)


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            send_mail(
                subject="Reset your school library password",
                message=(
                    f"Hello {user.full_name},\n\n"
                    "Use the link below to choose a new password:\n"
                    f"{build_password_reset_link(user)}\n\n"
                    "If you did not ask for this, you can ignore this email.\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        # Same answer either way: no account enumeration.
        return Response(
            {"detail": "If that address belongs to an active member, a reset link has been sent."}
        )


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"detail": "Password updated. You can now sign in.", "email": user.email})


class MemberViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Staff-facing member directory. Students and teachers are members."""

    permission_classes = [IsLibrarianOrAdmin]
    serializer_class = MemberSerializer
    filter_backends = [SearchFilter]
    search_fields = ["full_name", "email", "patron_profile__member_code", "patron_profile__class_section"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return (
            User.objects.filter(role__in=[User.Role.STUDENT, User.Role.TEACHER])
            .select_related("patron_profile")
            .order_by("full_name", "email")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(self.get_serializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Block sign-in and mark the profile inactive, keeping loan history intact."""
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])

        profile = user.patron_profile
        profile.status = PatronProfile.Status.INACTIVE
        profile.save(update_fields=["status"])
        return Response(self.get_serializer(user).data)
