from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from rest_framework import viewsets

from catalog.models import Provider

from .models import TimeOff, WorkingHours
from .permissions import ProviderOwnerOrAdmin, ProviderScheduleWrite
from .serializers import TimeOffSerializer, WorkingHoursSerializer


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
