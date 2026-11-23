# Roadmap

The delivery plan is split into five milestones. Phase 1 is done; the rest follows in order.

| Phase | Scope | Status |
|---|---|---|
| 1 — Foundations | Repo skeleton, CI, custom user with roles, email/password auth, member management API, Django admin, MySQL-ready settings | **Done** |
| 2 — Catalog | `Book` / `BookCopy` models, CRUD, search and filters, CSV import with dry run, barcode workflow, responsive catalog UI | Next |
| 3 — Circulation | `Loan` / `Reservation`, `circulation/services.py` rules, atomic issue/return, fine engine, counter UI | Planned |
| 4 — Reporting | Circulation, overdue, fines and inventory reports; CSV/PDF export; Node worker for the overdue sweep and export queue | Planned |
| 5 — Hardening | Load check (10k titles, 1k members, 50k loans), security review, deployment runbook, librarian manual, training | Planned |

## Phase 1 detail

Delivered:

- `User` with roles student / teacher / librarian / admin, email login, forced password change flag.
- `PatronProfile` with unique member code (`STU-00001` / `TCH-00001`), class/section, department, status.
- Session auth with CSRF, rate-limited login and password reset, 8-hour idle timeout.
- Password reset via emailed one-time link; invited members have no usable password until they set one.
- Member directory API restricted to librarian/admin, with search, create, update and deactivate.
- Django admin for users and memberships.
- pytest suite covering auth flows and role enforcement; GitHub Actions CI.
- Docker Compose (Django + MySQL 8.4) and a SQLite fallback for machines without Docker.

Not yet built (planned, intentionally out of phase 1):

- SPA frontend (`frontend/`) and Node worker (`worker/`) — phases 2 and 4.
- CSV bulk import, catalog and circulation models.
- MySQL-specific integration tests in CI (CI currently runs on SQLite).
