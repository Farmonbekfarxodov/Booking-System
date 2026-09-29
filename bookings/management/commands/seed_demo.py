"""Demo ma'lumotlar: xizmatlar, xodimlar, ish jadvali, foydalanuvchilar va bir nechta booking.

    python manage.py seed_demo

Buyruq idempotent: qayta ishga tushirilsa, mavjud yozuvlarni takror yaratmaydi.
Parol DEMO_PASSWORD muhit o'zgaruvchisidan olinadi (standart: Demo-pass-123).
"""
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from bookings.services import BookingError, confirm_booking, create_booking
from catalog.models import Provider, Service
from scheduling.models import TimeOff, WorkingHours

TZ = "Asia/Tashkent"

SERVICES = [
    ("Soch olish", "Klassik yoki zamonaviy soch turmagi", 30, 60000),
    ("Soqol olish", "Ustara bilan soqol olish va shakl berish", 20, 40000),
    ("Soch + soqol", "Kompleks xizmat", 60, 90000),
    ("Bolalar sochi", "12 yoshgacha bolalar uchun", 30, 40000),
]

PROVIDERS = [
    # username, ko'rinadigan ism, xizmatlar
    ("usta_ali", "Usta Ali", ["Soch olish", "Soqol olish", "Soch + soqol"]),
    ("usta_vali", "Usta Vali", ["Soch olish", "Bolalar sochi", "Soch + soqol"]),
]

# Dushanba-shanba: 09:00-13:00 va 14:00-19:00 (13-14 tushlik). Yakshanba dam olish.
SCHEDULE = [(wd, time(9), time(13)) for wd in range(6)] + [(wd, time(14), time(19)) for wd in range(6)]


class Command(BaseCommand):
    help = "Demo ma'lumotlarni yaratadi (idempotent)."

    def handle(self, *args, **opts):
        password = os.getenv("DEMO_PASSWORD", "Demo-pass-123")
        with transaction.atomic():
            admin = self._user("admin", User.Role.ADMIN, password, is_staff=True, is_superuser=True)
            customers = [self._user(u, User.Role.CUSTOMER, password) for u in ("mijoz", "mijoz2")]
            services = {
                name: Service.objects.get_or_create(
                    name=name, defaults={"description": d, "duration_minutes": m, "price": p})[0]
                for name, d, m, p in SERVICES
            }
            providers = []
            for username, display, svc_names in PROVIDERS:
                user = self._user(username, User.Role.STAFF, password)
                p, _ = Provider.objects.get_or_create(user=user, defaults={"display_name": display, "timezone": TZ})
                p.services.set([services[n] for n in svc_names])
                for wd, start, end in SCHEDULE:
                    WorkingHours.objects.get_or_create(provider=p, weekday=wd, start_time=start, end_time=end)
                providers.append(p)

        self._demo_time_off(providers[1])
        self._demo_bookings(customers, providers, services, admin)

        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar tayyor."))
        self.stdout.write(f"  Parol (hamma uchun): {password}")
        self.stdout.write("  admin     - biznes admini (Django admin ham)")
        self.stdout.write("  usta_ali, usta_vali - xodimlar (staff)")
        self.stdout.write("  mijoz, mijoz2       - mijozlar (customer)")

    def _user(self, username, role, password, **extra):
        user, created = User.objects.get_or_create(
            username=username, defaults={"email": f"{username}@demo.uz", "role": role, **extra})
        if created:
            user.set_password(password)
            user.save()
        return user

    def _next_workday(self, days_ahead):
        day = timezone.now().astimezone(ZoneInfo(TZ)).date() + timedelta(days=days_ahead)
        while day.weekday() == 6:        # yakshanba - dam olish
            day += timedelta(days=1)
        return day

    def _demo_time_off(self, provider):
        if TimeOff.objects.filter(provider=provider).exists():
            return
        day = self._next_workday(3)
        start = datetime.combine(day, time(14), tzinfo=ZoneInfo(TZ))
        TimeOff.objects.create(provider=provider, start_at=start, end_at=start + timedelta(hours=5),
                               reason="Shaxsiy ishlar")

    def _demo_bookings(self, customers, providers, services, admin):
        if Booking.objects.exists():
            return
        plan = [
            (customers[0], providers[0], "Soch olish", 1, time(10)),
            (customers[1], providers[0], "Soch + soqol", 1, time(11)),
            (customers[0], providers[1], "Bolalar sochi", 2, time(15)),
        ]
        for i, (cust, prov, svc, days, at) in enumerate(plan):
            start = datetime.combine(self._next_workday(days), at, tzinfo=ZoneInfo(TZ))
            try:
                b = create_booking(customer=cust, provider=prov, service=services[svc], start_at=start)
                if i == 0:
                    confirm_booking(b.pk, prov.user)
            except BookingError as e:
                self.stdout.write(self.style.WARNING(f"  Booking o'tkazib yuborildi: {e.message}"))
