import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from bookings.models import Booking, BookingEvent
from bookings.tests import next_monday_at, payload, provider, svc  # noqa: F401  (fixture'lar)

URL = "/api/bookings/"


@pytest.fixture
def booking(customer_api, provider, svc):  # noqa: F811
    r = customer_api.post(URL, payload(provider, svc, next_monday_at(10)))
    assert r.status_code == 201, r.data
    return Booking.objects.get(pk=r.data["id"])


def act(api, b, name, **data):
    return api.post(f"{URL}{b.id}/{name}/", data)


def make_past(b, hours_ago=2):
    """Bookingni o'tmishga siljitamiz (complete testlari uchun)."""
    start = timezone.now() - timedelta(hours=hours_ago)
    Booking.objects.filter(pk=b.pk).update(start_at=start, end_at=start + timedelta(hours=1))
    b.refresh_from_db()
    return b


# ---------- Confirm ----------
def test_provider_confirms(api, booking, provider):  # noqa: F811
    api.force_authenticate(provider.user)
    r = act(api, booking, "confirm")
    assert r.status_code == 200 and r.data["status"] == "confirmed"
    assert [e["to_status"] for e in r.data["events"]] == ["pending", "confirmed"]


def test_admin_confirms(admin_api, booking):
    assert act(admin_api, booking, "confirm").status_code == 200


def test_customer_cannot_confirm(customer_api, booking):
    assert act(customer_api, booking, "confirm").status_code == 403


def test_other_provider_cannot_see_or_confirm(api, booking, make_user):
    api.force_authenticate(make_user("boshqa_usta", role=User.Role.STAFF))
    assert act(api, booking, "confirm").status_code == 404     # begona booking umuman ko'rinmaydi


def test_confirm_twice_rejected(api, booking, provider):  # noqa: F811
    api.force_authenticate(provider.user)
    act(api, booking, "confirm")
    assert act(api, booking, "confirm").status_code == 400


# ---------- Cancel ----------
def test_customer_cancels_in_time(customer_api, booking, provider, svc):  # noqa: F811
    r = act(customer_api, booking, "cancel", reason="Rejalar o'zgardi")
    assert r.status_code == 200 and r.data["status"] == "cancelled"
    assert r.data["cancel_reason"] == "Rejalar o'zgardi" and r.data["cancelled_at"]
    # slot bo'shadi - boshqa booking qilish mumkin
    assert customer_api.post(URL, payload(provider, svc, next_monday_at(10))).status_code == 201


def test_customer_cannot_cancel_after_deadline(customer_api, booking, settings):
    settings.BOOKING_CANCEL_DEADLINE_HOURS = 24 * 30          # muddat allaqachon o'tgan
    r = act(customer_api, booking, "cancel")
    assert r.status_code == 400 and "soat" in r.data["detail"]


def test_provider_can_cancel_after_customer_deadline(api, booking, provider, settings):  # noqa: F811
    settings.BOOKING_CANCEL_DEADLINE_HOURS = 24 * 30
    api.force_authenticate(provider.user)
    assert act(api, booking, "cancel", reason="Usta kasal").status_code == 200


def test_other_customer_cannot_cancel(api, booking, make_user):
    api.force_authenticate(make_user("begona"))
    assert act(api, booking, "cancel").status_code == 404


def test_cannot_cancel_finished_booking(admin_api, booking):
    make_past(booking, hours_ago=3)
    assert act(admin_api, booking, "cancel").status_code == 400


def test_cancelled_is_final(admin_api, booking):
    act(admin_api, booking, "cancel")
    for a in ("confirm", "complete", "cancel"):
        assert act(admin_api, booking, a).status_code == 400


# ---------- Complete ----------
def test_complete_flow(api, booking, provider):  # noqa: F811
    api.force_authenticate(provider.user)
    act(api, booking, "confirm")
    make_past(booking)
    r = act(api, booking, "complete")
    assert r.status_code == 200 and r.data["status"] == "completed"
    assert [e["to_status"] for e in r.data["events"]] == ["pending", "confirmed", "completed"]


def test_cannot_complete_pending(admin_api, booking):
    make_past(booking)
    assert act(admin_api, booking, "complete").status_code == 400       # avval confirm kerak


def test_cannot_complete_future(admin_api, booking):
    act(admin_api, booking, "confirm")
    assert act(admin_api, booking, "complete").status_code == 400


def test_customer_cannot_complete(customer_api, admin_api, booking):
    act(admin_api, booking, "confirm")
    make_past(booking)
    assert act(customer_api, booking, "complete").status_code == 403


def test_history_records_actor(api, booking, provider, customer):  # noqa: F811
    api.force_authenticate(provider.user)
    act(api, booking, "confirm")
    events = list(BookingEvent.objects.filter(booking=booking))
    assert [e.actor for e in events] == [customer, provider.user]


@pytest.mark.django_db(transaction=True)
def test_concurrent_confirm_and_cancel(make_user, provider, svc):  # noqa: F811
    """Xodim tasdiqlayapti, mijoz shu soniyada bekor qilyapti: natija izchil, tarix to'g'ri."""
    cust = make_user("c1")
    c = APIClient()
    c.force_authenticate(cust)
    bid = c.post(URL, payload(provider, svc, next_monday_at(10))).data["id"]
    barrier, codes = threading.Barrier(2), {}

    def worker(user, name):
        cl = APIClient()
        cl.force_authenticate(user)
        barrier.wait()
        codes[name] = cl.post(f"{URL}{bid}/{name}/").status_code
        connection.close()

    ts = [threading.Thread(target=worker, args=(provider.user, "confirm")),
          threading.Thread(target=worker, args=(cust, "cancel"))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    b = Booking.objects.get(pk=bid)
    # Ikkala tartib ham qonuniy (pending->confirmed->cancelled yoki pending->cancelled, confirm rad etiladi),
    # lekin tarix doim oxirgi statusga mos keladi va hech narsa yo'qolmaydi
    assert b.status == Booking.Status.CANCELLED
    assert codes["cancel"] == 200
    assert list(b.events.values_list("to_status", flat=True))[-1] == "cancelled"
