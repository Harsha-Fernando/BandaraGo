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
python manage.py import_submission_data
python manage.py createsuperuser
python manage.py runserver
```

The system submission must include the local `submission-data/` folder next to `manage.py`. The import restores the current 13 places, categories, staff-edited information, publication states and photographs without internet. It skips existing place slugs and never overwrites staff edits. A GitHub clone does not contain this ignored data folder; copy it from the provided submission package before importing.

Open http://127.0.0.1:8000/; staff manage attractions and photographs at `/admin/`. Drafts need categories and an image before publishing. Uploaded photographs remain in local `media/`.

To prepare the data package on the original installation, run `python manage.py export_submission_data` before assembling the submission ZIP. The destination must not already exist. To refresh it while retaining the previous export, use a new ignored path, for example `python manage.py export_submission_data .local-checks/submission-data-new`, then include that new export as `submission-data/` in the ZIP. The export contains attraction data and photos only, with no administrator accounts, passwords or sessions. Retain image-source/licence records with the submission.

For a separate reference-only dataset, `python manage.py seed_categories` and `python manage.py import_verified_places --download-images` create twelve drafts for staff review; they do not restore the current catalogue. The optional `update_reference_hours` and `update_visitor_details` commands fill reviewed reference information while retaining existing staff schedules/map fields.

## Checks

```sh
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
```

Tests use PostgreSQL and require permission to create a test database. Check attraction maps in a browser with internet access. Optional load check: `python scripts/check_performance.py --users 10 --iterations 5` (server running).

`Bandarago/` contains configuration; `attractions/` and `planner/` are the two apps. Templates use the official Bootstrap [Album example](https://getbootstrap.com/docs/5.3/examples/album/) as a layout reference. Bootstrap 5.3.8 and Leaflet are precompiled local files in `static/vendor/`, with their licenses retained. SVG icons and their license are in `static/icons/`. Minimal CSS is in `static/css/style.css`. No npm, Node.js, or frontend build is required. Google Maps share embeds need internet but no application API key. Leaflet remains a fallback for places without an embed; OSM tiles need internet. Plan PDFs are generated locally with ReportLab and include ordered stops and map links. Displayed distances are straight-line measurements from Bandaragama.
