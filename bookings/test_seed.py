import pytest
from django.core.management import call_command

from accounts.models import User
from bookings.models import Booking
from catalog.models import Provider, Service
from scheduling.models import WorkingHours


@pytest.mark.django_db
def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    counts = (User.objects.count(), Service.objects.count(), Provider.objects.count(),
              WorkingHours.objects.count(), Booking.objects.count())
    call_command("seed_demo")                                   # ikkinchi marta - hech narsa takrorlanmaydi
    assert counts == (User.objects.count(), Service.objects.count(), Provider.objects.count(),
                      WorkingHours.objects.count(), Booking.objects.count())
    assert counts[:4] == (5, 4, 2, 24)
    assert Booking.objects.count() == 3
    assert Booking.objects.filter(status="confirmed").count() == 1
    assert User.objects.get(username="admin").check_password("Demo-pass-123")
