import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from .models import User

PASSWORD = "Str0ng-pass-123"


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_register_creates_customer(client):
    r = client.post(reverse("register"), {"username": "ali", "email": "Ali@Mail.com", "password": PASSWORD})
    assert r.status_code == 201
    u = User.objects.get(username="ali")
    assert u.role == User.Role.CUSTOMER
    assert u.email == "ali@mail.com"          # email kichik harfga keltiriladi
    assert "password" not in r.data


@pytest.mark.django_db
def test_register_cannot_set_role(client):
    """Foydalanuvchi o'zini admin qilib ro'yxatdan o'tkaza olmasligi kerak."""
    client.post(reverse("register"), {"username": "hacker", "email": "h@m.com", "password": PASSWORD, "role": "admin"})
    assert User.objects.get(username="hacker").role == User.Role.CUSTOMER


@pytest.mark.django_db
def test_register_duplicate_email(client):
    User.objects.create_user("a", "a@m.com", PASSWORD)
    r = client.post(reverse("register"), {"username": "b", "email": "A@m.com", "password": PASSWORD})
    assert r.status_code == 400 and "email" in r.data


@pytest.mark.django_db
def test_register_weak_password(client):
    r = client.post(reverse("register"), {"username": "c", "email": "c@m.com", "password": "123"})
    assert r.status_code == 400


@pytest.mark.django_db
def test_login_and_me(client):
    User.objects.create_user("vali", "v@m.com", PASSWORD)
    r = client.post(reverse("login"), {"username": "vali", "password": PASSWORD})
    assert r.status_code == 200 and "access" in r.data and "refresh" in r.data
    client.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    me = client.get(reverse("me"))
    assert me.status_code == 200 and me.data["username"] == "vali"


@pytest.mark.django_db
def test_me_requires_auth(client):
    assert client.get(reverse("me")).status_code == 401


@pytest.mark.django_db
def test_me_cannot_change_role(client):
    u = User.objects.create_user("x", "x@m.com", PASSWORD)
    client.force_authenticate(u)
    client.patch(reverse("me"), {"role": "admin", "first_name": "X"})
    u.refresh_from_db()
    assert u.role == User.Role.CUSTOMER and u.first_name == "X"
