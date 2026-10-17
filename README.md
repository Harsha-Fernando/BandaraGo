# BandaraGo

A Django application for discovering attractions within 25 km of Bandaragama and arranging a one-day visit. PostgreSQL stores places; Django sessions store each visitor's chosen order.

## Setup

Use Python 3.12+ and PostgreSQL 16+ for the SRS deployment environment.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create a PostgreSQL user/database and fill in `.env` with their credentials. Generate a secret using `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

```sh
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ and use `/admin/` for staff management. Never share administrator credentials.

## Styles and checks

Compiled Tailwind CSS is committed; Node.js is needed only when rebuilding styles:

```sh
npm ci
npm run build:css
python manage.py check
python manage.py test
```

Tests require a PostgreSQL role with permission to create a test database. Uploaded images live in ignored `media/`.

For deployment, set `DJANGO_DEBUG=False`, configure allowed hosts, serve collected static files and uploaded media through your web server, and terminate HTTPS there. Use `python manage.py collectstatic` and `python manage.py check --deploy`. Do not use Django's development server for deployment.
