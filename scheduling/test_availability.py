from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from accounts.models import User
from catalog.models import Provider, Service
from scheduling.availability import Interval, compute_slots, get_available_slots
from scheduling.models import TimeOff, WorkingHours

UTC = timezone.utc
TASH = ZoneInfo("Asia/Tashkent")          # UTC+5, yozgi vaqt yo'q
M = timedelta(minutes=1)


def utc(h, m=0, day=6):
    return datetime(2030, 5, day, h, m, tzinfo=UTC)


# ---------- compute_slots: sof funksiya ----------
def test_basic_slots():
    slots = compute_slots([Interval(utc(9), utc(11))], [], 30 * M, 30 * M, earliest=utc(0))
    assert [s.start.hour * 60 + s.start.minute for s in slots] == [540, 570, 600, 630]


def test_slot_must_fit_inside_window():
    """60 daqiqalik xizmat 10:30 da boshlana olmaydi, ish 11:00 da tugaydi."""
    slots = compute_slots([Interval(utc(9), utc(11))], [], 60 * M, 30 * M, earliest=utc(0))
    assert [s.start for s in slots] == [utc(9), utc(9, 30), utc(10)]


def test_busy_interval_removes_overlapping_slots():
    busy = [Interval(utc(10), utc(10, 30))]
    slots = compute_slots([Interval(utc(9), utc(12))], busy, 60 * M, 30 * M, earliest=utc(0))
    # 09:30-10:30 va 10:00-11:00 bandlik bilan kesishadi; 09:00-10:00 va 10:30-11:30 yonma-yon - ruxsat
    assert [s.start for s in slots] == [utc(9), utc(10, 30), utc(11)]


def test_earliest_cuts_past_slots():
    slots = compute_slots([Interval(utc(9), utc(12))], [], 60 * M, 60 * M, earliest=utc(10, 1))
    assert [s.start for s in slots] == [utc(11)]


def test_split_windows_lunch_break():
    windows = [Interval(utc(9), utc(12)), Interval(utc(13), utc(15))]
    slots = compute_slots(windows, [], 90 * M, 30 * M, earliest=utc(0))
    assert utc(11) not in [s.start for s in slots]        # 11:00-12:30 tushlikka kirib qoladi
    assert [s.start for s in slots] == [utc(9), utc(9, 30), utc(10), utc(10, 30), utc(13), utc(13, 30)]


def test_no_windows_no_slots():
    assert compute_slots([], [], 30 * M, 15 * M, earliest=utc(0)) == []


# ---------- get_available_slots: baza bilan ----------
@pytest.fixture
def setup(make_user):
    service = Service.objects.create(name="Soch", duration_minutes=60, price=50000)
    provider = Provider.objects.create(user=make_user("usta", role=User.Role.STAFF), display_name="Usta",
                                       timezone="Asia/Tashkent")
    provider.services.add(service)
    # 2030-05-06 - dushanba (weekday=0)
    WorkingHours.objects.create(provider=provider, weekday=0, start_time=time(9), end_time=time(12))
    return provider, service


DAY = date(2030, 5, 6)
NOW = datetime(2030, 5, 1, tzinfo=UTC)


def test_local_time_converted_to_utc(setup, settings):
    settings.BOOKING_SLOT_STEP_MINUTES = 60
    provider, service = setup
    slots = get_available_slots(provider, service, DAY, now=NOW)
    # Toshkent 09:00 = UTC 04:00
    assert [s.start for s in slots] == [utc(4), utc(5), utc(6)]
    assert slots[0].start.astimezone(TASH).hour == 9


def test_time_off_blocks_slots(setup, settings):
    settings.BOOKING_SLOT_STEP_MINUTES = 60
    provider, service = setup
    TimeOff.objects.create(provider=provider, start_at=utc(5), end_at=utc(6))    # 10:00-11:00 Toshkent
    assert [s.start for s in get_available_slots(provider, service, DAY, now=NOW)] == [utc(4), utc(6)]


def test_day_without_working_hours(setup):
    provider, service = setup
    assert get_available_slots(provider, service, DAY + timedelta(days=1), now=NOW) == []   # seshanba


def test_min_notice(setup, settings):
    settings.BOOKING_SLOT_STEP_MINUTES = 60
    settings.BOOKING_MIN_NOTICE_MINUTES = 60
    provider, service = setup
    now = utc(4, 30)       # Toshkent 09:30 -> eng erta 10:30, demak 11:00 dan
    assert [s.start for s in get_available_slots(provider, service, DAY, now=now)] == [utc(6)]


@pytest.mark.django_db
def test_dst_timezone(make_user, settings):
    """Yozgi vaqtga o'tadigan mintaqada ham mahalliy 09:00 to'g'ri o'giriladi."""
    settings.BOOKING_SLOT_STEP_MINUTES = 60
    s = Service.objects.create(name="X", duration_minutes=60, price=1)
    p = Provider.objects.create(user=make_user("b", role=User.Role.STAFF), display_name="B", timezone="Europe/Berlin")
    p.services.add(s)
    WorkingHours.objects.create(provider=p, weekday=0, start_time=time(9), end_time=time(10))
    winter = get_available_slots(p, s, date(2030, 1, 7), now=NOW - timedelta(days=200))   # UTC+1
    summer = get_available_slots(p, s, date(2030, 7, 1), now=NOW)                          # UTC+2
    assert winter[0].start.hour == 8 and summer[0].start.hour == 7


# ---------- API ----------
def test_availability_endpoint(api, setup, settings):
    settings.BOOKING_SLOT_STEP_MINUTES = 60
    settings.BOOKING_MAX_ADVANCE_DAYS = 100000
    provider, service = setup
    r = api.get(reverse("availability"), {"service": service.id, "date": DAY.isoformat()})
    assert r.status_code == 200, r.data
    p = r.data["providers"][0]
    assert p["provider_id"] == provider.id
    assert p["slots"][0]["start"] == "2030-05-06T09:00:00+05:00"


def test_availability_provider_must_offer_service(api, setup, make_user):
    _, service = setup
    other = Provider.objects.create(user=make_user("x", role=User.Role.STAFF), display_name="X")
    r = api.get(reverse("availability"), {"service": service.id, "provider": other.id, "date": "2030-05-06"})
    assert r.status_code == 400 and "provider" in r.data


def test_availability_past_and_far_dates(api, setup):
    _, service = setup
    assert api.get(reverse("availability"), {"service": service.id, "date": "2000-01-01"}).status_code == 400
    assert api.get(reverse("availability"), {"service": service.id, "date": "2099-01-01"}).status_code == 400


def test_availability_inactive_service(api, setup):
    _, service = setup
    service.is_active = False
    service.save()
    assert api.get(reverse("availability"), {"service": service.id, "date": "2030-05-06"}).status_code == 400
