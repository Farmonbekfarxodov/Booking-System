from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from accounts.permissions import IsAdminOrReadOnly

from .models import Provider, Service
from .serializers import ProviderSerializer, ServiceSerializer


class ServiceViewSet(viewsets.ModelViewSet):
    """Xizmatlar. Ko'rish hamma uchun ochiq, o'zgartirish faqat admin uchun.

    DELETE xizmatni o'chirmaydi, balki nofaol qiladi (soft delete), chunki
    eski bookinglar unga bog'langan bo'ladi.
    """

    serializer_class = ServiceSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = Service.objects.all()
        user = self.request.user
        # Oddiy foydalanuvchilar faqat faol xizmatlarni ko'radi
        if not (user.is_authenticated and user.is_business_admin):
            qs = qs.filter(is_active=True)
        return qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class ProviderViewSet(viewsets.ModelViewSet):
    """Xodimlar (providerlar). ?service=<id> bilan shu xizmatni ko'rsatadiganlarini filtrlash mumkin."""

    serializer_class = ProviderSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        is_admin = user.is_authenticated and user.is_business_admin
        services_qs = Service.objects.all() if is_admin else Service.objects.filter(is_active=True)
        qs = Provider.objects.select_related("user").prefetch_related(Prefetch("services", queryset=services_qs))
        if not is_admin:
            qs = qs.filter(is_active=True)
        service_id = self.request.query_params.get("service")
        if service_id and service_id.isdigit():
            qs = qs.filter(services__id=service_id, services__is_active=True).distinct()
        return qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
