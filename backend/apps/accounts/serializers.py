"""Serializers for authentication and member management."""

from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import PatronProfile, User
from .services import create_member


class UserSerializer(serializers.ModelSerializer):
    member_code = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "must_change_password",
            "member_code",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields

    def get_member_code(self, obj: User):
        profile = getattr(obj, "patron_profile", None)
        return profile.member_code if profile else None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            self.context.get("request"),
            username=attrs["email"].strip().lower(),
            password=attrs["password"],
        )
        if user is None:
            # Deliberately generic: never reveal whether an address exists.
            raise serializers.ValidationError({"detail": "Invalid email or password."})
        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is not correct.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        try:
            password_validation.validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": "Choose a password different from the current one."}
            )
        return attrs

    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "This reset link is not valid."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "This reset link has expired or was already used."})

        try:
            password_validation.validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc

        attrs["user"] = user
        return attrs

    def save(self, **kwargs) -> User:
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user


class MemberSerializer(serializers.Serializer):
    """Reads a member as a flat record; writes go through ``services.create_member``.

    Representation:
        {id, email, full_name, role, member_code, class_section, department,
         joined_on, status, is_active, date_joined}
    """

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=[User.Role.STUDENT, User.Role.TEACHER])
    member_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    class_section = serializers.CharField(max_length=60, required=False, allow_blank=True)
    department = serializers.CharField(max_length=80, required=False, allow_blank=True)
    joined_on = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=PatronProfile.Status.choices, required=False)
    is_active = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance: User) -> dict:
        profile = instance.patron_profile
        return {
            "id": instance.pk,
            "email": instance.email,
            "full_name": instance.full_name,
            "role": instance.role,
            "member_code": profile.member_code,
            "class_section": profile.class_section,
            "department": profile.department,
            "joined_on": profile.joined_on,
            "status": profile.status,
            "is_active": instance.is_active,
            "date_joined": instance.date_joined,
        }

    def validate_email(self, value: str) -> str:
        existing = User.objects.filter(email__iexact=value.strip())
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A member with this email already exists.")
        return value.strip().lower()

    def validate_role(self, value: str) -> str:
        if self.instance is not None and value != self.instance.role:
            raise serializers.ValidationError("A member's role cannot be changed after creation.")
        return value

    def validate_member_code(self, value: str) -> str:
        value = (value or "").strip()
        if value and PatronProfile.objects.filter(member_code__iexact=value).exists():
            raise serializers.ValidationError("This member code is already in use.")
        return value

    def create(self, validated_data) -> User:
        return create_member(
            email=validated_data["email"],
            full_name=validated_data["full_name"],
            role=validated_data["role"],
            member_code=validated_data.get("member_code", ""),
            class_section=validated_data.get("class_section", ""),
            department=validated_data.get("department", ""),
        )

    def update(self, instance: User, validated_data) -> User:
        for attr in ("email", "full_name"):
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()

        profile = instance.patron_profile
        for attr in ("class_section", "department", "joined_on", "status"):
            if attr in validated_data:
                setattr(profile, attr, validated_data[attr])
        profile.save()
        return instance
