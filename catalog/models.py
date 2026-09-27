from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

class Service(models.Model):
    """Biznes ko'rsatadigan xizmat (masalan: soch olish, 30 daqiqa, 80 000 so'm)."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(5), MaxValueValidator(8 * 60)],
        help_text="Davomiylik daqiqada (5..480, 5 ga karrali).",
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    # Xizmat o'chirilmaydi, faqat nofaol qilinadi: eski bookinglar unga bog'langan bo'lib qoladi
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(duration_minutes__gte=5), name="service_duration_min_5"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="service_price_non_negative"),
        ]

    def clean(self):
        if self.duration_minutes and self.duration_minutes % 5:
            raise ValidationError({"duration_minutes": "Davomiylik 5 daqiqaga karrali bo'lishi kerak."})

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min)"


class Provider(models.Model):
    """Xizmat ko'rsatuvchi xodim. Har bir provider bitta User'ga (role=staff) bog'langan."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="provider")
    display_name = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    services = models.ManyToManyField(Service, related_name="providers", blank=True)
    # Provider ish vaqti shu timezone'da kiritiladi; bazada vaqtlar UTC da saqlanadi
    # choices ishlatilmaydi: timezone ro'yxati OS/Python versiyasiga qarab farq qiladi va
    # har xil muhitda "yangi migratsiya bor" degan xatoni chiqaradi. Tekshiruv serializer'da.
    timezone = models.CharField(max_length=64, default="Asia/Tashkent")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name
