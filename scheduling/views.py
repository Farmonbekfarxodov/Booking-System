from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from zoneinfo import ZoneInfo

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Provider

from .models import TimeOff, WorkingHours
from .permissions import ProviderOwnerOrAdmin, ProviderScheduleWrite
from .availability import get_available_slots
from .serializers import (AvailabilityQuerySerializer, AvailabilityResponseSerializer, TimeOffSerializer,
                          WorkingHoursSerializer)


class ProviderNestedMixin:
    """URL'dagi /providers/<provider_pk>/... dan provider'ni oladi."""

    @cached_property
    def provider(self):
        return get_object_or_404(Provider, pk=self.kwargs["provider_pk"])

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "provider": self.provider}


class WorkingHoursViewSet(ProviderNestedMixin, viewsets.ModelViewSet):
    """Provider'ning haftalik ish jadvali."""
    queryset = WorkingHours.objects.none()   # Swagger sxemasi uchun (haqiqiy queryset get_queryset'da)
    serializer_class = WorkingHoursSerializer
    permission_classes = [ProviderScheduleWrite]
    pagination_class = None

    def get_queryset(self):
        return WorkingHours.objects.filter(provider=self.provider)


class TimeOffViewSet(ProviderNestedMixin, viewsets.ModelViewSet):
    """Provider'ning dam olish / ta'til oraliqlari."""
    queryset = TimeOff.objects.none()
    serializer_class = TimeOffSerializer
    permission_classes = [ProviderOwnerOrAdmin]

    def get_queryset(self):
        return TimeOff.objects.filter(provider=self.provider)


class AvailabilityView(APIView):
    """Tanlangan xizmat va sana uchun bo'sh vaqtlar.

    provider berilmasa, xizmatni ko'rsatadigan barcha faol xodimlar bo'yicha qaytariladi.
    Vaqtlar ISO 8601 formatida, provider'ning mahalliy timezone'ida (offset bilan) beriladi.
    """
    permission_classes = [AllowAny]

    @extend_schema(responses=AvailabilityResponseSerializer, parameters=[
        OpenApiParameter("service", int, required=True),
        OpenApiParameter("provider", int, required=False),
        OpenApiParameter("date", str, required=True, description="YYYY-MM-DD, provider timezone'ida"),
    ])
    def get(self, request):
        q = AvailabilityQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        service, day = q.validated_data["service"], q.validated_data["date"]
        providers = [q.validated_data["provider"]] if q.validated_data.get("provider") else \
            Provider.objects.filter(is_active=True, services=service).order_by("display_name")

        result = []
        for p in providers:
            tz = ZoneInfo(p.timezone)
            slots = get_available_slots(p, service, day)
            result.append({
                "provider_id": p.id,
                "provider_name": p.display_name,
                "timezone": p.timezone,
                "slots": [{"start": s.start.astimezone(tz).isoformat(), "end": s.end.astimezone(tz).isoformat()}
                          for s in slots],
            })
        return Response({"service_id": service.id, "date": day.isoformat(),
                         "duration_minutes": service.duration_minutes, "providers": result})
