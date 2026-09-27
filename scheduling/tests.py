import threading
from datetime import datetime, timedelta, timezone

import pytest
from django.db import connection
from django.urls import reverse

from accounts.models import User
from catalog.models import Provider
from scheduling.models import TimeOff, WorkingHours


@pytest.fixture
def provider(make_user):
    return Provider.objects.create(user=make_user("usta", role=User.Role.STAFF), display_name="Usta")


@pytest.fixture
def provider_api(api, provider):
    api.force_authenticate(provider.user)
    return api


def wh_url(p):
    return reverse("working-hours-list", args=[p.id])


def to_url(p):
    return reverse("time-off-list", args=[p.id])


def dt(day, hour):
    return datetime(2030, 1, day, hour, tzinfo=timezone.utc).isoformat()


# ---------- WorkingHours ----------
def test_provider_sets_own_working_hours(provider_api, provider):
    r = provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "09:00", "end_time": "13:00"})
    assert r.status_code == 201, r.data
    r = provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "14:00", "end_time": "18:00"})
    assert r.status_code == 201       # tushlikdan keyingi oraliq - ruxsat
    assert WorkingHours.objects.filter(provider=provider).count() == 2


def test_admin_sets_working_hours(admin_api, provider):
    assert admin_api.post(wh_url(provider), {"weekday": 1, "start_time": "10:00", "end_time": "12:00"}).status_code == 201


def test_other_staff_cannot_edit(api, provider, make_user):
    api.force_authenticate(make_user("boshqa", role=User.Role.STAFF))
    assert api.post(wh_url(provider), {"weekday": 0, "start_time": "09:00", "end_time": "10:00"}).status_code == 403


def test_customer_cannot_edit(customer_api, provider):
    assert customer_api.post(wh_url(provider), {"weekday": 0, "start_time": "09:00", "end_time": "10:00"}).status_code == 403


@pytest.mark.django_db
def test_anyone_can_read_working_hours(api, provider):
    WorkingHours.objects.create(provider=provider, weekday=0, start_time="09:00", end_time="18:00")
    r = api.get(wh_url(provider))
    assert r.status_code == 200 and r.data[0]["weekday_display"] == "Monday"


@pytest.mark.parametrize("start,end", [
    ("10:00", "09:00"),   # teskari
    ("09:00", "09:00"),   # nol uzunlik
    ("09:03", "10:00"),   # 5 ga karrali emas
])
def test_working_hours_validation(provider_api, provider, start, end):
    r = provider_api.post(wh_url(provider), {"weekday": 0, "start_time": start, "end_time": end})
    assert r.status_code == 400


def test_working_hours_overlap_rejected(provider_api, provider):
    provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "09:00", "end_time": "13:00"})
    r = provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "12:00", "end_time": "15:00"})
    assert r.status_code == 400
    # boshqa kunda xuddi shu vaqt - muammo emas
    r = provider_api.post(wh_url(provider), {"weekday": 1, "start_time": "12:00", "end_time": "15:00"})
    assert r.status_code == 201


def test_adjacent_intervals_allowed(provider_api, provider):
    """[09:00, 13:00) va [13:00, 18:00) kesishmaydi - chegaralar yarim ochiq."""
    provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "09:00", "end_time": "13:00"})
    r = provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "13:00", "end_time": "18:00"})
    assert r.status_code == 201


def test_update_does_not_conflict_with_itself(provider_api, provider):
    r = provider_api.post(wh_url(provider), {"weekday": 0, "start_time": "09:00", "end_time": "13:00"})
    url = reverse("working-hours-detail", args=[provider.id, r.data["id"]])
    assert provider_api.patch(url, {"end_time": "14:00"}).status_code == 200


# ---------- TimeOff ----------
def test_time_off_create_and_overlap(provider_api, provider):
    r = provider_api.post(to_url(provider), {"start_at": dt(10, 0), "end_at": dt(12, 0), "reason": "Ta'til"})
    assert r.status_code == 201, r.data
    r = provider_api.post(to_url(provider), {"start_at": dt(11, 0), "end_at": dt(13, 0)})
    assert r.status_code == 400
    r = provider_api.post(to_url(provider), {"start_at": dt(12, 0), "end_at": dt(13, 0)})   # yonma-yon
    assert r.status_code == 201


def test_time_off_invalid_range(provider_api, provider):
    assert provider_api.post(to_url(provider), {"start_at": dt(12, 0), "end_at": dt(10, 0)}).status_code == 400


def test_time_off_is_private(customer_api, provider):
    assert customer_api.get(to_url(provider)).status_code == 403


@pytest.mark.django_db
def test_time_off_db_constraint_blocks_overlap(provider):
    """Serializer'ni chetlab o'tsak ham baza ustma-ust dam olishni saqlamaydi."""
    from django.db import IntegrityError
    start = datetime(2030, 1, 10, tzinfo=timezone.utc)
    TimeOff.objects.create(provider=provider, start_at=start, end_at=start + timedelta(days=2))
    with pytest.raises(IntegrityError):
        TimeOff.objects.create(provider=provider, start_at=start + timedelta(days=1), end_at=start + timedelta(days=3))


@pytest.mark.django_db(transaction=True)
def test_time_off_race_condition(provider):
    """Ikki parallel so'rov bir xil oraliqni yaratmoqchi bo'lsa, faqat bittasi saqlanadi."""
    from rest_framework.test import APIClient
    start = datetime(2030, 2, 1, tzinfo=timezone.utc)
    payload = {"start_at": start.isoformat(), "end_at": (start + timedelta(hours=5)).isoformat()}
    barrier, codes = threading.Barrier(2), []

    def worker():
        c = APIClient()
        c.force_authenticate(provider.user)
        barrier.wait()
        codes.append(c.post(to_url(provider), payload).status_code)
        connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [201, 400]
    assert TimeOff.objects.filter(provider=provider).count() == 1
