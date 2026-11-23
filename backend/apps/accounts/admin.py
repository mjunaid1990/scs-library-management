from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import PatronProfile, User


class PatronProfileInline(admin.StackedInline):
    model = PatronProfile
    extra = 0
    can_delete = False
    verbose_name_plural = "Library membership"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [PatronProfileInline]
    ordering = ("full_name", "email")
    list_display = ("email", "full_name", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name", "patron_profile__member_code")
    readonly_fields = ("date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Profile"), {"fields": ("full_name", "role")}),
        (_("Access"), {"fields": ("is_active", "is_staff", "is_superuser", "must_change_password")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(PatronProfile)
class PatronProfileAdmin(admin.ModelAdmin):
    list_display = ("member_code", "user", "class_section", "department", "status", "joined_on")
    list_filter = ("status", "joined_on")
    search_fields = ("member_code", "user__email", "user__full_name")
    autocomplete_fields = ("user",)
