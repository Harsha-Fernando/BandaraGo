# BandaraGo

A Django application for discovering attractions within 25 km of Bandaragama and arranging a one-day visit. PostgreSQL stores places; Django sessions store each visitor's chosen order.

## Setup

SRS deployment target: Python 3.12 and PostgreSQL 16+. Local development was verified on Python 3.13.7 and PostgreSQL 14.20 with user approval.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create a PostgreSQL user/database and fill in `.env` with their credentials. Generate a secret using `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

```sh
python manage.py migrate
python manage.py seed_categories
python manage.py import_verified_places --download-images
python manage.py createsuperuser
python manage.py runserver
```

The optional importer downloads attributed Commons photographs and creates ten source-verified drafts. If a download is rate-limited, wait before rerunning; completed records are retained. Review and publish the drafts in admin. Existing places are never overwritten; add any missing images through admin.

Open http://127.0.0.1:8000/ and use `/admin/` for staff management. Never share administrator credentials.

## Styles and checks

Precompiled Bootstrap 5.3.8 CSS and JavaScript are served locally from `static/css/bootstrap/` and `static/js/bootstrap/`. The MIT license is in `static/css/bootstrap/LICENSE`. A locally served Bootstrap Icons 1.13.1 SVG subset supplies interface icons (MIT license in `static/icons/LICENSE`). Necessary theme and layout overrides are in `static/css/style.css`. No npm, Node.js, CDN, or frontend build process is required:

```sh
python manage.py check
python manage.py test
```

Tests require a PostgreSQL role with permission to create a test database. Uploaded images live in ignored `media/`.

For deployment, set `DJANGO_DEBUG=False`, configure allowed hosts, serve collected static files and uploaded media through your web server, and terminate HTTPS there. Use `python manage.py collectstatic` and `python manage.py check --deploy`. Do not use Django's development server for deployment.

## Content management

Run `python manage.py seed_categories` once (safe to repeat). In `/admin/`, save a draft while preparing content. Assign one or more categories and add photos through the image rows before publishing. Use JPG, PNG, or WebP files up to 5 MB each; select at most one cover. Unpublish or reassign affected places before deleting an attached category. A place's distance is calculated from its coordinates, not entered manually.

Visitor instructions: [user guide](docs/user-guide.pdf) and `/help/`. Source attribution: [data sources](docs/data-sources.md). Test evidence and limitations: [validation](docs/testing/validation.md).

With the server running, open http://127.0.0.1:8000/static/js/map-check.html for the browser map behavior checks (no Node.js). These simulate Leaflet and do not request map tiles; check a real attraction map separately. For optional local load evidence, `python scripts/check_performance.py --users 10 --iterations 5` measures local HTTP responses and session writes (it does not measure browser or map rendering).

The user approved Bootstrap in place of the SRS Tailwind requirement. The SRS file is unchanged. Leaflet uses standard OSM tiles with visible attribution; `SECURE_REFERRER_POLICY` permits the cross-origin Referer required by the [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Do not replace this with `same-origin` or `no-referrer` in Django or a reverse proxy.
