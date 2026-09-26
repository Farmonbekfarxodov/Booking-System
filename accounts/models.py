from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Tizim foydalanuvchisi.

    Role'lar:
    - customer: xizmatni band qiladi (ro'yxatdan o'tganda doim shu beriladi)
    - staff: xizmat ko'rsatuvchi xodim (provider), o'z bookinglarini boshqaradi
    - admin: biznes egasi, xizmatlar/xodimlar/bookinglarni boshqaradi
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER, db_index=True)

    @property
    def is_customer(self) -> bool:
        return self.role == self.Role.CUSTOMER

    @property
    def is_staff_member(self) -> bool:
        return self.role == self.Role.STAFF

    @property
    def is_business_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        return f"{self.username} ({self.role})"
