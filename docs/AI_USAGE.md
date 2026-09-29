# How AI was used

I built this project together with an AI assistant (Claude). AI was used as a pair programmer:
it proposed code, I reviewed it, ran it, tested it and made the final decisions. Nothing was
merged without passing the test suite.

## What AI did

- Scaffolding: Django project, Docker Compose, settings, app skeletons.
- Boilerplate: serializers, viewsets, URL routing, admin classes.
- First drafts of tests, which I then extended with edge cases.
- First draft of this documentation.

## What was decided and verified by me

- **Architecture:** four apps with one-way dependencies; business logic in service functions, thin views.
- **Double-booking strategy:** DB `EXCLUDE` constraint as the source of truth + row lock + re-check,
  and a concurrency test to prove it.
- **Data rules:** price and `end_at` snapshots, soft delete, local-time working hours vs UTC bookings,
  half-open intervals, role cannot be self-assigned, 404 instead of 403 for foreign objects.
- **Product rules:** min notice, max advance, cancellation deadline, who can confirm/cancel/complete.

## Problems found in AI-generated code (and how)

| Problem | How it was found | Fix |
|---|---|---|
| `Provider.timezone` used `choices=available_timezones()` → Django reported *"models have changes not reflected in a migration"* inside Docker | Ran `migrate` in the container (different Python/tzdata than where the migration was generated) | Removed `choices`, validate timezone in the serializer; added a test |
| Concurrent `TimeOff` inserts sometimes failed with **`deadlock detected`** (~1/20) | Concurrency test run in a loop | Lock the provider row before checking/inserting; re-ran 30× with no failure. Same pattern applied to bookings |
| Bookings migration could run before the `btree_gist` extension was installed | Fresh test DB failed: *"bigint has no default operator class for gist"* | Explicit migration dependency on `scheduling.0001` |
| Test fixtures `admin_api` and `customer_api` shared one client — the second silently overwrote the first's auth, so an "admin" request was actually sent as a customer | A permission test failed unexpectedly (403 instead of 200) | Separate `APIClient` per role |
| `MinValueValidator(0)` on a `DecimalField` → DRF warnings | Warnings in test output | `MinValueValidator(Decimal("0"))` |

## How results were checked

- `pytest` after every step (95 tests at the end), including concurrency tests with real threads and a real PostgreSQL.
- Flaky-test hunting: concurrency tests executed 10–30 times in a loop.
- `manage.py makemigrations --check` and OpenAPI schema generation with zero warnings.
- Manual checks in Swagger UI and Django admin.
