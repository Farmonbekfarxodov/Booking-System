"""Bo'sh vaqtlarni (slot) hisoblash.

Ikki qatlam:
1. compute_slots() - sof funksiya: faqat vaqt oraliqlari bilan ishlaydi, bazaga murojaat qilmaydi.
   Shuning uchun uni alohida, tez va aniq test qilish oson.
2. get_available_slots() - bazadan ish jadvali, dam olish va bandliklarni olib, compute_slots() ni chaqiradi.

Barcha oraliqlar yarim ochiq: [start, end). 13:00 da tugagan va 13:00 da boshlangan oraliqlar kesishmaydi.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from catalog.models import Provider, Service

from .models import TimeOff, WorkingHours


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


def compute_slots(windows, busy, duration: timedelta, step: timedelta, earliest: datetime) -> list[Interval]:
    """Ish oynalari ichidan band bo'lmagan, `duration` uzunlikdagi slotlarni qaytaradi.

    windows  - ish vaqti oraliqlari (UTC)
    busy     - band oraliqlar: dam olish, mavjud bookinglar (UTC)
    earliest - bundan oldin boshlanadigan slot berilmaydi (hozirgi vaqt + minimal ogohlantirish)
    """
    busy = sorted(busy, key=lambda b: b.start)
    slots = []
    for w in sorted(windows, key=lambda w: w.start):
        t = w.start
        while t + duration <= w.end:
            slot = Interval(t, t + duration)
            if t >= earliest and not any(slot.overlaps(b) for b in busy):
                slots.append(slot)
            t += step
    return slots


def local_day_bounds(day: date, tz: ZoneInfo) -> Interval:
    """Provider timezone'idagi kunning boshi va oxiri (UTC da)."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return Interval(start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc))


def working_windows(provider: Provider, day: date) -> list[Interval]:
    """Haftalik jadvaldan shu sana uchun ish oynalarini hosil qiladi.

    Ish vaqti mahalliy soatda saqlangani uchun zoneinfo orqali UTC ga o'giramiz -
    shu tufayli yozgi/qishki vaqtga o'tish (DST) to'g'ri hisobga olinadi.
    """
    tz = ZoneInfo(provider.timezone)
    return [
        Interval(
            datetime.combine(day, wh.start_time, tzinfo=tz).astimezone(dt_timezone.utc),
            datetime.combine(day, wh.end_time, tzinfo=tz).astimezone(dt_timezone.utc),
        )
        for wh in WorkingHours.objects.filter(provider=provider, weekday=day.weekday())
    ]


def busy_intervals(provider: Provider, span: Interval) -> list[Interval]:
    """Shu oraliqda provider band bo'lgan vaqtlar.

    Hozircha faqat dam olish. 6-bosqichda faol bookinglar ham shu yerga qo'shiladi.
    """
    offs = TimeOff.objects.filter(provider=provider, start_at__lt=span.end, end_at__gt=span.start)
    return [Interval(o.start_at, o.end_at) for o in offs]


def get_available_slots(provider: Provider, service: Service, day: date, now: datetime | None = None) -> list[Interval]:
    now = now or timezone.now()
    tz = ZoneInfo(provider.timezone)
    span = local_day_bounds(day, tz)
    earliest = now + timedelta(minutes=settings.BOOKING_MIN_NOTICE_MINUTES)
    return compute_slots(
        windows=working_windows(provider, day),
        busy=busy_intervals(provider, span),
        duration=timedelta(minutes=service.duration_minutes),
        step=timedelta(minutes=settings.BOOKING_SLOT_STEP_MINUTES),
        earliest=earliest,
    )
