# BandaraGo

Django website for discovering attractions within 25 km of Bandaragama and arranging an ordered, session-based day plan.

## Setup and run

Requires Python and PostgreSQL. SRS deployment target: Python 3.12 / PostgreSQL 16+; approved local environment: Python 3.13 / PostgreSQL 14.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create a PostgreSQL database/user and configure `.env`. Set a secret key using `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

```sh
python manage.py migrate
python manage.py seed_categories
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/; staff manage attractions and photographs at `/admin/`. Drafts need categories and an image before publishing. Optional: `python manage.py import_verified_places --download-images` creates twelve attributed drafts without overwriting existing records. Review drafts in admin. For existing reference places with blank times, `python manage.py update_reference_hours` fills the source-reviewed hours without replacing staff-entered times. Uploaded photographs remain in local `media/`.

## Checks

```sh
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
```

Tests use PostgreSQL and require permission to create a test database. With Django running, serve the browser map checks using `python -m http.server 8001 --bind 127.0.0.1 --directory docs/testing`, then open http://127.0.0.1:8001/map-check.html. These simulate Leaflet; check actual maps separately. Optional load check: `python scripts/check_performance.py --users 10 --iterations 5` (server running).

`Bandarago/` contains configuration; `attractions/` and `planner/` are the two apps. Templates use the official Bootstrap [Album example](https://getbootstrap.com/docs/5.3/examples/album/) as a layout reference. Bootstrap 5.3.8 and Leaflet are precompiled local files in `static/vendor/`, with their licenses retained. SVG icons and their license are in `static/icons/`. Minimal CSS is in `static/css/style.css`. No npm, Node.js, or frontend build is required. OSM tiles require internet and the configured cross-origin referrer policy.

[Attribution records](docs/data-sources.md) · [Visitor guide](docs/user-guide.pdf)
