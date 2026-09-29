# Edge cases

Every case below is covered by an automated test (file in brackets).

## Concurrency

| Case | Behaviour |
|---|---|
| **Two customers book the same slot at the same moment** | Provider row lock serializes them; the first gets `201`, the second sees the slot taken and gets `409 Conflict`. Backed by a DB `EXCLUDE` constraint. Test starts two threads behind a `Barrier`. (`bookings/tests.py::test_race_condition_two_users_same_slot`) |
| Overlap sneaks past application code (bug, admin panel, raw ORM) | PostgreSQL rejects it (`IntegrityError`). (`test_db_constraint_blocks_overlap_even_without_service_layer`) |
| Provider confirms while the customer cancels at the same second | Booking row lock → transitions run one after another; history stays consistent. (`bookings/test_transitions.py::test_concurrent_confirm_and_cancel`) |
| Two overlapping time-off requests at once | One succeeds, one gets `400`. Found a real deadlock here, fixed with a row lock. (`scheduling/tests.py::test_time_off_race_condition`) |

## Booking time

| Case | Behaviour |
|---|---|
| Partial overlap (10:00–11:00 booked, request 10:30) | `409` |
| Adjacent slot (10:00–11:00 booked, request 11:00) | Allowed — intervals are half-open `[start, end)` |
| Service does not fit before closing (60-min service at 17:30, closes 18:00) | `400` |
| Outside working hours / day off | `400` |
| Not aligned to slot step (10:07) | `400` |
| In the past or sooner than minimum notice | `400` |
| Further ahead than `BOOKING_MAX_ADVANCE_DAYS` | `400` |
| Provider has time off | `400`; slot not shown in availability |
| Same customer, overlapping booking with another provider | `400` (second `EXCLUDE` constraint on customer) |
| Cancelled booking | Slot becomes free again immediately |
| Lunch break (09–13, 14–18) | No slot crosses the break |

## Timezones

| Case | Behaviour |
|---|---|
| Provider in `Asia/Tashkent`, server in UTC | Working hours stored in local time, converted with `zoneinfo`; API returns `…T09:00:00+05:00` |
| Daylight-saving time (e.g. `Europe/Berlin`) | "09:00 local" is 08:00 UTC in winter and 07:00 UTC in summer (`test_dst_timezone`) |
| Client sends time in another offset | Accepted — all times are ISO 8601 with offset and compared in UTC |
| Invalid timezone name | `400` |

## Data integrity

| Case | Behaviour |
|---|---|
| Service price changes after booking | Booking keeps its price snapshot |
| Service duration changes after booking | Booking keeps its stored `end_at` |
| Service / provider "deleted" | Soft delete (`is_active=False`); hidden from customers, history intact; DB uses `PROTECT` |
| Inactive service or provider | Cannot be booked or assigned |
| Provider does not offer the chosen service | `400` |
| Time off added over existing active bookings | Rejected — business must resolve the bookings first |
| Overlapping working-hour intervals on the same day | `400` |
| Duration not a multiple of 5, negative price, duplicate service name (case-insensitive) | `400` (also `CHECK` constraints in DB) |

## Status & permissions

| Case | Behaviour |
|---|---|
| Invalid transition (e.g. `cancelled → confirmed`, `completed → pending`) | `400` — state machine |
| Complete a booking that is still `pending` or hasn't started | `400` |
| Customer cancels less than `BOOKING_CANCEL_DEADLINE_HOURS` before start | `400`; provider/admin can still cancel |
| Cancel a finished booking | `400` |
| Customer tries to confirm/complete | `403` |
| Access to someone else's booking | `404` (existence is not leaked) |
| Register with `"role": "admin"` | Ignored, user is always `customer` |
| Change own role via `PATCH /me/` | Ignored |
| Staff tries to book | `400` — only customers book |
| Staff edits another provider's schedule | `403` |
