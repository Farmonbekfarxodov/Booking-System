"""Booking biznes mantiqi. View'lar yupqa qoladi, barcha qoidalar shu yerda."""
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from zoneinfo import ZoneInfo

from catalog.models import Provider, Service
from scheduling.availability import Interval, get_available_slots

from .models import Booking


class BookingError(Exception):
    """Booking qilib bo'lmaydi (400)."""
    status_code = 400

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message, self.field = message, field


class SlotTakenError(BookingError):
    """Slot allaqachon band (409 Conflict)."""
    status_code = 409


def create_booking(*, customer, provider: Provider, service: Service, start_at, notes: str = "") -> Booking:
    # --- 1. Arzon tekshiruvlar (qulfsiz) ---
    if not customer.is_customer:
        raise BookingError("Faqat mijozlar booking qila oladi.")
    if not service.is_active:
        raise BookingError("Xizmat faol emas.", "service")
    if not provider.is_active:
        raise BookingError("Xodim faol emas.", "provider")
    if not provider.services.filter(pk=service.pk).exists():
        raise BookingError("Bu xodim tanlangan xizmatni ko'rsatmaydi.", "provider")

    now = timezone.now()
    if start_at < now + timedelta(minutes=settings.BOOKING_MIN_NOTICE_MINUTES):
        raise BookingError(f"Kamida {settings.BOOKING_MIN_NOTICE_MINUTES} daqiqa oldin band qilish kerak.", "start_at")
    if start_at > now + timedelta(days=settings.BOOKING_MAX_ADVANCE_DAYS):
        raise BookingError(f"Eng ko'pi {settings.BOOKING_MAX_ADVANCE_DAYS} kun oldinga band qilish mumkin.", "start_at")

    end_at = start_at + timedelta(minutes=service.duration_minutes)
    local_day = start_at.astimezone(ZoneInfo(provider.timezone)).date()

    try:
        with transaction.atomic():
            # --- 2. Qulf: shu provider uchun booking yaratish navbat bilan bajariladi ---
            # Ikki mijoz bir vaqtda bir slotni olmoqchi bo'lsa, ikkinchisi birinchisi tugashini kutadi,
            # keyin yangilangan holatni ko'radi va 409 oladi.
            Provider.objects.select_for_update().only("id").get(pk=provider.pk)

            # --- 3. Qulf ichida: slot haqiqatan bo'shmi? ---
            # Bo'sh slotlar ro'yxati ish vaqti, dam olish, mavjud bookinglar va slot qadamini hisobga oladi.
            free = {s.start for s in get_available_slots(provider, service, local_day, now=now)}
            if start_at not in free:
                slot = Interval(start_at, end_at)
                taken = Booking.objects.filter(
                    provider=provider, status__in=Booking.ACTIVE_STATUSES,
                    start_at__lt=slot.end, end_at__gt=slot.start,
                ).exists()
                if taken:
                    raise SlotTakenError("Bu vaqt allaqachon band qilingan. Boshqa vaqtni tanlang.", "start_at")
                raise BookingError("Bu vaqt bo'sh slotlar ro'yxatida yo'q (ish vaqtidan tashqarida, "
                                   "dam olish kuni yoki slot qadamiga mos emas).", "start_at")

            if Booking.objects.filter(customer=customer, status__in=Booking.ACTIVE_STATUSES,
                                      start_at__lt=end_at, end_at__gt=start_at).exists():
                raise BookingError("Sizda shu vaqtda boshqa booking bor.", "start_at")

            return Booking.objects.create(
                customer=customer, provider=provider, service=service,
                start_at=start_at, end_at=end_at, price=service.price, notes=notes,
            )
    except IntegrityError as e:
        # --- 4. Oxirgi himoya chizig'i: baza constraint'i ---
        if "booking_no_customer_overlap" in str(e):
            raise BookingError("Sizda shu vaqtda boshqa booking bor.", "start_at")
        raise SlotTakenError("Bu vaqt allaqachon band qilingan. Boshqa vaqtni tanlang.", "start_at")
