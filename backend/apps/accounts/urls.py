from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    LoginView,
    LogoutView,
    MemberViewSet,
    MeView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    csrf_cookie,
)

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")

urlpatterns = [
    path("auth/csrf/", csrf_cookie, name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/password/reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
] + router.urls
