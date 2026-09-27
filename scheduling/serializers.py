from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from catalog.models import Provider, Service

from .models import TimeOff, WorkingHours

OVERLAP_MSG = "Bu oraliq mavjud dam olish vaqti bilan ustma-ust tushadi."


class WorkingHoursSerializer(serializers.ModelSerializer):
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = WorkingHours
        fields = ["id", "weekday", "weekday_display", "start_time", "end_time"]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        if start >= end:
            raise serializers.ValidationError({"end_time": "Tugash vaqti boshlanishdan keyin bo'lishi kerak."})
        if start.minute % 5 or end.minute % 5 or start.second or end.second:
            raise serializers.ValidationError("Vaqtlar 5 daqiqaga karrali bo'lishi kerak (masalan 09:00, 09:05).")
        # Bir kunda oraliqlar ustma-ust tushmasligi kerak: [a, b) va [c, d) kesishadi, agar a < d va c < b
        qs = WorkingHours.objects.filter(
            provider=self.context["provider"], weekday=weekday, start_time__lt=end, end_time__gt=start
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bu kunda ish vaqti boshqa oraliq bilan ustma-ust tushadi.")
        return attrs

    def create(self, validated_data):
        return WorkingHours.objects.create(provider=self.context["provider"], **validated_data)


class TimeOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeOff
        fields = ["id", "start_at", "end_at", "reason", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start >= end:
            raise serializers.ValidationError({"end_at": "Tugash vaqti boshlanishdan keyin bo'lishi kerak."})
        # Tezkor tekshiruv (qulfsiz). Parallel so'rovlar uchun _save() ichida qulf bilan qayta tekshiriladi.
        self._check_overlap(start, end)
        # TODO (6-bosqich): shu oraliqda faol booking bo'lsa, rad etish
        return attrs

    def _check_overlap(self, start, end):
        qs = TimeOff.objects.filter(provider=self.context["provider"], start_at__lt=end, end_at__gt=start)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(OVERLAP_MSG)

    def _save(self, fn):
        provider = self.context["provider"]
        try:
            with transaction.atomic():
                # Provider qatorini qulflaymiz: shu provider uchun parallel yozuvlar navbat bilan bajariladi.
                # Qulfsiz ikki INSERT exclusion constraint'da bir-birini kutib, "deadlock" berishi mumkin
                # (testda aniqlangan). Qulfdan keyin ustma-ust tushishni qayta tekshiramiz.
                Provider.objects.select_for_update().only("id").get(pk=provider.pk)
                data = self.validated_data
                self._check_overlap(data.get("start_at", getattr(self.instance, "start_at", None)),
                                    data.get("end_at", getattr(self.instance, "end_at", None)))
                return fn()
        except IntegrityError:
            # Oxirgi himoya chizig'i: baza constraint'i
            raise serializers.ValidationError(OVERLAP_MSG)

    def create(self, validated_data):
        return self._save(lambda: TimeOff.objects.create(provider=self.context["provider"], **validated_data))

    def update(self, instance, validated_data):
        return self._save(lambda: super(TimeOffSerializer, self).update(instance, validated_data))


class AvailabilityQuerySerializer(serializers.Serializer):
    """GET /api/availability/ parametrlari."""
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.filter(is_active=True), required=False)
    date = serializers.DateField()

    def validate(self, attrs):
        provider, service = attrs.get("provider"), attrs["service"]
        if provider and not provider.services.filter(pk=service.pk).exists():
            raise serializers.ValidationError({"provider": "Bu xodim tanlangan xizmatni ko'rsatmaydi."})
        today = timezone.localdate()
        # Provider timezone'i server timezone'idan farq qilishi mumkin, shuning uchun 1 kun zaxira qoldiramiz
        if attrs["date"] < today - timedelta(days=1):
            raise serializers.ValidationError({"date": "O'tgan sana uchun bo'sh vaqt yo'q."})
        if attrs["date"] > today + timedelta(days=settings.BOOKING_MAX_ADVANCE_DAYS):
            raise serializers.ValidationError(
                {"date": f"Eng ko'pi {settings.BOOKING_MAX_ADVANCE_DAYS} kun oldinga band qilish mumkin."})
        return attrs


# ---- Javob sxemasi (Swagger hujjati uchun) ----
class SlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class ProviderSlotsSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()
    provider_name = serializers.CharField()
    timezone = serializers.CharField()
    slots = SlotSerializer(many=True)


class AvailabilityResponseSerializer(serializers.Serializer):
    service_id = serializers.IntegerField()
    date = serializers.DateField()
    duration_minutes = serializers.IntegerField()
    providers = ProviderSlotsSerializer(many=True)
