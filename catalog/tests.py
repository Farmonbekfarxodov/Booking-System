import pytest
from django.urls import reverse

from accounts.models import User
from catalog.models import Provider, Service

SERVICE = {"name": "Soch olish", "description": "Klassik", "duration_minutes": 30, "price": "80000.00"}


@pytest.fixture
def service(db):
    return Service.objects.create(name="Manikyur", duration_minutes=60, price=100000)


# ---------- Service ----------
@pytest.mark.django_db
def test_anyone_can_list_services(api, service):
    r = api.get(reverse("service-list"))
    assert r.status_code == 200 and r.data["count"] == 1


def test_admin_creates_service(admin_api):
    r = admin_api.post(reverse("service-list"), SERVICE)
    assert r.status_code == 201, r.data
    assert Service.objects.get().name == "Soch olish"


def test_customer_cannot_create_service(customer_api):
    assert customer_api.post(reverse("service-list"), SERVICE).status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_create_service(api):
    assert api.post(reverse("service-list"), SERVICE).status_code == 401


@pytest.mark.parametrize("field,value", [
    ("duration_minutes", 0), ("duration_minutes", 7), ("duration_minutes", 600), ("price", "-1"),
])
def test_service_validation(admin_api, field, value):
    r = admin_api.post(reverse("service-list"), {**SERVICE, field: value})
    assert r.status_code == 400 and field in r.data


def test_service_name_unique_case_insensitive(admin_api, service):
    r = admin_api.post(reverse("service-list"), {**SERVICE, "name": "MANIKYUR"})
    assert r.status_code == 400 and "name" in r.data


def test_delete_service_is_soft(admin_api, api, service):
    assert admin_api.delete(reverse("service-detail", args=[service.id])).status_code == 204
    service.refresh_from_db()
    assert service.is_active is False                     # bazada qoladi
    api.force_authenticate(None)
    assert api.get(reverse("service-list")).data["count"] == 0   # mijozlarga ko'rinmaydi


# ---------- Provider ----------
def test_admin_creates_provider_and_user_becomes_staff(admin_api, make_user, service):
    u = make_user("usta")
    r = admin_api.post(reverse("provider-list"),
                       {"user_id": u.id, "display_name": "Usta Ali", "service_ids": [service.id]}, format="json")
    assert r.status_code == 201, r.data
    u.refresh_from_db()
    assert u.role == User.Role.STAFF
    assert r.data["services"][0]["name"] == "Manikyur"


def test_user_cannot_be_provider_twice(admin_api, make_user):
    u = make_user("usta")
    Provider.objects.create(user=u, display_name="A")
    r = admin_api.post(reverse("provider-list"), {"user_id": u.id, "display_name": "B"}, format="json")
    assert r.status_code == 400


def test_inactive_service_cannot_be_assigned(admin_api, make_user, service):
    service.is_active = False
    service.save()
    r = admin_api.post(reverse("provider-list"),
                       {"user_id": make_user("u").id, "display_name": "X", "service_ids": [service.id]}, format="json")
    assert r.status_code == 400 and "service_ids" in r.data


@pytest.mark.django_db
def test_filter_providers_by_service(api, make_user, service):
    other = Service.objects.create(name="Massaj", duration_minutes=45, price=150000)
    p1 = Provider.objects.create(user=make_user("a", role=User.Role.STAFF), display_name="A")
    p1.services.add(service)
    Provider.objects.create(user=make_user("b", role=User.Role.STAFF), display_name="B").services.add(other)
    r = api.get(reverse("provider-list"), {"service": service.id})
    assert [p["display_name"] for p in r.data["results"]] == ["A"]


def test_customer_cannot_create_provider(customer_api, make_user):
    r = customer_api.post(reverse("provider-list"), {"user_id": make_user("z").id, "display_name": "Z"})
    assert r.status_code == 403


def test_invalid_timezone_rejected(admin_api, make_user):
    r = admin_api.post(reverse("provider-list"),
                       {"user_id": make_user("tz").id, "display_name": "T", "timezone": "Mars/Base"}, format="json")
    assert r.status_code == 400 and "timezone" in r.data
