from zoneinfo import ZoneInfo

from rest_framework import serializers

from catalog.models import Provider, Service

from .models import Booking, BookingEvent


class BookingCreateSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.all())
    start_at = serializers.DateTimeField(help_text="ISO 8601, timezone bilan. Masalan 2030-05-06T09:00:00+05:00")
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BookingSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    provider_name = serializers.CharField(source="provider.display_name", read_only=True)
    customer_username = serializers.CharField(source="customer.username", read_only=True)
    timezone = serializers.CharField(source="provider.timezone", read_only=True)
    start_local = serializers.SerializerMethodField()
    end_local = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ["id", "status", "service", "service_name", "provider", "provider_name", "customer",
                  "customer_username", "start_at", "end_at", "start_local", "end_local", "timezone",
                  "price", "notes", "cancelled_at", "cancel_reason", "created_at", "updated_at"]
        read_only_fields = fields

    def _local(self, obj, value):
        return value.astimezone(ZoneInfo(obj.provider.timezone)).isoformat()

    def get_start_local(self, obj) -> str:
        return self._local(obj, obj.start_at)

    def get_end_local(self, obj) -> str:
        return self._local(obj, obj.end_at)


class BookingEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", default=None, read_only=True)

    class Meta:
        model = BookingEvent
        fields = ["from_status", "to_status", "actor", "note", "created_at"]


class BookingDetailSerializer(BookingSerializer):
    events = BookingEventSerializer(many=True, read_only=True)

    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ["events"]
        read_only_fields = fields


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)
