from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from .models import Booking
from .serializers import BookingCreateSerializer, BookingDetailSerializer, BookingSerializer, CancelSerializer
from .services import BookingError, cancel_booking, complete_booking, confirm_booking, create_booking


class BookingAPIError(APIException):
    def __init__(self, err: BookingError):
        self.status_code = err.status_code
        super().__init__({err.field or "detail": [err.message]} if err.field else {"detail": err.message})


class BookingViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """Bookinglar.

    - customer: faqat o'z bookinglarini ko'radi va yangisini yaratadi
    - staff: o'ziga (provider sifatida) yozilgan bookinglarni ko'radi
    - admin: hammasini ko'radi
    """
    serializer_class = BookingSerializer
    queryset = Booking.objects.none()   # Swagger sxemasi uchun; haqiqiy queryset get_queryset'da

    def get_serializer_class(self):
        return BookingDetailSerializer if self.action == "retrieve" else BookingSerializer

    def get_queryset(self):
        u = self.request.user
        qs = Booking.objects.select_related("service", "provider", "customer")
        if self.action == "retrieve":
            qs = qs.prefetch_related("events__actor")
        if u.is_business_admin:
            pass
        elif u.is_staff_member:
            qs = qs.filter(provider__user=u)
        else:
            qs = qs.filter(customer=u)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status__in=status_param.split(","))
        return qs

    @extend_schema(parameters=[OpenApiParameter("status", str, description="Masalan: pending,confirmed")])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=BookingCreateSerializer, responses={201: BookingSerializer})
    def create(self, request, *args, **kwargs):
        s = BookingCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            booking = create_booking(customer=request.user, **s.validated_data)
        except BookingError as e:
            raise BookingAPIError(e)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    # ---------- Status o'tishlari ----------
    def _run(self, fn, *args):
        # get_object() - ko'rish huquqini tekshiradi: begona booking uchun 404
        booking = self.get_object()
        try:
            booking = fn(booking.pk, self.request.user, *args)
        except BookingError as e:
            raise BookingAPIError(e)
        booking = self.get_queryset().prefetch_related("events__actor").get(pk=booking.pk)
        return Response(BookingDetailSerializer(booking).data)

    @extend_schema(request=None, responses=BookingDetailSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Pending -> Confirmed (xodim yoki admin)."""
        return self._run(confirm_booking)

    @extend_schema(request=CancelSerializer, responses=BookingDetailSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Pending/Confirmed -> Cancelled. Mijoz faqat boshlanishiga N soatdan ko'p qolganda."""
        s = CancelSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._run(cancel_booking, s.validated_data.get("reason", ""))

    @extend_schema(request=None, responses=BookingDetailSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Confirmed -> Completed (xodim yoki admin, boshlanganidan keyin)."""
        return self._run(complete_booking)
