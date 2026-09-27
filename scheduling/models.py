from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.db import models
from django.db.models import F, Func, Q

from catalog.models import Provider


class TsTzRange(Func):
    """PostgreSQL tstzrange(start, end, '[)') - yarim ochiq vaqt oralig'i."""
    function = "TSTZRANGE"
    output_field = models.DateTimeField()


class WorkingHours(models.Model):
    """Provider'ning haftalik ish jadvali.

    Vaqtlar provider'ning o'z timezone'ida (Provider.timezone) saqlanadi, chunki
    "har dushanba 09:00-18:00" degan qoida yozgi/qishki vaqtdan qat'i nazar
    mahalliy soat bo'yicha ishlaydi. Bir kunda bir nechta oraliq bo'lishi mumkin
    (masalan 09:00-13:00 va 14:00-18:00 - o'rtada tushlik).
    """

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["provider", "weekday", "start_time"]
        indexes = [models.Index(fields=["provider", "weekday"])]
        constraints = [
            models.CheckConstraint(condition=Q(start_time__lt=F("end_time")), name="wh_start_before_end"),
        ]

    def __str__(self):
        return f"{self.provider} {self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"


class TimeOff(models.Model):
    """Provider ishlamaydigan aniq vaqt oralig'i (ta'til, kasallik, bayram).

    Aniq sana-vaqt bo'lgani uchun UTC da (timezone-aware) saqlanadi.
    """

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="time_off")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["provider", "start_at"]
        constraints = [
            models.CheckConstraint(condition=Q(start_at__lt=F("end_at")), name="timeoff_start_before_end"),
            # Bir provider uchun dam olish oraliqlari ustma-ust tushmasligini bazaning o'zi kafolatlaydi.
            # Bu - keyinchalik Booking uchun ishlatiladigan usulning birinchi qo'llanishi.
            ExclusionConstraint(
                name="timeoff_no_overlap",
                expressions=[
                    (TsTzRange("start_at", "end_at"), RangeOperators.OVERLAPS),
                    ("provider", RangeOperators.EQUAL),
                ],
            ),
        ]

    def __str__(self):
        return f"{self.provider}: {self.start_at:%Y-%m-%d %H:%M} - {self.end_at:%Y-%m-%d %H:%M}"
