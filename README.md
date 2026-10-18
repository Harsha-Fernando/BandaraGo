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

Open http://127.0.0.1:8000/; staff manage attractions and photographs at `/admin/`. Drafts need categories and an image before publishing. Optional: `python manage.py import_verified_places --download-images` creates twelve attributed drafts without overwriting existing records. Review drafts in admin. For existing reference places with blank schedules, `python manage.py update_reference_hours` fills the source-reviewed hours without replacing staff-entered schedules. `python manage.py update_visitor_details` fills blank weekly schedules and map fields and appends reviewed practical guidance without removing existing text. Uploaded photographs remain in local `media/`.

## Checks

```sh
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
```

Tests use PostgreSQL and require permission to create a test database. Check attraction maps in a browser with internet access. Optional load check: `python scripts/check_performance.py --users 10 --iterations 5` (server running).

`Bandarago/` contains configuration; `attractions/` and `planner/` are the two apps. Templates use the official Bootstrap [Album example](https://getbootstrap.com/docs/5.3/examples/album/) as a layout reference. Bootstrap 5.3.8 and Leaflet are precompiled local files in `static/vendor/`, with their licenses retained. SVG icons and their license are in `static/icons/`. Minimal CSS is in `static/css/style.css`. No npm, Node.js, or frontend build is required. Google Maps share embeds need internet but no application API key. Leaflet remains a fallback for places without an embed; OSM tiles need internet. Plan PDFs are generated locally with ReportLab and include ordered stops and map links. Displayed distances are straight-line measurements from Bandaragama.

Academic diagrams, attribution records, testing evidence and the user guide are retained locally and excluded from Git.
