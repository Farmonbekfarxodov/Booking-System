from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.db import models
from django.db.models import F, Q

from catalog.models import Provider, Service
from scheduling.models import TsTzRange


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    # Vaqtni band qilib turadigan statuslar. Cancelled/Completed slotni bo'shatadi.
    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED)

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    start_at = models.DateTimeField()
    # end_at saqlanadi (hisoblanmaydi): xizmat davomiyligi keyin o'zgarsa ham eski booking buzilmaydi
    end_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    # Narx booking paytidagi holatda saqlanadi: xizmat narxi keyin o'zgarsa ham tarix to'g'ri qoladi
    price = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.CharField(max_length=500, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["provider", "start_at"]),
            models.Index(fields=["customer", "start_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(start_at__lt=F("end_at")), name="booking_start_before_end"),
            # ASOSIY HIMOYA: bitta provider uchun ikkita faol booking vaqti ustma-ust tusha olmaydi.
            # Kod qanchalik xato bo'lmasin, baza buni hech qachon saqlamaydi.
            ExclusionConstraint(
                name="booking_no_provider_overlap",
                expressions=[
                    (TsTzRange("start_at", "end_at"), RangeOperators.OVERLAPS),
                    ("provider", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=["pending", "confirmed"]),
            ),
            # Bitta mijoz bir vaqtning o'zida ikki joyda bo'la olmaydi
            ExclusionConstraint(
                name="booking_no_customer_overlap",
                expressions=[
                    (TsTzRange("start_at", "end_at"), RangeOperators.OVERLAPS),
                    ("customer", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=["pending", "confirmed"]),
            ),
        ]

    # Ruxsat etilgan status o'tishlari (state machine). Boshqa har qanday o'tish taqiqlangan.
    TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.COMPLETED, Status.CANCELLED},
        Status.CANCELLED: set(),      # yakuniy holat
        Status.COMPLETED: set(),      # yakuniy holat
    }

    def can_transition_to(self, new_status) -> bool:
        return new_status in self.TRANSITIONS[self.status]

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def __str__(self):
        return f"#{self.pk} {self.service} @ {self.start_at:%Y-%m-%d %H:%M} ({self.status})"


class BookingEvent(models.Model):
    """Booking tarixi (audit log): kim, qachon, qaysi statusdan qaysisiga o'tkazdi."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=10, choices=Booking.Status.choices, blank=True)
    to_status = models.CharField(max_length=10, choices=Booking.Status.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"#{self.booking_id}: {self.from_status or '-'} -> {self.to_status}"
