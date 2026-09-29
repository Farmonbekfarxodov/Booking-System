#!/bin/sh
# Konteyner ishga tushganda: migratsiya -> (ixtiyoriy) demo ma'lumot -> gunicorn
set -e
python manage.py migrate --noinput
if [ "$SEED_DEMO" = "1" ]; then
    python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --access-logfile -
