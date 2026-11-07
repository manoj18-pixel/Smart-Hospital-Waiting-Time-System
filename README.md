# MediQueue — Smart Hospital Waiting-Time System

MediQueue is a full-stack hospital appointment and queue-management system built with **Flask**, **SQLite/MySQL**, **SQLAlchemy**, **Bootstrap 5**, **Chart.js** and **Pytest**.

It solves a simple but important problem: when several patients try to book the same doctor at the same time, only one booking may succeed. MediQueue locks slots atomically in the database, estimates waiting time from the live queue, and gives patients, doctors and administrators a dedicated dashboard.

The project was built as a college full-stack submission and is intentionally self-contained: no JavaScript framework, no external database required, and demo data can be loaded with one command.

---

## Feature highlights

### Patient portal
- Register, sign in, sign out with hashed passwords and CSRF protection.
- Browse departments and doctors, including consultation fees, room numbers and working days.
- Pick a date and time slot; the slot is locked instantly.
- Booking confirmation page with a unique booking ID and emailed confirmation.
- View upcoming, past and cancelled appointments.
- Cancel an appointment (subject to a 2-hour cutoff and a 30-day limit).
- Live waiting-time estimate based on patients ahead and the doctor's average consultation time.

### Doctor portal
- Daily dashboard with today's queue and statistics.
- Check a patient in, complete a consultation, or mark a no-show.
- Add a delay for the day; waiting-time estimates update immediately.
- Browse any day's schedule with previous/next-day navigation.

### Admin portal
- KPI cards, Chart.js charts (bookings per day, department load, peak hours, slot utilization).
- JSON statistics endpoint at `/admin/api/stats`.
- CRUD for departments and doctors.
- Weekly schedule windows, leave/exceptions, and slot generation.
- Patient and doctor account activation/deactivation.
- Appointment search and filtering by date, doctor and status.
- Administrative cancellation that bypasses patient cutoffs.

### Engineering
- Atomic conditional `UPDATE` for slot claiming, plus database-level unique constraints.
- Responsive blue/white/light-green hospital theme with an off-canvas dashboard sidebar.
- Lighthouse 1.0 for accessibility, best practices and SEO on the public home page and admin dashboard.
- Friendly HTML error pages and JSON error envelopes for API callers.
- Audit log for authentication and privileged actions.
- Email notification log; failed delivery never rolls back a booking.
- 164 automated tests, including a real two-thread concurrency test.

---

## Tech stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3.1 (application factory + blueprints) |
| ORM / database | Flask-SQLAlchemy, SQLite by default, MySQL supported |
| Authentication | Flask-Login |
| Forms / CSRF | Flask-WTF, WTForms |
| Email | Flask-Mail |
| Rate limiting | Flask-Limiter |
| Migrations | Flask-Migrate |
| Frontend | Bootstrap 5.3, Font Awesome 6, Chart.js 4, custom CSS |
| Tests | Pytest, file-backed SQLite, two-thread concurrency test |

---

## Project structure

```
smart-hospital/
├── app/
│   ├── __init__.py            # application factory, CLI commands, error hooks
│   ├── config.py              # development / testing / production config
│   ├── constants.py           # roles, slot/appointment statuses, defaults
│   ├── extensions.py          # db, login_manager, csrf, mail, limiter, migrate
│   ├── forms.py               # all WTForms, including HospitalEmail
│   ├── models/                # users, doctors, departments, slots, appointments...
│   ├── services/              # booking, schedule, waiting, stats, mail, audit
│   ├── blueprints/            # main, auth, patient, doctor, admin, api, errors
│   ├── templates/             # Jinja2 pages, macros, email templates
│   └── static/                # theme.css, components.css, pages.css, app.js
├── instance/hospital.db       # development SQLite database (generated)
├── tests/                     # 164 Pytest tests
├── seed.py                    # realistic demo hospital data
├── run.py                     # development entry point
├── wsgi.py                    # production WSGI entry point
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## Quick start

### Windows PowerShell

```powershell
cd smart-hospital

# Create a self-contained virtual environment inside the project
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Create tables and load demo departments, doctors, schedules and patients
.\.venv\Scripts\python.exe -m flask --app run.py seed

# Start the development server
.\.venv\Scripts\python.exe run.py
```

Open **http://127.0.0.1:5000**. If port 5000 is already used by another project, start with `--port 5001` and open that URL instead.

### macOS / Linux

```bash
cd smart-hospital
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m flask --app run.py seed
python run.py
```

### Alternative: Flask CLI only

```bash
flask --app run.py init-db        # create tables + default settings
flask --app run.py generate-slots # create future slots for every doctor
flask --app run.py seed           # complete demo data
flask --app run.py run
```

Running `seed` more than once is safe. It reuses existing users/departments and tops up future slots.

### Deploy to Vercel

Vercel runs the app as a serverless function (`api/index.py`), so the local
SQLite file cannot be used: its filesystem is read-only and ephemeral. Create a
free hosted database first, for example [Neon](https://neon.tech) (PostgreSQL)
or [Aiven](https://aiven.io) (MySQL), then:

1. Push this repository to GitHub.
2. In Vercel, choose **Add New → Project** and import the repository.
3. Add these **Environment Variables** (Project → Settings → Environment
   Variables) for Production, Preview and Development:

   | Name | Value |
   | --- | --- |
   | `SECRET_KEY` | a long random string (`python -c "import secrets; print(secrets.token_hex(32))"`) |
   | `FLASK_CONFIG` | `production` |
   | `DATABASE_URL` | `postgresql://user:password@host/db?sslmode=require` or `mysql+pymysql://user:password@host/db` |
   | `MAIL_SUPPRESS_SEND` | `true` (or configure real SMTP credentials) |

4. Deploy. On the first request the app creates the schema and loads the demo
   data automatically when `VERCEL=1` is present (Vercel adds it for you), so
   no terminal step is required. To do it manually — or to use a different
   database — run this from your machine instead:

   ```powershell
   $env:SECRET_KEY = "any-temporary-value"
   $env:FLASK_CONFIG = "production"
   $env:DATABASE_URL = "postgresql://user:password@host/db?sslmode=require"
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m flask --app run.py init-db
   .\.venv\Scripts\python.exe -m flask --app run.py seed
   ```

5. Open the URL Vercel gives you, such as
   `https://smart-hospital-waiting-time-system.vercel.app`.

Notes:

- `api/index.py` starts the app with the `production` config and Vercel loads
  every other route through the rewrite in `vercel.json`.
- The app refuses to boot in production without `SECRET_KEY` and
  `DATABASE_URL`, so misconfiguration fails fast instead of silently falling
  back to SQLite.
- `AUTO_INIT_DB` (default `true` on Vercel) creates missing tables and default
  settings. `AUTO_SEED_DEMO` (default `true` on Vercel) inserts the demo
  hospital once, when the admin account does not exist. Set either to `false`
  for a clean production database.
- Bootstrap, Font Awesome, Chart.js, Inter/Poppins and the photos are served
  from `app/static/vendor` and `app/static/img`, so the UI works on networks
  that block Google Fonts or public CDNs.
- Demo credentials are the same as below; change the passwords before using a
  public deployment.

---

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Admin | `admin@mediqueue.local` | `Admin@123` |
| Doctor | `dr.arjun@mediqueue.local` | `Doctor@123` |
| Patient | `asha@example.com` | `Patient@123` |
| Patient | `ravi@example.com` | `Patient@123` |

Other seeded doctors use the pattern `dr.kavya@mediqueue.local`, `dr.rahul@mediqueue.local`, etc., all with `Doctor@123`. Additional patients use `meera@example.com`, `priya@example.com`, etc., all with `Patient@123`.

---

## Running the tests

From `smart-hospital/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result:

```
164 passed
```

Useful variants:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_concurrency.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_booking.py tests/test_cancellation.py
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
```

The test suite uses a temporary **file-backed SQLite** database so that the concurrency test can open two independent connections. CSRF and rate limiting are disabled only in the testing configuration; mail is suppressed but notifications are still written to the database.

---

## How double-booking is prevented

The slot is claimed with one atomic conditional update:

```sql
UPDATE slots
SET status = 'BOOKED'
WHERE id = :slot_id AND status = 'AVAILABLE';
```

`claim_slot()` returns `True` only when exactly one row changed. Two concurrent requests therefore produce:

- one winner (`rowcount == 1`) that proceeds to create the appointment;
- one loser (`rowcount == 0`) that receives HTTP **409 Conflict**.

Three layers protect the invariant:

1. `UNIQUE(doctor_id, slot_date, start_time)` on `slots`.
2. The conditional `UPDATE ... WHERE status = 'AVAILABLE'`.
3. `UNIQUE(slot_id)` on `appointments` as a final guard.

On SQLite the booking transaction begins with a `rollback()` so the write transaction does not have to upgrade a read transaction (which would cause `SQLITE_BUSY`). On InnoDB the conditional update locks the matched row, so the loser waits and then re-evaluates the `WHERE` clause.

The concurrency test (`tests/test_concurrency.py`) logs two clients in, synchronises them with a `Barrier(2)`, posts the same slot from both threads, and asserts that the status codes are exactly `[302, 409]`, that exactly one appointment exists, and that the slot is `BOOKED`.

---

## Waiting-time calculation

```
patients_ahead = number of active appointments earlier than this slot
estimated_wait = patients_ahead × doctor.avg_consult_minutes + doctor_delay
```

The estimate shown after booking uses the appointments already queued for that doctor and date. On the day of the visit, `live_wait()` recalculates the estimate from the live queue, including checked-in and in-consultation patients. Doctors can set a delay for the day, which is added to every estimate.

When a consultation is completed, the doctor's `avg_consult_minutes` is gradually adjusted using a weighted moving average of the actual consultation duration.

---

## Booking and cancellation rules

Defaults are configurable through environment variables or the `settings` table:

| Rule | Default |
|---|---|
| Booking window | 30 days ahead |
| Cancellation cutoff | 2 hours before the appointment |
| Maximum patient cancellations | 3 per rolling 30 days |
| One active appointment per doctor per date per patient | enforced |
| Past slots | cannot be booked |
| Past slots | cannot be reopened by cancellation |
| Admin cancellation | bypasses cutoff and cancellation limit |

---

## Email notifications

Booking confirmations, cancellations and hospital-initiated cancellations are rendered from HTML + text templates. Every attempt is recorded in the `notifications` table with `sent` or `failed` status, recipient, subject, body and error message.

In development, `MAIL_SUPPRESS_SEND=true` prevents real delivery. To inspect mail with [MailHog](https://github.com/mailhog/MailHog), run it on `localhost:1025` and set:

```env
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_SUPPRESS_SEND=false
```

A delivery failure is deliberately non-fatal: the appointment remains confirmed and only the notification is marked `failed`.

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/doctors/<id>/slots?date=YYYY-MM-DD` | Serialised slots for a date |
| `GET` | `/api/doctors/<id>/next-available?from=YYYY-MM-DD` | Next bookable slot |
| `GET` | `/api/appointments/<booking_id>/wait` | Live waiting-time estimate (owner only) |
| `GET` | `/admin/api/stats` | Admin dashboard aggregates (admin JSON) |

API errors use a consistent envelope:

```json
{
  "ok": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to do that."
  }
}
```

Paths containing an `/api/` segment return JSON even for role violations and anonymous requests. HTML pages return the friendly `400`, `403`, `404`, `409`, `429` and `500` templates.

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```env
SECRET_KEY=change-me-to-a-random-32-byte-secret
FLASK_CONFIG=development
FLASK_APP=run.py

# Default is SQLite at instance/hospital.db.
# MySQL example:
# DATABASE_URL=mysql+pymysql://root:password@localhost/mediqueue

MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_SUPPRESS_SEND=true
MAIL_DEFAULT_SENDER=MediQueue <no-reply@mediqueue.local>

CANCELLATION_CUTOFF_HOURS=2
MAX_CANCELLATIONS_PER_30_DAYS=3
BOOKING_OPEN_DAYS=30
RATELIMIT_STORAGE_URI=memory://
```

Production additionally requires a real `SECRET_KEY` and uses secure cookies plus HTTPS-oriented settings.

### Switching to MySQL

```bash
pip install pymysql
```

```env
DATABASE_URL=mysql+pymysql://user:password@localhost/mediqueue
```

Create the database, then run:

```bash
flask --app run.py init-db
flask --app run.py seed
```

The atomic slot claim works on both SQLite and InnoDB.

---

## Security notes

- Passwords are stored as Werkzeug hashes (PBKDF2/scrypt), never plaintext.
- CSRF is enabled on every form; failures return a friendly 400 page or JSON envelope.
- Session cookies are `HttpOnly` and `SameSite=Lax`.
- Responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and `Permissions-Policy`.
- Role decorators protect every portal; deactivated accounts lose access immediately.
- Login attempts are rate limited and audited.
- Search inputs are parameterised through SQLAlchemy; wildcard/SQL-injection payloads are treated as text.

---

## Troubleshooting

**`flask` is not recognised**
Use the interpreter directly: `.\.venv\Scripts\python.exe -m flask --app run.py seed`.

**Empty doctor dashboard**
Run `flask --app run.py seed` again, or `flask --app run.py generate-slots`. The seeder creates a same-day demo queue even if the OPD window has already ended.

**Port 5000 already in use**
Run `python run.py` after changing the port in `run.py`, or stop the other process.

**Emails are not arriving**
This is expected with `MAIL_SUPPRESS_SEND=true`. Inspect the `notifications` table or start MailHog and disable suppression.

**Tests fail with a database lock**
Run them from `smart-hospital/` so `pytest.ini` is picked up, and avoid running two suites against the same temporary directory. Each test gets its own file-backed SQLite database.

**`email_validator` rejects `.local` demo addresses**
The app uses a custom `HospitalEmail` validator that accepts internal `.local` addresses and test-only `.test` addresses, while still rejecting malformed input.

---

## Academic notes and possible extensions

This project focuses on correctness of the booking invariant and a complete three-role workflow. Natural extensions include:

- SMS/WhatsApp reminders in addition to email.
- Doctor-initiated rescheduling with automatic patient notification.
- Payment gateway integration for consultation fees.
- Calendar export (`.ics`) and PDF prescriptions.
- Alembic migrations with versioned seed fixtures.
- A REST API secured with token authentication for a mobile client.

---

## License

Created for educational use. You may adapt it for coursework, portfolios and learning.
