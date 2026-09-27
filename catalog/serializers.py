from zoneinfo import available_timezones

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Provider, Service

User = get_user_model()


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "description", "duration_minutes", "price", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_duration_minutes(self, value):
        if value % 5:
            raise serializers.ValidationError("Davomiylik 5 daqiqaga karrali bo'lishi kerak.")
        return value

    def validate_name(self, value):
        value = value.strip()
        qs = Service.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bu nomli xizmat allaqachon mavjud.")
        return value


class ServiceShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes", "price"]


class ProviderSerializer(serializers.ModelSerializer):
    """O'qish uchun: xizmatlar to'liq ko'rinadi. Yozish uchun: service_ids va user_id qabul qilinadi."""

    services = ServiceShortSerializer(many=True, read_only=True)
    service_ids = serializers.PrimaryKeyRelatedField(
        many=True, write_only=True, source="services", queryset=Service.objects.filter(is_active=True), required=False
    )
    user_id = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all(), write_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Provider
        fields = ["id", "user_id", "username", "display_name", "bio", "timezone", "is_active",
                  "services", "service_ids", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_timezone(self, value):
        if value not in available_timezones():
            raise serializers.ValidationError("Noto'g'ri timezone. Masalan: Asia/Tashkent")
        return value

    def validate_user_id(self, user):
        if self.instance and self.instance.user_id != user.id:
            raise serializers.ValidationError("Provider'ning foydalanuvchisini o'zgartirib bo'lmaydi.")
        if not self.instance and Provider.objects.filter(user=user).exists():
            raise serializers.ValidationError("Bu foydalanuvchi allaqachon provider.")
        if user.is_business_admin:
            raise serializers.ValidationError("Admin foydalanuvchini provider qilib bo'lmaydi.")
        return user

    @transaction.atomic
    def create(self, validated_data):
        user = validated_data["user"]
        # Customer provider qilinsa, uning roli avtomatik staff ga o'zgaradi
        if user.role != User.Role.STAFF:
            user.role = User.Role.STAFF
            user.save(update_fields=["role"])
        return super().create(validated_data)
