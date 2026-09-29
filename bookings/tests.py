import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from bookings.models import Booking
from catalog.models import Provider, Service
from scheduling.models import TimeOff, WorkingHours

TASH = ZoneInfo("Asia/Tashkent")
URL = "/api/bookings/"


def next_monday_at(hour, minute=0):
    """Kelasi haftaning dushanbasi, Toshkent vaqti bilan."""
    today = timezone.now().astimezone(TASH).date()
    monday = today + timedelta(days=(7 - today.weekday()) or 7)
    return datetime.combine(monday, time(hour, minute), tzinfo=TASH)


@pytest.fixture
def svc(db):
    return Service.objects.create(name="Soch", duration_minutes=60, price=80000)


@pytest.fixture
def provider(make_user, svc):
    p = Provider.objects.create(user=make_user("usta", role=User.Role.STAFF), display_name="Usta")
    p.services.add(svc)
    for wd in range(7):
        WorkingHours.objects.create(provider=p, weekday=wd, start_time=time(9), end_time=time(18))
    return p


def payload(provider, svc, start):
    return {"provider": provider.id, "service": svc.id, "start_at": start.isoformat()}


# ---------- Muvaffaqiyatli booking ----------
def test_customer_books_slot(customer_api, provider, svc):
    start = next_monday_at(10)
    r = customer_api.post(URL, payload(provider, svc, start))
    assert r.status_code == 201, r.data
    b = Booking.objects.get()
    assert b.status == Booking.Status.PENDING
    assert b.end_at - b.start_at == timedelta(minutes=60)
    assert b.price == svc.price
    assert r.data["start_local"].startswith(start.date().isoformat() + "T10:00:00+05:00")


def test_price_snapshot_survives_price_change(customer_api, provider, svc):
    customer_api.post(URL, payload(provider, svc, next_monday_at(10)))
    svc.price = 999999
    svc.save()
    assert Booking.objects.get().price == 80000


# ---------- Double booking ----------
def test_double_booking_rejected_with_409(api, make_user, provider, svc):
    start = next_monday_at(10)
    for name, expected in [("a", 201), ("b", 409)]:
        api.force_authenticate(make_user(name))
        assert api.post(URL, payload(provider, svc, start)).status_code == expected


def test_partial_overlap_rejected(api, make_user, provider, svc):
    api.force_authenticate(make_user("a"))
    api.post(URL, payload(provider, svc, next_monday_at(10)))           # 10:00-11:00
    api.force_authenticate(make_user("b"))
    assert api.post(URL, payload(provider, svc, next_monday_at(10, 30))).status_code == 409   # 10:30-11:30


def test_adjacent_booking_allowed(api, make_user, provider, svc):
    api.force_authenticate(make_user("a"))
    api.post(URL, payload(provider, svc, next_monday_at(10)))
    api.force_authenticate(make_user("b"))
    assert api.post(URL, payload(provider, svc, next_monday_at(11))).status_code == 201


def test_cancelled_booking_frees_slot(api, make_user, provider, svc):
    api.force_authenticate(make_user("a"))
    api.post(URL, payload(provider, svc, next_monday_at(10)))
    Booking.objects.update(status=Booking.Status.CANCELLED)
    api.force_authenticate(make_user("b"))
    assert api.post(URL, payload(provider, svc, next_monday_at(10))).status_code == 201


def test_customer_cannot_be_in_two_places(customer_api, make_user, provider, svc):
    other = Provider.objects.create(user=make_user("usta2", role=User.Role.STAFF), display_name="Usta2")
    other.services.add(svc)
    WorkingHours.objects.create(provider=other, weekday=0, start_time=time(9), end_time=time(18))
    assert customer_api.post(URL, payload(provider, svc, next_monday_at(10))).status_code == 201
    r = customer_api.post(URL, payload(other, svc, next_monday_at(10, 30)))
    assert r.status_code == 400 and "start_at" in r.data


@pytest.mark.django_db
def test_db_constraint_blocks_overlap_even_without_service_layer(make_user, provider, svc):
    """Biznes mantiqini chetlab o'tsak ham baza ikki faol bookingni saqlamaydi."""
    start = next_monday_at(10)
    kw = dict(provider=provider, service=svc, start_at=start, end_at=start + timedelta(hours=1), price=1)
    Booking.objects.create(customer=make_user("a"), **kw)
    with pytest.raises(IntegrityError):
        Booking.objects.create(customer=make_user("b"), **kw)


@pytest.mark.django_db(transaction=True)
def test_race_condition_two_users_same_slot(make_user, provider, svc):
    """Ikki mijoz AYNAN bir vaqtda bir slotni band qilmoqchi: bittasi 201, ikkinchisi 409."""
    users = [make_user("r1"), make_user("r2")]
    data = payload(provider, svc, next_monday_at(10))
    barrier, codes = threading.Barrier(2), []

    def worker(u):
        c = APIClient()
        c.force_authenticate(u)
        barrier.wait()                      # ikkala oqim bir vaqtda "start"
        codes.append(c.post(URL, data).status_code)
        connection.close()

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [201, 409]
    assert Booking.objects.count() == 1


# ---------- Validatsiya ----------
@pytest.mark.parametrize("hour,minute", [(8, 0), (17, 30), (10, 7), (20, 0)])
def test_invalid_times_rejected(customer_api, provider, svc, hour, minute):
    """Ish vaqtidan oldin, oxiriga sig'maydi, slot qadamiga mos emas, ish vaqtidan keyin."""
    r = customer_api.post(URL, payload(provider, svc, next_monday_at(hour, minute)))
    assert r.status_code == 400, r.data


def test_past_time_rejected(customer_api, provider, svc):
    r = customer_api.post(URL, payload(provider, svc, timezone.now() - timedelta(days=1)))
    assert r.status_code == 400


def test_too_far_in_future_rejected(customer_api, provider, svc, settings):
    settings.BOOKING_MAX_ADVANCE_DAYS = 3
    r = customer_api.post(URL, payload(provider, svc, next_monday_at(10) + timedelta(days=30)))
    assert r.status_code == 400


def test_time_off_blocks_booking(customer_api, provider, svc):
    start = next_monday_at(10)
    TimeOff.objects.create(provider=provider, start_at=start, end_at=start + timedelta(hours=2))
    assert customer_api.post(URL, payload(provider, svc, start)).status_code == 400


def test_provider_must_offer_service(customer_api, provider):
    other = Service.objects.create(name="Massaj", duration_minutes=30, price=1)
    r = customer_api.post(URL, payload(provider, other, next_monday_at(10)))
    assert r.status_code == 400 and "provider" in r.data


def test_inactive_service_rejected(customer_api, provider, svc):
    svc.is_active = False
    svc.save()
    assert customer_api.post(URL, payload(provider, svc, next_monday_at(10))).status_code == 400


def test_staff_cannot_book(api, provider, svc):
    api.force_authenticate(provider.user)
    assert api.post(URL, payload(provider, svc, next_monday_at(10))).status_code == 400


@pytest.mark.django_db
def test_anonymous_cannot_book(api, provider, svc):
    assert api.post(URL, payload(provider, svc, next_monday_at(10))).status_code == 401


# ---------- Integratsiya ----------
def test_booked_slot_disappears_from_availability(customer_api, provider, svc, settings):
    settings.BOOKING_SLOT_STEP_MINUTES = 60
    start = next_monday_at(10)
    customer_api.post(URL, payload(provider, svc, start))
    r = customer_api.get(reverse("availability"), {"service": svc.id, "date": start.date().isoformat()})
    starts = [s["start"] for s in r.data["providers"][0]["slots"]]
    assert start.isoformat() not in starts and next_monday_at(11).isoformat() in starts


def test_time_off_over_active_booking_rejected(customer_api, api, provider, svc):
    start = next_monday_at(10)
    customer_api.post(URL, payload(provider, svc, start))
    api.force_authenticate(provider.user)
    r = api.post(reverse("time-off-list", args=[provider.id]),
                 {"start_at": start.isoformat(), "end_at": (start + timedelta(hours=3)).isoformat()})
    assert r.status_code == 400


# ---------- Ko'rish huquqlari ----------
def test_visibility_scoping(api, make_user, provider, svc, admin_user):
    a, b = make_user("a"), make_user("b")
    for u, h in [(a, 10), (b, 12)]:
        api.force_authenticate(u)
        api.post(URL, payload(provider, svc, next_monday_at(h)))
    api.force_authenticate(a)
    assert api.get(URL).data["count"] == 1                       # faqat o'ziniki
    other_id = Booking.objects.get(customer=b).id
    assert api.get(f"{URL}{other_id}/").status_code == 404        # boshqaning bookingi "yo'q"
    api.force_authenticate(provider.user)
    assert api.get(URL).data["count"] == 2                       # provider o'ziga yozilganlarni ko'radi
    api.force_authenticate(admin_user)
    assert api.get(URL).data["count"] == 2


def test_filter_by_status(customer_api, provider, svc):
    customer_api.post(URL, payload(provider, svc, next_monday_at(10)))
    assert customer_api.get(URL, {"status": "pending"}).data["count"] == 1
    assert customer_api.get(URL, {"status": "cancelled"}).data["count"] == 0
