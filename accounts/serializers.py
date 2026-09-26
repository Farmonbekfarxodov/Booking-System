from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone", "role", "date_joined"]
        read_only_fields = ["id", "username", "role", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "first_name", "last_name", "phone"]

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email bilan foydalanuvchi allaqachon mavjud.")
        return value

    def validate(self, attrs):
        # Django'ning parol qoidalari (uzunlik, oddiy parol, username'ga o'xshash emas)
        validate_password(attrs["password"], user=User(username=attrs.get("username"), email=attrs.get("email")))
        return attrs

    def create(self, validated_data):
        # role atayin qabul qilinmaydi: ro'yxatdan o'tgan har kim customer bo'ladi.
        # Staff/Admin faqat admin tomonidan tayinlanadi (privilege escalation'ning oldini olish).
        return User.objects.create_user(**validated_data, role=User.Role.CUSTOMER)
