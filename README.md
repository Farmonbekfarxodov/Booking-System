# Booking System API

Appointment booking backend for a small service business (barbershop, clinic, beauty salon…).
Customers pick a service, see free time slots and book; the business manages services, staff,
working hours and bookings.

**Stack:** Python 3.12 · Django 5.1 · Django REST Framework · PostgreSQL 16 · JWT · Docker · pytest

**Highlights**

- Double booking is impossible — enforced by a PostgreSQL `EXCLUDE` constraint, a row lock and a
  concurrency test that fires two simultaneous requests at the same slot.
- Availability engine with timezone and DST support (working hours are stored in the provider's local time).
- Booking status state machine (`pending → confirmed → completed`, `cancelled`) with a cancellation policy
  and a full audit log of who changed what.
- 95 automated tests, Swagger/OpenAPI docs, one-command Docker setup.

---

## Quick start

```bash
git clone https://github.com/Farmonbekfarxodov/booking-system.git
cd booking-system
cp .env.example .env                 # set a long DJANGO_SECRET_KEY
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

| URL | What |
|---|---|
| http://localhost:8000/api/docs/ | Swagger UI (interactive API docs) |
| http://localhost:8000/api/schema/ | OpenAPI schema |
| http://localhost:8000/admin/ | Django admin |
| http://localhost:8000/api/health/ | Health check |

Run the tests:

```bash
docker compose exec web pytest -q
```

> If port 8000 is busy, set `WEB_PORT=8001` in `.env`. The database port is not exposed to the host
> on purpose — the web container reaches it over the internal Docker network.

### Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `BOOKING_SLOT_STEP_MINUTES` | 15 | Step between offered slots |
| `BOOKING_MIN_NOTICE_MINUTES` | 60 | A slot must start at least this far in the future |
| `BOOKING_MAX_ADVANCE_DAYS` | 60 | How far ahead customers can book |
| `BOOKING_CANCEL_DEADLINE_HOURS` | 2 | Customers cannot cancel later than this before start |

---

## Typical flow (curl)

```bash
# 1. register + login (customer)
curl -X POST localhost:8000/api/auth/register/ -H 'Content-Type: application/json' \
     -d '{"username":"ali","email":"ali@mail.com","password":"Str0ng-pass-123"}'
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login/ -H 'Content-Type: application/json' \
     -d '{"username":"ali","password":"Str0ng-pass-123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access"])')

# 2. free slots for service 1 on a date
curl "localhost:8000/api/availability/?service=1&date=2026-10-05"

# 3. book a slot
curl -X POST localhost:8000/api/bookings/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"service":1,"provider":1,"start_at":"2026-10-05T10:00:00+05:00"}'

# 4. booking history
curl "localhost:8000/api/bookings/?status=pending,confirmed" -H "Authorization: Bearer $TOKEN"
```

A second customer booking the same slot gets **`409 Conflict`**.

---

## API overview

| Method & path | Who | Description |
|---|---|---|
| `POST /api/auth/register/` | anyone | Register (always as `customer`) |
| `POST /api/auth/login/`, `/refresh/` | anyone | JWT access / refresh tokens |
| `GET/PATCH /api/auth/me/` | authenticated | Own profile |
| `GET /api/services/` | anyone | Active services |
| `POST/PATCH/DELETE /api/services/…` | admin | Manage services (DELETE = soft delete) |
| `GET /api/providers/?service=ID` | anyone | Staff offering a service |
| `POST/PATCH/DELETE /api/providers/…` | admin | Manage staff |
| `GET/POST /api/providers/{id}/working-hours/` | read: anyone · write: admin / that provider | Weekly schedule |
| `GET/POST /api/providers/{id}/time-off/` | admin / that provider | Vacations, sick days |
| `GET /api/availability/?service=&date=[&provider=]` | anyone | Free slots |
| `POST /api/bookings/` | customer | Create booking |
| `GET /api/bookings/[?status=]` | customer: own · staff: assigned · admin: all | Booking history |
| `GET /api/bookings/{id}/` | same as above | Booking with event history |
| `POST /api/bookings/{id}/confirm/` | provider / admin | `pending → confirmed` |
| `POST /api/bookings/{id}/cancel/` | customer (before deadline) / provider / admin | `→ cancelled` |
| `POST /api/bookings/{id}/complete/` | provider / admin | `confirmed → completed` (after start) |

Full request/response schemas: Swagger UI.

---

## Documentation

- [Architecture & database design](docs/ARCHITECTURE.md)
- [Edge cases and how they are handled](docs/EDGE_CASES.md)
- [How AI tools were used and verified](docs/AI_USAGE.md)

## Project structure

```
config/       settings, root urls
accounts/     custom User (roles), JWT auth, permission classes
catalog/      Service, Provider
scheduling/   WorkingHours, TimeOff, availability engine (availability.py)
bookings/     Booking, BookingEvent, business logic (services.py), status transitions
conftest.py   shared pytest fixtures
```
