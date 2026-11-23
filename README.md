# scs-library-management

School library management system: catalog, circulation, fines and reporting for a school library.

**Current state: Phase 1 (foundations) complete.** The Django backend, authentication with roles, member
management, Django admin and CI are in place. Catalog, circulation and reporting follow in later phases — see
[`docs/roadmap.md`](docs/roadmap.md).

## Stack

| Layer | Choice |
|---|---|
| Domain + API | Python 3.12, Django 5.2, Django REST Framework |
| Database | MySQL 8 (production and Docker dev); SQLite fallback for a workstation without MySQL |
| UI | Responsive TypeScript SPA (phase 2+, built with Node/Vite) |
| Jobs | Node worker for overdue sweep and report export (phase 4) |

Django owns the domain, business rules and permissions; Node is kept to the frontend build and one small job worker
so there is a single source of truth for library data.

## Repository layout

```
backend/
  config/            settings, urls, wsgi/asgi
  apps/accounts/     User (role-based), PatronProfile, auth + member API, admin
  tests/             pytest-django unit and API tests
docs/                roadmap and operational notes
docker-compose.yml   MySQL 8 + Django for local development
```

## Local setup (SQLite, fastest)

Requires Python 3.12+.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- API: http://127.0.0.1:8000/api/
- Admin: http://127.0.0.1:8000/admin/

Copy `.env.example` to `.env` to override any setting (see `backend/config/settings.py` for the full list).

## Local setup with MySQL 8 (recommended, matches production)

```bash
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Then http://127.0.0.1:8000/. The compose stack sets `DB_ENGINE=mysql` and starts MySQL 8.4 with a healthcheck, so
the app waits for the database before migrating.

To point the backend at any other MySQL server, install the driver and set the environment variables:

```bash
pip install -r requirements-mysql.txt
export DB_ENGINE=mysql DB_NAME=scs_library DB_USER=... DB_PASSWORD=... DB_HOST=... DB_PORT=3306
```

## Authentication and roles

Email + password login with server-side sessions (CSRF-protected, 8-hour idle timeout). Four roles: `student`,
`teacher`, `librarian`, `admin`. Permission checks run on the server for every endpoint, not just in the UI.

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/health/` | anyone | Liveness check |
| GET | `/api/auth/csrf/` | anyone | Sets the CSRF cookie before the first POST |
| POST | `/api/auth/login/` | anyone | `{email, password}` → session cookie + user |
| POST | `/api/auth/logout/` | signed in | Ends the session |
| GET | `/api/auth/me/` | signed in | Current user, role and member code |
| POST | `/api/auth/password/change/` | signed in | `{current_password, new_password}` |
| POST | `/api/auth/password/reset/` | anyone | Emails a reset link (always reports success) |
| POST | `/api/auth/password/reset/confirm/` | anyone | `{uid, token, new_password}` |
| GET | `/api/members/` | librarian, admin | Paginated member list, `?search=` by name/email/code |
| POST | `/api/members/` | librarian, admin | Create a member and email an invite link |
| GET | `/api/members/{id}/` | librarian, admin | Member detail |
| PATCH | `/api/members/{id}/` | librarian, admin | Update contact/class/section/status |
| POST | `/api/members/{id}/deactivate/` | librarian, admin | Disable login, mark profile inactive |

New members are created with an unusable password and `must_change_password=true`; they receive a one-time reset
link (console backend in development, SMTP in production).

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | Required in production |
| `DJANGO_DEBUG` | `true` | Set `false` in production (enables secure cookies) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma separated |
| `DJANGO_TIME_ZONE` | `UTC` | School's timezone |
| `DB_ENGINE` | `sqlite` | `mysql` to use MySQL |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | — | Used when `DB_ENGINE=mysql` |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | Base URL used in invite/reset emails |
| `EMAIL_BACKEND` | console | Set SMTP backend in production |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | Comma separated, required behind HTTPS |

## Notes

- SQLite is a convenience fallback for machines without MySQL. All tests run on SQLite, but every model and query is
  written for MySQL 8 (strict mode, `utf8mb4`, `DECIMAL` money) and the Docker compose stack uses MySQL from the start.
- No Docker daemon is needed to develop with the SQLite fallback, which is how phase 1 was verified here.
