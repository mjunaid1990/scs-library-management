"""Server-side role checks used by every API view."""

from rest_framework.permissions import BasePermission


class IsLibrarianOrAdmin(BasePermission):
    message = "Librarian or administrator role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_library_staff)
