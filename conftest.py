"""Barcha testlar uchun umumiy fixture'lar."""
import pytest
from rest_framework.test import APIClient

from accounts.models import User

PASSWORD = "Str0ng-pass-123"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make(username, role=User.Role.CUSTOMER, **kw):
        return User.objects.create_user(username, f"{username}@test.com", PASSWORD, role=role, **kw)
    return _make


@pytest.fixture
def admin_user(make_user):
    return make_user("boss", role=User.Role.ADMIN)


@pytest.fixture
def customer(make_user):
    return make_user("mijoz")


# Har bir rol uchun ALOHIDA client: bitta testda bir nechtasi ishlatilsa, bir-birining
# autentifikatsiyasini ustidan yozib yubormaydi.
@pytest.fixture
def admin_api(admin_user):
    c = APIClient()
    c.force_authenticate(admin_user)
    return c


@pytest.fixture
def customer_api(customer):
    c = APIClient()
    c.force_authenticate(customer)
    return c
