# Smart Hospital Waiting-Time System

### Complete Full-Stack Project Plan (v1.0)

| Item | Detail |
|---|---|
| Project name | **MediQueue** — Smart Hospital Waiting-Time System |
| Document type | Project plan: architecture, database design, module specification, UI plan, test plan |
| Stack | HTML5, CSS3, Vanilla JavaScript, Bootstrap 5, Python 3.12 + Flask 3, SQLAlchemy ORM, SQLite (dev) / MySQL 8 (prod) |
| Libraries | Flask-Login, Flask-WTF, Flask-Mail, Flask-Migrate, Flask-Limiter, Chart.js, Font Awesome |
| Testing | Pytest, Flask test client, pytest-cov |
| Status | **Plan approved → ready to build** |
| Target | College full-stack development project (major project / capstone) |

---

## 1. Executive Summary

MediQueue is a hospital appointment and **live queue management** platform. Patients register, choose a department and doctor, pick a date and time slot, and book an appointment. Each doctor can serve **one patient per time slot per date**. The instant a booking succeeds, that slot is locked in the database and disappears from every other patient's screen as *Booked*. The system then shows a **confirmation with a booking ID**, an **estimated waiting time**, and a **queue position**.

The technical centre of the project is **concurrency-safe slot locking**: even if two patients click *Book* on the same slot at the exact same moment, exactly one booking succeeds and the other receives a clean "slot already booked, please choose another" response. This is guaranteed by a database `UNIQUE` constraint plus an atomic conditional update inside a transaction — not by JavaScript.

### One-sentence goal

> Let a patient book a hospital appointment in under 60 seconds while guaranteeing that no doctor is ever double-booked for the same date and time slot.

### What makes this project stand out in a viva

1. **A real correctness problem** (race conditions) solved with database constraints, demonstrated by an automated concurrent-booking test.
2. **Three complete role-based dashboards** (patient, doctor, admin) with charts.
3. **A waiting-time engine** that is simple enough to explain and useful in practice.
4. **A polished, responsive UI** with real booking interactions, not static pages.
5. **A documented 20-case test plan** mapped directly to the requirement list.

---

## 2. Problem Statement

| Pain point in hospitals today | MediQueue response |
|---|---|
| Patients queue physically for hours without knowing when their turn is | Live queue position + estimated waiting time |
| Reception books the same doctor twice by mistake | Database-level one-booking-per-slot constraint |
| No visibility of doctor availability by department | Department → doctor → date → slot wizard |
| Appointments tracked in registers / Excel | Central SQL database + patient history |
| No-shows waste slots | Cancellation rules + automatic slot re-opening |
| Admin has no operational view | Admin dashboard with counts and charts |
| Doctors don't know their day | Doctor daily schedule screen |

---

## 3. Objectives and Success Criteria

### 3.1 Functional objectives

1. Secure patient registration/login/logout with email + password.
2. Department and doctor discovery with profiles and availability.
3. Date-wise, slot-wise appointment booking.
4. **Automatic, atomic slot locking** — one doctor, one patient, one slot, one date.
5. Booking confirmation with a human-readable booking ID and email.
6. Appointment view / cancel / reschedule (subject to hospital rules).
7. Estimated waiting-time and live queue position.
8. Doctor daily schedule.
9. Admin management of doctors, departments, schedules, patients, appointments.
10. Admin analytics dashboard.
11. Appointment history and status tracking.
12. Fully responsive, modern hospital-themed UI.

### 3.2 Non-functional objectives

| Quality | Target |
|---|---|
| Correctness | 0 double bookings under any concurrency; enforced by DB constraint |
| Response time | Slot list API < 300 ms for a normal day; booking endpoint < 500 ms locally |
| Security | Hashed passwords, CSRF protection, role-based access, rate limiting, audit log |
| Usability | Mobile-first, keyboard accessible, clear success/error feedback |
| Testability | ≥ 85% backend coverage; all 20 required test cases automated |
| Maintainability | Service layer separated from routes; one responsibility per module |

### 3.3 Explicit non-goals (v1)

- Online payments / insurance claims.
- Video consultations.
- Real SMS/WhatsApp gateway (email only; console mailer in development).
- Native mobile apps (responsive web only).
- HIPAA/GDPR certification (best-practice privacy design only).
- AI diagnosis or medical advice.

---

## 4. Users, Roles and Permissions

| Capability | Patient | Doctor | Admin |
|---|:---:|:---:|:---:|
| Register / login / logout | ✅ | ✅ (admin-created) | ✅ (seeded) |
| Browse departments & doctors | ✅ | ✅ | ✅ |
| View slots / book appointment | ✅ | ❌ | ❌ (can book on behalf, optional) |
| View own appointments | ✅ | ❌ | ✅ all |
| Cancel own appointment | ✅ (rules apply) | ❌ | ✅ any time |
| View daily schedule | ❌ | ✅ own only | ✅ any doctor |
| Mark patient checked-in / complete | ❌ | ✅ own queue | ✅ |
| Manage doctors / departments / schedules | ❌ | ❌ | ✅ |
| View analytics dashboard | ❌ | ❌ | ✅ |
| Manage patients (activate/deactivate) | ❌ | ❌ | ✅ |

**Rules**
- One account = one role (`users.role ∈ {patient, doctor, admin}`).
- A doctor account is always linked to a `doctors` row; an admin has no patient/doctor profile.
- Route access is enforced by a `@role_required("admin")` decorator on the server. Hiding a button in HTML is **not** security.

---

## 5. Feature Specification (mapped to the 20 requirements)

### 5.1 Patient features

| # | Feature | Behaviour / acceptance |
|---|---|---|
| 1 | Registration | Full name, email, phone, password + confirm. Email unique (case-insensitive). Password ≥ 8 chars with letter + number. Success → login page with flash message. |
| 2 | Login / Logout | Email + password; generic error message ("Invalid email or password") to avoid account enumeration. Session cookie is HttpOnly. Logout clears session. |
| 3 | Patient dashboard | Cards: upcoming appointments, completed visits, cancelled, next appointment countdown; quick "Book appointment" CTA; recent activity. |
| 4 | Department selection | Grid of department cards (icon, name, description, doctor count). Only active departments. |
| 5 | Doctor selection | Doctors filtered by department; cards with photo, specialization, experience, fee, next-available date. Profile page with bio, qualifications, weekly schedule. |
| 6 | Availability & scheduling | Weekly recurring schedule templates generate dated slots; leaves/blocked dates remove slots. |
| 7 | Date + time-slot booking | Booking wizard: Department → Doctor → Date → Slot → Confirm. Dates limited to next 30 days; past dates disabled. |
| 8 | One patient per slot | Enforced by DB unique constraint on `(doctor_id, slot_date, start_time)` and unique `appointments.slot_id`. |
| 9 | Auto-close slot | On successful booking, `slots.status = BOOKED`, `slot_id` linked to appointment. Slot vanishes from availability API immediately. |
| 10 | No duplicate booking | Second booking attempt returns HTTP 409 with a friendly message; UI refreshes slot list automatically. |
| 11 | Available vs unavailable display | Green = Available; grey/red = Booked; amber = Few left? (optional); blocked = Unavailable. Legend always visible. |
| 12 | Immediate lock example | 1:00 PM booked by Patient A → API marks it BOOKED → Patient B sees 1:00 PM disabled and books 2:00 PM. |
| 13 | Confirmation | Success page with booking ID (`MQ-20261106-0007`), doctor, department, date, time, room, fee, queue position, estimated wait. Email sent. |
| 14 | Manage appointments | List with filters (upcoming / past / cancelled). Cancel before cutoff (default 2 hours); reason required; confirmation modal. |
| 15 | Estimated waiting time | Computed from queue position × doctor's average consultation time + current delay. Shown before booking and on confirmation. |
| 19 | History & status | Status timeline: Confirmed → Checked-in → Completed / Cancelled / No-show. |
| 20 | Email notification | HTML email on booking, cancellation, and (optional) reminder 24 h before. |

### 5.2 Doctor features

| # | Feature | Behaviour |
|---|---|---|
| 17 | Daily schedule | Date picker (default today) → ordered list of patients: slot time, booking ID, patient name, status, check-in time, wait time. Buttons: Check in, Complete, No-show. |
| — | Queue control | Doctor can mark current patient complete, which reduces waiting time for everyone behind. |
| — | Profile | View/edit short bio, consultation fee, average consultation minutes. Cannot change department without admin. |

### 5.3 Admin features

| # | Feature | Behaviour |
|---|---|---|
| 16 | Manage doctors | CRUD doctor + linked user account; assign department; set fee, room, average consultation minutes, photo. Deactivate instead of delete when appointments exist. |
| 16 | Manage departments | CRUD; icon name + description + floor. Deactivate hides it from patients. |
| 16 | Manage schedules | Weekly template editor per doctor (weekday, start, end, slot duration, max patients) + leave/blocked dates. |
| 16 | Manage patients | Search, view appointment history, activate/deactivate accounts. |
| 18 | Dashboard | KPI cards: total patients, doctors, appointments today, available slots today, booked slots today, cancellation rate. Charts: bookings per day (line), department load (doughnut), slot utilization (bar), peak hours (bar). |
| 19 | Appointment oversight | Filter all appointments by date/doctor/status; cancel with reason; export CSV (optional). |

---

## 6. System Architecture

### 6.1 High-level architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (responsive)                      │
│  HTML5 + Bootstrap 5 + custom CSS + Vanilla JS + Chart.js        │
│  Pages: landing, auth, patient, doctor, admin                    │
│  JS modules: booking.js, slots.js, dashboard.js, ui.js           │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTPS (JSON + HTML)
┌───────────────────────────────▼──────────────────────────────────┐
│                      Flask Application (app factory)             │
│                                                                  │
│  Blueprints (HTTP layer)                                         │
│   auth · main · patient · booking · doctor · admin · api · errors│
│                                                                  │
│  Services (business rules)                                       │
│   slot_service · booking_service · waiting_service ·             │
│   schedule_service · mail_service · audit_service                │
│                                                                  │
│  Models (SQLAlchemy ORM) + validation (WTForms)                  │
└───────────────────────────────┬──────────────────────────────────┘
                                │ SQLAlchemy / transaction
┌───────────────────────────────▼──────────────────────────────────┐
│        SQLite (dev/test, WAL mode)  |  MySQL 8 (production)      │
│  users · patients · departments · doctors · schedules · slots    │
│  appointments · notifications · audit_logs · settings            │
│  HARD GUARANTEE: UNIQUE(doctor_id, slot_date, start_time)        │
└──────────────────────────────────────────────────────────────────┘
                                │ SMTP
                     ┌──────────▼──────────┐
                     │  Email (Flask-Mail) │
                     │  dev: console/file  │
                     └─────────────────────┘
```

### 6.2 Layer responsibilities

| Layer | Responsibility | Must NOT |
|---|---|---|
| Blueprint / route | Parse request, call service, render/JSON response, flash messages | Contain SQL or booking rules |
| Form / validator | Input shape, email format, password strength, date bounds | Touch the DB directly |
| Service | Business rules, transactions, slot locking, waiting-time math | Render HTML |
| Model | Tables, relationships, constraints, small helper properties | Send email or read request |
| Template / JS | Presentation, interactivity, progressive enhancement | Enforce security or uniqueness |

### 6.3 Booking request flow

```
Patient selects slot
        │
        ▼
POST /patient/book  (CSRF token + slot_id)
        │
        ├─ 1. Auth check: role == patient
        ├─ 2. Validate slot belongs to selected doctor & date; date in future
        ├─ 3. BEGIN IMMEDIATE transaction (SQLite) / SELECT ... FOR UPDATE (MySQL)
        ├─ 4. Atomic claim:
        │       UPDATE slots
        │       SET status='BOOKED'
        │       WHERE id=:slot_id AND status='AVAILABLE'
        │       → rowcount == 1 ? proceed : ROLLBACK → 409 "Slot already booked"
        ├─ 5. Re-check patient does not already hold a booking for this doctor+date
        ├─ 6. INSERT appointment (booking_id, slot_id UNIQUE, status=CONFIRMED)
        ├─ 7. COMMIT
        ├─ 8. Compute queue position + estimated wait
        ├─ 9. Send confirmation email (after commit; failure does not roll back booking)
        └─ 10. Redirect to confirmation page
```

### 6.4 Why the design is safe

Three independent guards, so a bug in one does not cause a double booking:

1. **Database unique constraint** on `(doctor_id, slot_date, start_time)` — impossible to have two slot rows for the same doctor/date/time.
2. **Unique `appointments.slot_id`** — one appointment per slot row.
3. **Conditional update with rowcount check** inside a transaction — only one concurrent request can flip `AVAILABLE → BOOKED`.

The UI disables booked slots as a *convenience*, not as the guarantee.

---

## 7. Technology Stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Course requirement, clean syntax |
| Web framework | Flask 3 (app factory + blueprints) | Lightweight, teachable, modular |
| ORM | Flask-SQLAlchemy 3 | Relationships + transactions + portability |
| Migrations | Flask-Migrate (Alembic) | Schema evolution without dropping data |
| Auth | Flask-Login + Werkzeug `generate_password_hash` (scrypt) | Session management, secure hashing |
| Forms/CSRF | Flask-WTF | Server-side validation + CSRF tokens |
| Email | Flask-Mail | Confirmation & cancellation emails |
| Rate limiting | Flask-Limiter | Login/registration abuse protection |
| DB | SQLite (dev/test), MySQL 8 (prod) | Zero-setup dev; production realism |
| Frontend | Jinja2 + Bootstrap 5 + custom CSS | Fast, responsive, professional |
| JS | Vanilla ES6 modules | Requirement; no build step |
| Charts | Chart.js 4 | Admin analytics |
| Icons | Font Awesome 6 | Medical icons |
| Images | Unsplash / Pexels hospital & doctor photos, or local `static/img` | Free-to-use visuals |
| Testing | Pytest + pytest-cov + Flask test client | Required test suite |
| Tooling | python-dotenv, ruff/black (optional), gunicorn (prod) | Clean workflow |

### 7.1 Python dependencies (`requirements.txt`)

```text
Flask==3.1.*
Flask-SQLAlchemy==3.1.*
Flask-Login==0.6.*
Flask-WTF==1.2.*
Flask-Mail==0.10.*
Flask-Migrate==4.0.*
Flask-Limiter==3.8.*
email-validator==2.2.*
python-dotenv==1.0.*
PyMySQL==1.1.*          # production MySQL only
pytest==8.*
pytest-cov==5.*
```

---

## 8. Core Design: Slot Locking, Booking Rules, Waiting Time

### 8.1 Slot generation model

- A doctor has one or more **weekly schedule templates**: `weekday`, `start_time`, `end_time`, `slot_duration_minutes`, `max_patients`.
- Slots are generated for the next **30 days** by a service (on demand or nightly job) skipping:
  - dates in the past,
  - doctor leave / blocked dates,
  - hospital holidays,
  - slots already started (same-day cutoff).
- Generation is **idempotent**: `INSERT ... ON CONFLICT DO NOTHING` (SQLite/Postgres) or `INSERT IGNORE` (MySQL) on the unique key.
- Each slot row: `doctor_id`, `slot_date`, `start_time`, `end_time`, `status`, `fee`, optional `appointment_id`.

### 8.2 Slot state machine

```
           generated
              │
              ▼
        ┌───────────┐   patient books    ┌──────────┐
        │ AVAILABLE │ ─────────────────► │  BOOKED  │
        └───────────┘   (atomic claim)   └────┬─────┘
              ▲                              │
              │ appointment cancelled        │ appointment completed
              │ (allowed by rules)           ▼
              │                         ┌───────────┐
              └──────────────────────── │ COMPLETED │
                                        └───────────┘

  BLOCKED  ← doctor leave / admin block (never bookable)
  CLOSED   ← past slot / same-day cutoff (never bookable)
  HELD     ← optional 5-minute checkout hold (stretch goal, not MVP)
```

**MVP decision:** no `HELD` state. Claiming is instant on submit. A short hold can be added later with a `hold_expires_at` column.

### 8.3 Cancellation rules (configurable in `settings`)

| Rule | Default | Enforcement |
|---|---|---|
| Cutoff before appointment | 2 hours | Reject cancellation if `now > appointment_datetime - 2h` |
| Maximum active bookings per patient per doctor/day | 1 | Checked in booking service |
| Maximum cancellations per 30 days | 3 | Counted from appointments |
| Cancellation reason | Required | WTForms validator |
| Slot re-opening | If slot datetime is still in the future → `AVAILABLE` | In same transaction as cancellation |
| Admin override | Always allowed, reason logged | Audit log |
| Doctor leave cancellation | Admin cancels; slot becomes `BLOCKED`, not `AVAILABLE` | Bulk action |

**Important:** a cancelled slot only becomes available again if it is in the future and the doctor's schedule still permits it. Past slots become `CLOSED`.

### 8.4 Waiting-time and queue-position algorithm

Inputs:
- `avg_consult_minutes` per doctor (default 15, editable by admin).
- `delay_minutes` per doctor per day (optional manual "running late" value; default 0).
- Appointment statuses: `CONFIRMED`, `CHECKED_IN`, `IN_CONSULTATION`, `COMPLETED`, `CANCELLED`, `NO_SHOW`.
- Slot times.

For a **new booking** at slot time `T` on date `D` for doctor `X`:

```
patients_ahead = count of non-cancelled appointments
                 for doctor X, date D
                 where start_time < T
                 and status in (CONFIRMED, CHECKED_IN, IN_CONSULTATION)

queue_position      = patients_ahead + 1
estimated_wait_min  = patients_ahead * avg_consult_minutes + delay_minutes
estimated_start     = T + delay_minutes          (displayed as "approx. 1:15 PM")
```

For the **live queue** (patient already booked, on appointment day):

```
remaining_ahead = count of appointments for doctor X, date D
                  where status in (CHECKED_IN, IN_CONSULTATION)
                  OR (status = CONFIRMED and start_time <= now)

estimated_wait_min = remaining_ahead * avg_consult_minutes + delay_minutes
```

For a **completed consultation**, optionally record `actual_duration_min` and update the doctor's rolling average:

```
avg_consult = 0.8 * avg_consult + 0.2 * actual_duration
```

Display rules:
- `< 0` → clamp to 0.
- Show "~15 min", "~1 hr 5 min".
- Always label as **estimate**, with tooltip "Based on N patients ahead × average consultation time".
- If queue is empty → "No wait — you're next".

### 8.5 Concurrent booking: what happens when two patients press Book

| Time | Patient A | Patient B | Database |
|---|---|---|---|
| t0 | GET slots → 1:00 PM available | GET slots → 1:00 PM available | slot status AVAILABLE |
| t1 | POST book slot 42 | — | — |
| t2 | — | POST book slot 42 | — |
| t3 | begins `BEGIN IMMEDIATE`, claims slot 42 | waiting for write lock | `UPDATE … WHERE status='AVAILABLE'` → 1 row |
| t4 | inserts appointment, commits | proceeds after lock release | slot 42 BOOKED |
| t5 | 302 → confirmation | `UPDATE … WHERE status='AVAILABLE'` → **0 rows** | rollback |
| t6 | sees booking ID | 409 → "This slot was just booked. Please pick another." + refreshed slots | — |

**SQLite setup:** enable WAL (`PRAGMA journal_mode=WAL`), set `timeout=15`, use `BEGIN IMMEDIATE` for the booking transaction to avoid `database is locked` surprises.
**MySQL setup:** `SELECT id FROM slots WHERE id=? AND status='AVAILABLE' FOR UPDATE`, then update, inside `InnoDB` transaction.
**Test proof:** spawn two threads with two test clients hitting the same slot; assert exactly one 302/200 booking and one 409, and exactly one appointment row.

### 8.6 Booking ID format

`MQ-YYYYMMDD-NNNN` — e.g. `MQ-20261106-0007`, generated from a per-day sequence table or by counting that day's appointments inside the transaction and retrying on unique violation. Stored unique. This is the ID shown to patients and used by staff.

### 8.7 Rescheduling (optional but recommended)

- Allowed once per appointment, before cutoff.
- Atomic operation: claim new slot → release old slot → update appointment → all in one transaction.
- If the new slot claim fails, the old booking remains untouched.

---

## 9. Database Design

### 9.1 Entity-relationship overview

```
users (1) ──── (0..1) patient_profiles
  │
  │ 1
  │
  ├──── (0..1) doctors ──── (1) departments
  │                │
  │                ├──── (1..*) doctor_schedules
  │                ├──── (1..*) schedule_exceptions
  │                ├──── (1..*) slots
  │                └──── (1..*) appointments
  │
  ├──── (1..*) appointments (as patient)
  ├──── (1..*) notifications
  └──── (1..*) audit_logs (as actor)

slots (1) ──── (0..1) appointments     [appointments.slot_id UNIQUE]
```

### 9.2 Table: `users`

| Column | Type | Constraints / Notes |
|---|---|---|
| id | INTEGER / BIGINT | PK, autoincrement |
| role | VARCHAR(10) | NOT NULL, `patient` / `doctor` / `admin` |
| full_name | VARCHAR(120) | NOT NULL |
| email | VARCHAR(255) | NOT NULL, **UNIQUE**, stored lowercase |
| password_hash | VARCHAR(255) | NOT NULL (scrypt via Werkzeug) |
| phone | VARCHAR(20) | NULL |
| is_active | BOOLEAN | NOT NULL DEFAULT 1 |
| last_login_at | DATETIME | NULL |
| created_at | DATETIME | NOT NULL DEFAULT now |
| updated_at | DATETIME | NOT NULL DEFAULT now |

Indexes: `UNIQUE(email)`, `INDEX(role, is_active)`.

### 9.3 Table: `patient_profiles`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| user_id | INTEGER | **UNIQUE**, FK `users.id` ON DELETE CASCADE |
| date_of_birth | DATE | NULL |
| gender | VARCHAR(15) | NULL |
| blood_group | VARCHAR(5) | NULL |
| address | VARCHAR(255) | NULL |
| emergency_contact | VARCHAR(20) | NULL |
| created_at | DATETIME | NOT NULL |

### 9.4 Table: `departments`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| name | VARCHAR(100) | NOT NULL, **UNIQUE** |
| slug | VARCHAR(120) | NOT NULL, **UNIQUE** |
| description | TEXT | NULL |
| icon | VARCHAR(50) | Font Awesome class, e.g. `fa-heart-pulse` |
| image_url | VARCHAR(255) | NULL |
| floor | VARCHAR(30) | NULL |
| phone_ext | VARCHAR(10) | NULL |
| is_active | BOOLEAN | NOT NULL DEFAULT 1 |
| created_at | DATETIME | NOT NULL |

### 9.5 Table: `doctors`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| user_id | INTEGER | **UNIQUE**, FK `users.id` ON DELETE CASCADE |
| department_id | INTEGER | NOT NULL, FK `departments.id` ON DELETE RESTRICT |
| specialization | VARCHAR(120) | NOT NULL |
| qualification | VARCHAR(150) | NULL |
| experience_years | INTEGER | NOT NULL DEFAULT 0 |
| consultation_fee | NUMERIC(10,2) | NOT NULL DEFAULT 0 |
| room_no | VARCHAR(20) | NULL |
| bio | TEXT | NULL |
| photo_url | VARCHAR(255) | NULL |
| avg_consult_minutes | INTEGER | NOT NULL DEFAULT 15, CHECK 5–120 |
| is_active | BOOLEAN | NOT NULL DEFAULT 1 |
| created_at | DATETIME | NOT NULL |

Index: `INDEX(department_id, is_active)`.

### 9.6 Table: `doctor_schedules`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| doctor_id | INTEGER | NOT NULL, FK `doctors.id` ON DELETE CASCADE |
| weekday | SMALLINT | NOT NULL, 0 = Monday … 6 = Sunday |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| slot_duration_minutes | SMALLINT | NOT NULL DEFAULT 20 |
| max_patients | SMALLINT | NULL (NULL = derived from window ÷ duration) |
| is_active | BOOLEAN | NOT NULL DEFAULT 1 |

Constraints: `UNIQUE(doctor_id, weekday, start_time)`, `CHECK(end_time > start_time)`.

### 9.7 Table: `schedule_exceptions`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| doctor_id | INTEGER | NOT NULL, FK `doctors.id` ON DELETE CASCADE |
| exception_date | DATE | NOT NULL |
| is_closed | BOOLEAN | NOT NULL DEFAULT 1 (full-day leave) |
| start_time | TIME | NULL (partial-day block) |
| end_time | TIME | NULL |
| reason | VARCHAR(200) | NULL |
| created_by | INTEGER | FK `users.id` |
| created_at | DATETIME | NOT NULL |

Index: `INDEX(doctor_id, exception_date)`.

### 9.8 Table: `slots` (the heart of the system)

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| doctor_id | INTEGER | NOT NULL, FK `doctors.id` ON DELETE CASCADE |
| slot_date | DATE | NOT NULL |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| status | VARCHAR(12) | NOT NULL DEFAULT `AVAILABLE`; CHECK in (`AVAILABLE`,`BOOKED`,`BLOCKED`,`CLOSED`) |
| fee | NUMERIC(10,2) | NULL (snapshot of doctor fee) |
| created_at | DATETIME | NOT NULL |

**Critical constraints**
- `UNIQUE(doctor_id, slot_date, start_time)` ← one physical slot per doctor/date/time.
- `INDEX(slot_date, status)` for fast day views.
- `INDEX(doctor_id, slot_date, status)` for queue queries.
- `CHECK(end_time > start_time)`.

### 9.9 Table: `appointments`

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK |
| booking_id | VARCHAR(24) | NOT NULL, **UNIQUE** |
| patient_id | INTEGER | NOT NULL, FK `users.id` ON DELETE RESTRICT |
| doctor_id | INTEGER | NOT NULL, FK `doctors.id` ON DELETE RESTRICT |
| slot_id | INTEGER | NOT NULL, **UNIQUE**, FK `slots.id` ON DELETE RESTRICT |
| appointment_date | DATE | NOT NULL |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| status | VARCHAR(15) | NOT NULL DEFAULT `CONFIRMED`; CHECK in (`CONFIRMED`,`CHECKED_IN`,`IN_CONSULTATION`,`COMPLETED`,`CANCELLED`,`NO_SHOW`) |
| reason_for_visit | VARCHAR(300) | NULL |
| fee | NUMERIC(10,2) | NOT NULL DEFAULT 0 |
| queue_position | SMALLINT | NULL (snapshot at booking) |
| estimated_wait_minutes | SMALLINT | NULL |
| checked_in_at | DATETIME | NULL |
| completed_at | DATETIME | NULL |
| cancelled_at | DATETIME | NULL |
| cancelled_by | INTEGER | FK `users.id`, NULL |
| cancel_reason | VARCHAR(300) | NULL |
| created_at | DATETIME | NOT NULL |
| updated_at | DATETIME | NOT NULL |

**Constraints / indexes**
- `UNIQUE(booking_id)`, `UNIQUE(slot_id)`.
- `INDEX(patient_id, status)`, `INDEX(doctor_id, appointment_date, start_time)`, `INDEX(appointment_date, status)`.
- Application rule: a patient cannot hold more than one active appointment for the same doctor on the same date.
- Delete policy: never hard-delete appointments; status changes only (audit trail).

### 9.10 Table: `notifications`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| user_id | INTEGER | FK `users.id` |
| appointment_id | INTEGER | FK `appointments.id`, NULL |
| channel | VARCHAR(10) | `email` / `inapp` |
| type | VARCHAR(30) | `booking_confirmation`, `cancellation`, `reminder` |
| recipient_email | VARCHAR(255) | snapshot |
| subject | VARCHAR(200) | |
| body | TEXT | rendered HTML/text |
| status | VARCHAR(10) | `pending` / `sent` / `failed` |
| error_message | VARCHAR(500) | NULL |
| sent_at | DATETIME | NULL |
| created_at | DATETIME | NOT NULL |

### 9.11 Table: `audit_logs`

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| actor_user_id | INTEGER | FK `users.id`, NULL for system |
| action | VARCHAR(50) | `login`, `booking_created`, `booking_cancelled`, `doctor_created`, … |
| entity_type | VARCHAR(30) | `appointment`, `slot`, `doctor`, `department`, `user` |
| entity_id | INTEGER | NULL |
| details | TEXT | JSON string (old/new values, reason) |
| ip_address | VARCHAR(45) | |
| created_at | DATETIME | NOT NULL |

Index: `INDEX(actor_user_id, created_at)`, `INDEX(entity_type, entity_id)`.

### 9.12 Table: `settings`

| key (PK) | value | Default |
|---|---|---|
| hospital_name | string | MediQueue General Hospital |
| cancellation_cutoff_hours | int | 2 |
| max_cancellations_per_30_days | int | 3 |
| slot_generation_days | int | 30 |
| booking_open_days | int | 30 |
| reminder_hours_before | int | 24 |
| support_email | string | support@mediqueue.local |

### 9.13 Key SQL (SQLite dialect)

```sql
CREATE TABLE slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id   INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    slot_date   DATE    NOT NULL,
    start_time  TIME    NOT NULL,
    end_time    TIME    NOT NULL,
    status      VARCHAR(12) NOT NULL DEFAULT 'AVAILABLE'
                CHECK (status IN ('AVAILABLE','BOOKED','BLOCKED','CLOSED')),
    fee         NUMERIC(10,2),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_doctor_slot UNIQUE (doctor_id, slot_date, start_time),
    CHECK (end_time > start_time)
);

CREATE TABLE appointments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id     VARCHAR(24) NOT NULL UNIQUE,
    patient_id     INTEGER NOT NULL REFERENCES users(id),
    doctor_id      INTEGER NOT NULL REFERENCES doctors(id),
    slot_id        INTEGER NOT NULL UNIQUE REFERENCES slots(id),
    appointment_date DATE NOT NULL,
    start_time     TIME NOT NULL,
    end_time       TIME NOT NULL,
    status         VARCHAR(15) NOT NULL DEFAULT 'CONFIRMED'
                   CHECK (status IN ('CONFIRMED','CHECKED_IN','IN_CONSULTATION',
                                     'COMPLETED','CANCELLED','NO_SHOW')),
    reason_for_visit VARCHAR(300),
    fee            NUMERIC(10,2) NOT NULL DEFAULT 0,
    queue_position SMALLINT,
    estimated_wait_minutes SMALLINT,
    checked_in_at  DATETIME,
    completed_at   DATETIME,
    cancelled_at   DATETIME,
    cancelled_by   INTEGER REFERENCES users(id),
    cancel_reason  VARCHAR(300),
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_slots_day      ON slots (slot_date, status);
CREATE INDEX idx_slots_doctor   ON slots (doctor_id, slot_date, status);
CREATE INDEX idx_appt_patient   ON appointments (patient_id, status);
CREATE INDEX idx_appt_doctor    ON appointments (doctor_id, appointment_date, start_time);
```

### 9.14 Why `slots` is separate from `appointments`

- A slot exists even when nobody has booked it. If appointments owned the time grid, you could not display "available" slots without inventing rows at query time.
- The unique constraint lives on the smallest, most stable table.
- Blocking a doctor's leave is a slot update, not a fake appointment.
- Historical appointments keep their slot snapshot, so schedule edits later don't rewrite history.

---

## 10. Project Folder Structure

```
smart-hospital/
│
├─ run.py                        # entry point: create_app().run()
├─ config.py                     # Base / Dev / Test / Prod config classes
├─ requirements.txt
├─ requirements-dev.txt
├─ .env.example                  # SECRET_KEY, DATABASE_URL, MAIL_* ...
├─ .gitignore
├─ README.md
├─ HOSPITAL_PROJECT_PLAN.md
│
├─ app/
│  ├─ __init__.py                # application factory, blueprint registration, error handlers
│  ├─ extensions.py              # db, login_manager, mail, csrf, limiter, migrate
│  ├─ constants.py               # enums: Roles, AppointmentStatus, SlotStatus
│  ├─ forms.py                   # shared WTForms (or split per blueprint)
│  │
│  ├─ blueprints/
│  │  ├─ __init__.py
│  │  ├─ auth.py                 # /register /login /logout /forgot /reset
│  │  ├─ main.py                 # / /about /contact (public)
│  │  ├─ patient.py              # /patient/dashboard /appointments /book /cancel
│  │  ├─ doctor.py               # /doctor/dashboard /schedule /queue
│  │  ├─ admin.py                # /admin/* CRUD + analytics
│  │  ├─ api.py                  # /api/slots /api/wait-time /api/admin/stats
│  │  └─ errors.py               # 400/403/404/409/429/500 handlers
│  │
│  ├─ models/
│  │  ├─ __init__.py             # imports all models for Alembic
│  │  ├─ user.py                 # User, PatientProfile
│  │  ├─ department.py
│  │  ├─ doctor.py               # Doctor, DoctorSchedule, ScheduleException
│  │  ├─ slot.py
│  │  ├─ appointment.py
│  │  ├─ notification.py
│  │  ├─ audit_log.py
│  │  └─ setting.py
│  │
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ schedule_service.py     # generate slots, block leave, next available date
│  │  ├─ slot_service.py         # list slots for date, atomic claim/release
│  │  ├─ booking_service.py      # create/cancel/reschedule, booking IDs, rules
│  │  ├─ waiting_service.py      # queue position + estimated waiting time
│  │  ├─ mail_service.py         # templates, send, notification logging
│  │  ├─ audit_service.py        # write audit entries
│  │  └─ stats_service.py        # admin dashboard aggregates
│  │
│  ├─ utils/
│  │  ├─ decorators.py           # @role_required, @active_user_required
│  │  ├─ validators.py           # date/time, phone, slot-in-future
│  │  ├─ time_utils.py           # local timezone handling, humanize minutes
│  │  └─ security.py             # safe redirect, password policy
│  │
│  ├─ templates/
│  │  ├─ base.html               # navbar, sidebar, flash toasts, footer
│  │  ├─ macros/
│  │  │  ├─ forms.html           # render_field, errors
│  │  │  ├─ cards.html           # stat_card, doctor_card, dept_card
│  │  │  └─ badges.html          # status_badge
│  │  ├─ main/
│  │  │  ├─ index.html           # landing page
│  │  │  ├─ about.html
│  │  │  └─ contact.html
│  │  ├─ auth/
│  │  │  ├─ login.html
│  │  │  ├─ register.html
│  │  │  ├─ forgot.html
│  │  │  └─ reset.html
│  │  ├─ patient/
│  │  │  ├─ dashboard.html
│  │  │  ├─ departments.html
│  │  │  ├─ doctors.html
│  │  │  ├─ doctor_profile.html
│  │  │  ├─ book.html            # wizard: date + slots
│  │  │  ├─ confirmation.html
│  │  │  ├─ appointments.html
│  │  │  └─ appointment_detail.html
│  │  ├─ doctor/
│  │  │  ├─ dashboard.html
│  │  │  ├─ schedule.html
│  │  │  └─ queue.html
│  │  ├─ admin/
│  │  │  ├─ dashboard.html
│  │  │  ├─ departments.html
│  │  │  ├─ department_form.html
│  │  │  ├─ doctors.html
│  │  │  ├─ doctor_form.html
│  │  │  ├─ schedules.html
│  │  │  ├─ patients.html
│  │  │  └─ appointments.html
│  │  ├─ email/
│  │  │  ├─ booking_confirmation.html
│  │  │  ├─ cancellation.html
│  │  │  └─ reminder.html
│  │  └─ errors/
│  │     ├─ 403.html
│  │     ├─ 404.html
│  │     ├─ 409.html
│  │     └─ 500.html
│  │
│  └─ static/
│     ├─ css/
│     │  ├─ theme.css            # design tokens, typography, utilities
│     │  ├─ components.css       # cards, buttons, badges, forms, tables
│     │  ├─ pages.css            # landing, auth, booking, dashboards
│     │  └─ responsive.css       # breakpoints and mobile sidebar
│     ├─ js/
│     │  ├─ app.js               # navbar, sidebar, toasts, tooltips
│     │  ├─ booking.js           # wizard, date picker, slot fetch/render
│     │  ├─ slots.js             # slot polling + conflict handling
│     │  ├─ dashboard.js         # patient/doctor dashboard widgets
│     │  ├─ charts.js            # Chart.js admin analytics
│     │  └─ validation.js        # client-side form hints (server is authoritative)
│     ├─ img/
│     │  ├─ hero-hospital.jpg
│     │  ├─ departments/*.jpg
│     │  ├─ doctors/*.jpg
│     │  └─ logo.svg
│     └─ uploads/doctors/        # admin-uploaded photos (dev only)
│
├─ migrations/                   # Flask-Migrate / Alembic
│  ├─ env.py
│  └─ versions/
│
├─ tests/
│  ├─ conftest.py                # app, db, client, factories, auth helpers
│  ├─ factories.py               # make_user, make_doctor, make_slot, ...
│  ├─ test_auth.py
│  ├─ test_registration.py
│  ├─ test_departments.py
│  ├─ test_doctors.py
│  ├─ test_slots.py
│  ├─ test_booking.py
│  ├─ test_concurrency.py
│  ├─ test_cancellation.py
│  ├─ test_confirmation.py
│  ├─ test_waiting_time.py
│  ├─ test_doctor_schedule.py
│  ├─ test_admin.py
│  ├─ test_security.py
│  ├─ test_responsive.py         # static template/responsive contract checks
│  └─ test_errors.py
│
├─ instance/
│  └─ hospital.db                # SQLite dev database (git-ignored)
│
├─ seed.py                       # demo departments, doctors, schedules, slots
├─ wsgi.py                       # production entry point
└─ docs/
   ├─ ERD.png
   ├─ screenshots/
   └─ test-report.md
```

---

## 11. Routes and API Contract

### 11.1 Page routes

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/` | public | Landing page |
| GET/POST | `/register` | public | Patient registration |
| GET/POST | `/login` | public | Login (all roles → role dashboard) |
| POST | `/logout` | authenticated | Logout (POST + CSRF) |
| GET | `/patient/dashboard` | patient | Dashboard cards |
| GET | `/patient/departments` | patient | Department grid |
| GET | `/patient/departments/<id>/doctors` | patient | Doctors in department |
| GET | `/patient/doctors/<id>` | patient | Doctor profile + schedule |
| GET | `/patient/book/<doctor_id>` | patient | Booking wizard (date/slots) |
| POST | `/patient/book/<doctor_id>` | patient | Create booking |
| GET | `/patient/appointments` | patient | History + filters |
| GET | `/patient/appointments/<booking_id>` | patient (owner) | Detail |
| POST | `/patient/appointments/<booking_id>/cancel` | patient (owner) | Cancel |
| GET | `/doctor/dashboard` | doctor | Today at a glance |
| GET | `/doctor/schedule` | doctor | Daily schedule (`?date=`) |
| POST | `/doctor/appointments/<id>/checkin` | doctor (own) | Check in |
| POST | `/doctor/appointments/<id>/complete` | doctor (own) | Complete |
| POST | `/doctor/appointments/<id>/no-show` | doctor (own) | Mark no-show |
| GET | `/admin/dashboard` | admin | KPIs + charts |
| GET/POST | `/admin/departments` `/admin/departments/new` `/admin/departments/<id>/edit` | admin | Department CRUD |
| GET/POST | `/admin/doctors...` | admin | Doctor CRUD + account creation |
| GET/POST | `/admin/doctors/<id>/schedules` | admin | Weekly schedule editor |
| POST | `/admin/doctors/<id>/leave` | admin | Block date(s) |
| GET | `/admin/patients` | admin | Patient list/search |
| POST | `/admin/patients/<id>/toggle` | admin | Activate/deactivate |
| GET | `/admin/appointments` | admin | Filter all appointments |
| POST | `/admin/appointments/<id>/cancel` | admin | Override cancel |

### 11.2 JSON API (used by JavaScript)

#### `GET /api/doctors/<int:doctor_id>/slots?date=YYYY-MM-DD`

```json
{
  "doctor_id": 4,
  "date": "2026-11-10",
  "is_working_day": true,
  "slots": [
    {"id": 101, "start": "13:00", "end": "13:20", "status": "BOOKED", "available": false},
    {"id": 102, "start": "13:20", "end": "13:40", "status": "AVAILABLE", "available": true}
  ],
  "summary": {"total": 18, "available": 11, "booked": 7},
  "server_time": "2026-11-06T10:42:00"
}
```

#### `GET /api/doctors/<int:doctor_id>/next-available?from=YYYY-MM-DD`

```json
{"date": "2026-11-08", "start": "09:00", "slot_id": 88, "available": true}
```

#### `GET /api/appointments/<booking_id>/wait`

```json
{
  "booking_id": "MQ-20261110-0004",
  "status": "CONFIRMED",
  "queue_position": 3,
  "patients_ahead": 2,
  "avg_consult_minutes": 15,
  "delay_minutes": 5,
  "estimated_wait_minutes": 35,
  "estimated_start": "13:45",
  "label": "~35 min",
  "updated_at": "2026-11-10T12:58:00"
}
```

#### `GET /admin/api/stats?range=7d`

```json
{
  "kpis": {
    "total_patients": 128, "total_doctors": 12,
    "appointments_today": 34, "available_slots_today": 58,
    "booked_slots_today": 34, "cancellation_rate": 6.4
  },
  "bookings_per_day": {"labels": ["Nov 01", "..."], "values": [12, 18, 15, 21, 19, 27, 34]},
  "department_load": {"labels": ["Cardiology", "..."], "values": [22, 18, 14]},
  "peak_hours": {"labels": ["09:00", "10:00", "..."], "values": [4, 9, 7, 2]}
}
```

#### Error response shape (API)

```json
{"ok": false, "error": {"code": "SLOT_TAKEN", "message": "This slot was just booked. Please choose another available slot."}}
```

| HTTP | Code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing/invalid fields, past date |
| 401 | `AUTH_REQUIRED` | Not logged in |
| 403 | `FORBIDDEN` | Wrong role / not owner |
| 404 | `NOT_FOUND` | Unknown doctor/booking |
| 409 | `SLOT_TAKEN` | Atomic claim failed (concurrent booking) |
| 409 | `ALREADY_BOOKED` | Patient already has a booking for this doctor/date |
| 409 | `CANCEL_CUTOFF_PASSED` | Cancellation too late |
| 429 | `RATE_LIMITED` | Login/registration abuse |

---

## 12. UI / UX Design Plan

### 12.1 Design direction

**Feeling:** calm, trustworthy, clinical but warm. Lots of white space, soft blue, fresh green accents, human photography, round cards, gentle motion. Avoid clip-art, avoid dark/neon "tech" looks.

### 12.2 Design tokens

| Token | Value | Usage |
|---|---|---|
| `--blue-700` | `#0B4F9E` | Headings, nav active |
| `--blue-600` | `#0D6EFD` | Primary buttons, links |
| `--blue-100` | `#E7F1FF` | Card tints, hover |
| `--green-600` | `#16A34A` | Available slots, success |
| `--green-100` | `#E6F9EE` | Success banners |
| `--red-500` | `#DC3545` | Errors, booked, cancel |
| `--amber-500` | `#F59E0B` | Warnings, few slots |
| `--ink-900` | `#0F172A` | Body headings |
| `--ink-600` | `#475569` | Body text |
| `--surface` | `#FFFFFF` | Cards |
| `--bg` | `#F5F9FF` | Page background |
| `--radius-sm/md/lg` | `10px / 16px / 24px` | Cards, inputs, hero |
| `--shadow-card` | `0 10px 30px rgba(15,23,42,.08)` | Cards |
| `--shadow-hover` | `0 18px 40px rgba(13,110,253,.18)` | Hover lift |
| Font | `Poppins` headings, `Inter` body | Google Fonts |
| Spacing | 4px scale (`4, 8, 12, 16, 24, 32, 48, 64`) | Consistent rhythm |

### 12.3 Page-by-page design

| Page | Layout & key elements |
|---|---|
| **Landing** | Sticky translucent navbar; split hero (headline + "Book appointment" + "Find a doctor" CTAs + hospital photo with floating stat cards "12 departments / 40+ doctors / 5 min avg wait"); trust strip (accreditations); "How it works" 3-step cards with icons; department grid; featured doctors carousel; live queue preview; testimonials; footer with emergency number. |
| **Login** | Split screen: left = form on white card, right = hospital image with soft blue overlay + quote. Show/hide password, remember me, forgot link. |
| **Register** | Same split; inline field validation; password strength meter; terms checkbox. |
| **Patient dashboard** | Sidebar (desktop) / bottom nav (mobile); greeting + next appointment hero card with countdown; 4 stat cards; "Upcoming appointments" table; quick actions; waiting-time widget. |
| **Departments** | Search box; responsive grid of 8 department cards with icon, name, doctor count, "View doctors" hover lift. |
| **Doctors** | Filter chips (department, availability today); doctor cards with photo, specialization, experience, fee, star rating; "View profile / Book". |
| **Doctor profile** | Header card (photo, name, dept, qualification, experience, fee, room); tabs: About / Weekly schedule / Reviews (optional); sticky "Book appointment" panel. |
| **Booking wizard** | Stepper: 1 Department ✓ → 2 Doctor ✓ → 3 Date & Time → 4 Confirm. Horizontal scrollable date pills for 14 days (disabled past/leave). Slot grid: green available, grey booked with lock icon, selected blue. Legend. Right-side summary card (doctor, fee, chosen slot). Confirm modal. |
| **Confirmation** | Big green check animation; booking ID in a copyable chip; detail grid; queue position + estimated wait; "Add to calendar" (.ics, optional); email-sent notice; buttons to dashboard / book another. |
| **Appointments** | Tabs: Upcoming / Past / Cancelled; cards or table; status badges; cancel button opens modal with reason + rule warning; empty states with illustration. |
| **Doctor dashboard** | Today's date, KPI row (patients today, completed, waiting, avg consult); next patient hero; queue table with action buttons; live waiting-time. |
| **Doctor schedule** | Date picker + timeline list grouped by morning/afternoon; each row: time, patient, booking ID, status, actions. Print-friendly. |
| **Admin dashboard** | KPI cards with sparkline/icons; Chart.js line (bookings 7/30 days), doughnut (department load), bar (slot utilization), bar (peak hours); today's appointments table; quick action tiles. |
| **Admin CRUD** | Data tables with search, filters, pagination; slide-over or modal forms; delete = deactivate; confirmation dialogs. |
| **Errors** | Friendly illustration + message + "Go home" / "Back" buttons. 409 page explains slot conflict. |

### 12.4 Component library (CSS classes)

- Buttons: `.btn-primary`, `.btn-outline`, `.btn-success`, `.btn-danger`, `.btn-ghost`, sizes `sm/lg`, loading state `.is-loading` with spinner.
- Cards: `.card`, `.stat-card`, `.doctor-card`, `.dept-card`, `.slot-card`.
- Forms: `.form-control`, `.form-label`, `.invalid-feedback`, `.input-icon`.
- Badges: `.badge-available`, `.badge-booked`, `.badge-cancelled`, `.badge-completed`.
- Feedback: toast container top-right, flash messages auto-dismiss, skeleton loaders.
- Navigation: `.navbar`, `.sidebar`, `.sidebar-link.active`, `.mobile-bottom-nav`.

### 12.5 Slot visual language

| State | Background | Border | Text | Icon |
|---|---|---|---|---|
| Available | `#E6F9EE` | `#16A34A` | `#14532D` | none / check |
| Selected | `#0D6EFD` | `#0B4F9E` | white | check |
| Booked | `#F1F5F9` | `#CBD5E1` | `#94A3B8` | lock |
| Blocked / leave | `#FEF2F2` | `#FCA5A5` | `#B91C1C` | ban |
| Past / closed | `#F8FAFC` | `#E2E8F0` | `#CBD5E1` | clock |

Rules: booked slots are rendered as `<button disabled>` with `aria-disabled="true"` and a tooltip "Already booked". A legend is always visible above the grid.

### 12.6 Animations and interaction

- Page load: fade-up on cards with 60 ms stagger (CSS `@keyframes`, `animation-delay` via inline style or `nth-child`).
- Hover: cards lift `translateY(-4px)` + shadow; buttons darken; doctor photo `scale(1.04)`.
- Slot click: scale pulse, then summary updates.
- Booking submit: button spinner + disabled; skeleton on slot grid while loading.
- Success: checkmark draw animation (SVG stroke), confetti optional (respect `prefers-reduced-motion`).
- Toasts: slide in from right, auto-hide 4 s, close button.
- Respect `@media (prefers-reduced-motion: reduce)` → disable transforms/animations.

### 12.7 Responsive behaviour

| Breakpoint | Layout |
|---|---|
| `< 576px` (mobile) | Single column; navbar collapses to hamburger; patient nav = bottom bar; slot grid 3 columns; tables become stacked cards; charts height 220 px. |
| `576–991px` (tablet) | 2-column grids; sidebar off-canvas; slot grid 4 columns; forms full width. |
| `≥ 992px` (desktop) | Fixed 260 px sidebar for dashboards; 3–4 column grids; slot grid 5–6 columns; sticky booking summary. |
| `≥ 1400px` | Max content width 1320 px, larger hero type. |

Responsive checks in tests: every template extends `base.html`, includes viewport meta, uses `.container`/grid classes, no fixed pixel widths on main wrappers, images have `srcset`/`loading="lazy"` where relevant.

### 12.8 Accessibility

- Semantic landmarks (`header`, `nav`, `main`, `footer`), one `h1` per page.
- Colour contrast ≥ 4.5:1 for text; slot state also indicated by icon/label, not colour alone.
- All inputs have labels; errors linked with `aria-describedby`; focus ring visible.
- Keyboard: modals trap focus, Esc closes, slot buttons reachable by Tab.
- Alt text on all medical images (decorative images `alt=""`).
- Language attribute, page titles per route.

### 12.9 Image and icon plan

- Use local, optimised images in `static/img` (download once; do not hotlink in production).
- Hero: bright modern hospital reception or doctor with patient.
- Departments: one representative photo each (cardiology, neurology, orthopaedics, pediatrics, dermatology, general medicine, ENT, gynaecology).
- Doctors: professional portrait placeholders (free-licence), consistent crop (4:5), fallback avatar with initials.
- Icons: Font Awesome medical set (`fa-hospital`, `fa-user-doctor`, `fa-stethoscope`, `fa-heart-pulse`, `fa-calendar-check`, `fa-clock`, `fa-notes-medical`).
- Illustrations: simple SVG blobs/waves as section dividers; avoid heavy 3D assets.

---

## 13. Security and Privacy Plan

| Area | Control |
|---|---|
| Password storage | `werkzeug.security.generate_password_hash` (scrypt default), never plaintext; rehash on login if method changes |
| Password policy | Min 8 chars, at least 1 letter + 1 number; optional strength meter; max 128 chars |
| Session | Flask-Login session cookie: `HttpOnly=True`, `SameSite=Lax`, `Secure=True` in production; `PERMANENT_SESSION_LIFETIME=8h`; session refreshed on login |
| CSRF | Flask-WTF CSRFProtect globally; every POST form and fetch includes token; API POST uses `X-CSRFToken` |
| Authorization | `@login_required` + `@role_required("patient"|"doctor"|"admin")`; ownership checks on every booking/appointment route (IDOR prevention) |
| SQL injection | SQLAlchemy ORM parameterization; no string-built SQL |
| XSS | Jinja2 autoescape on; never `|safe` on user input; sanitize admin HTML fields |
| Rate limiting | Login 5/min per IP+email; register 3/hour per IP; booking 10/min per user; API slots 60/min |
| Account enumeration | Generic login error; register reveals only "email already registered" (acceptable trade-off) |
| Secure redirects | Validate `next` URL is relative; no open redirect |
| File uploads | Only images, extension + MIME check, size ≤ 2 MB, random filename, stored outside web root in prod |
| Secrets | `.env` only, `.env.example` committed; `SECRET_KEY` random 32+ bytes; never in git |
| HTTPS / headers | Production behind HTTPS; `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, basic CSP |
| Audit | Log logins, failed logins, bookings, cancellations, admin CRUD, role changes with IP + timestamp |
| Data minimization | Only collect name, email, phone, optional DOB/gender; no medical records beyond free-text visit reason |
| Privacy | Patients see only their own data; doctors see only their own patients; admin access logged; export/delete request process documented |
| Backups | Nightly DB backup in production; test restore procedure |
| Dependency hygiene | Pinned versions, `pip-audit` (optional) |

**Threat model highlights**

1. *Two patients booking the same slot* → DB unique constraint + atomic update (see §8.5).
2. *Patient A opening Patient B's appointment URL* → ownership check returns 403, not data.
3. *Doctor editing another doctor's schedule* → `doctor_id` derived from session, never from URL.
4. *Brute-force login* → rate limit + generic errors + optional account lock after 10 failures.
5. *CSRF on cancel booking* → CSRF token + POST-only route.

---

## 14. Email Notification Design

| Trigger | Recipient | Subject | Contents |
|---|---|---|---|
| Booking confirmed | Patient | `Appointment confirmed — MQ-20261110-0004` | Booking ID, doctor, department, date/time, room, fee, queue position, estimated wait, cancellation rules, directions |
| Appointment cancelled | Patient | `Appointment cancelled — MQ-...` | Reason, original slot, "book again" link |
| Cancellation by admin/doctor | Patient | `Your appointment was cancelled by the hospital` | Reason, apology, rebook link |
| Reminder (optional) | Patient | `Reminder: appointment tomorrow at 1:00 PM` | Details + check-in instructions |
| Doctor daily digest (optional) | Doctor | `Your schedule for 10 Nov — 14 patients` | Ordered list |

Implementation:
- `mail_service.send_booking_confirmation(appointment)` renders HTML + plain-text alternative.
- Called **after** the DB commit; wrapped in try/except so email failure never rolls back the booking.
- Every send is recorded in `notifications` with status `sent`/`failed` for troubleshooting and admin visibility.
- Development uses `MAIL_SUPPRESS_SEND=True` or writes emails to `instance/mail/` / console; tests monkeypatch the mailer and assert the call.

---

## 15. Validation and Error-Handling Matrix

| Input / scenario | Server rule | Response |
|---|---|---|
| Email format | `Email()` validator + lowercase | 400 / inline error |
| Email already registered | Case-insensitive lookup | Inline "An account with this email already exists" |
| Password mismatch | EqualTo validator | Inline error |
| Weak password | Regex policy | Inline error |
| Past date booking | `slot_date >= today` and time > now + 30 min | 400 "This slot has already passed" |
| Date beyond booking window | ≤ today + `booking_open_days` | 400 "Bookings open only 30 days ahead" |
| Doctor on leave | Slot status BLOCKED or no slot | Slot list empty + message |
| Slot already booked | Atomic claim rowcount = 0 | 409 + auto-refresh |
| Duplicate patient booking same doctor/date | Query active appointments | 409 "You already have an appointment with this doctor on this date" |
| Cancel after cutoff | Compare with cutoff setting | 409 "Cancellations are allowed up to 2 hours before the appointment" |
| Cancel someone else's booking | Ownership check | 403 |
| Inactive account | `is_active` check on login and each request | Logout + "Account disabled, contact hospital" |
| Unknown booking ID | Lookup | 404 page |
| Slot ID tampered to another doctor | Re-validate slot's doctor/date against URL | 400 |
| Mail server down | try/except + notification row `failed` | Booking succeeds; admin can resend (optional) |
| Database locked (SQLite) | WAL + busy timeout 15 s + retry once | 503 "Please try again" if still locked |
| 500 error | Global handler | Log traceback; friendly page; no stack trace to user |

**Flash message convention:** success = green toast, error = red toast, warning = amber, info = blue. Booking conflict always offers a "Show available slots" action.

---

## 16. Testing Plan

### 16.1 Test strategy

| Level | Scope | Tools |
|---|---|---|
| Unit | Waiting-time math, slot generation, booking-ID format, validators, cancellation rule function | Pytest, pure functions |
| Integration | Routes + DB + auth: register/login/book/cancel/admin flows | Flask test client, in-memory SQLite |
| Concurrency | Two threads booking one slot | `ThreadPoolExecutor`, separate app contexts/sessions |
| UI contract | Templates extend base, responsive meta, slot classes/labels, no missing static assets | Pytest + BeautifulSoup/regex |
| Manual E2E | Full demo script across 3 roles at 3 screen sizes | Checklist in `docs/test-report.md` |

**Test configuration**
- `TESTING=True`, `SQLALCHEMY_DATABASE_URI=sqlite:///:memory:` (or temp file for concurrency), `WTF_CSRF_ENABLED=False`, `MAIL_SUPPRESS_SEND=True`.
- `conftest.py` fixtures: `app`, `db`, `client`, `patient`, `doctor`, `admin`, `logged_in_patient`, `slot_factory`.
- Each test function gets a clean DB (`db.create_all()` / `drop_all()`).
- Coverage target: ≥ 85% overall; 100% of booking service and waiting service.

### 16.2 Required test cases (20)

| ID | Requirement | Test scenario | Steps (summary) | Expected result | Type / File |
|---|---|---|---|---|---|
| T01 | Patient registration | Valid registration creates patient | POST `/register` with name, unique email, valid password | 302 → login; user row role=patient; password hashed (not plaintext) | Integration `test_registration.py` |
| T02 | Registration validation | Duplicate email / weak password rejected | POST same email twice; POST `abc123` short password | 200 with form; no duplicate row; clear error messages | Integration |
| T03 | Login / logout | Valid login, session, logout | Register → login → GET dashboard → POST logout | Dashboard 200 with name; after logout dashboard redirects to login | Integration `test_auth.py` |
| T04 | Department selection | Only active departments listed | Create 2 active + 1 inactive; GET departments page | Active names present, inactive absent; cards link to doctors | Integration `test_departments.py` |
| T05 | Doctor selection | Doctors filtered by department | Create doctors in 2 departments; GET dept A doctors | Only dept A doctors returned; profile link works | Integration `test_doctors.py` |
| T06 | Date selection | Valid booking dates only | Request booking page for doctor with schedule | Dates within window, past dates disabled, leave dates disabled; API rejects past date | Integration `test_slots.py` |
| T07 | Available slots display | Slot states rendered correctly | Create AVAILABLE, BOOKED, BLOCKED slots; GET `/api/.../slots` + page | JSON statuses correct; available=true only for AVAILABLE; UI legend/classes present | Integration + UI contract |
| T08 | Successful booking | Book an available slot | Login patient → POST book slot | 302 to confirmation; appointment CONFIRMED; slot BOOKED; booking ID matches `MQ-...` | Integration `test_booking.py` |
| T09 | Auto slot close | Slot unavailable immediately after booking | Book slot → GET slots API → second patient GET page | First: 200; API shows `BOOKED/available:false`; second patient sees disabled 1:00 PM | Integration |
| T10 | Prevent duplicate booking | Same slot cannot be booked twice | Book slot as A, then POST same slot as B | B receives 409 `SLOT_TAKEN`; exactly 1 appointment; slot still BOOKED | Integration |
| T11 | Simultaneous booking | Two patients race for one slot | Two threads, barrier start, both POST same slot | Exactly one success, one 409; DB has 1 appointment; no 500 | Concurrency `test_concurrency.py` |
| T12 | Appointment cancellation | Patient cancels before cutoff | Book future slot → POST cancel with reason | Appointment CANCELLED; slot AVAILABLE again; cancellation email/notification logged | Integration `test_cancellation.py` |
| T13 | Cancellation rules | Cutoff / repeat / ownership enforced | Cancel within 2 h; cancel other patient's; exceed max cancellations | 409/403 with rule messages; slot unchanged | Integration |
| T14 | Cancelled slot reopens | Another patient can book released slot | A books → A cancels → B books same slot | B succeeds, new booking ID; slot BOOKED by B | Integration |
| T15 | Confirmation | Confirmation page and email | Complete booking | Page shows booking ID, doctor, dept, date, time, room, fee, wait; mailer called once with patient email | Integration `test_confirmation.py` |
| T16 | Doctor daily schedule | Doctor sees own day only | Create appointments for 2 doctors on same date; login doctor A | Doctor A sees only own patients ordered by time; cannot see doctor B's | Integration `test_doctor_schedule.py` |
| T17 | Patient history | All statuses visible, filtered | Create upcoming, completed, cancelled appointments | History shows all with correct badges/filters; other patient's booking absent | Integration |
| T18 | Admin dashboard | Correct KPIs and charts data | Seed known counts → login admin → GET dashboard + `/admin/api/stats` | Totals match; available/booked slot counts correct; chart arrays non-empty; patient blocked from access | Integration `test_admin.py` |
| T19 | Doctor & department management | Admin CRUD | Create/edit/deactivate department & doctor with account | Rows updated; inactive hidden from patients; non-admin gets 403 | Integration `test_admin.py` |
| T20 | Waiting-time calculation | Correct estimate from queue | 3 appointments ahead, avg 15 min, delay 5 | `patients_ahead=3`, position 4, wait = 50 min; patient with no queue → 0/"you're next" | Unit `test_waiting_time.py` |
| T21 | Mobile responsive UI | Responsive contract | Render key templates; parse viewport meta, base extension, responsive classes; check CSS media queries | All pages include viewport, base layout, media queries for 576/768/992; no fixed-width main container | UI contract `test_responsive.py` |
| T22 | Security & auth | Access control, CSRF, hashing, injection | Patient hits `/admin/dashboard`; POST without CSRF; inspect password; login SQLi payload in email | 403; CSRF 400; hash != password; SQLi treated as literal email, no bypass | Security `test_security.py` |

> The numbering above covers the 20 requested areas (T19 combines doctor/department management; T20 combines waiting time and estimate display; T21/T22 cover responsive and security). Rename to `TC-01 … TC-20` in the report if the rubric expects exactly 20 rows.

### 16.3 Concurrency test sketch

```python
# tests/test_concurrency.py
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

def test_two_patients_one_slot(app, slot_id, two_patients):
    barrier = Barrier(2)
    def book(patient_id):
        client = app.test_client()
        login(client, patient_id)
        barrier.wait()                      # maximise overlap
        return client.post(f"/patient/book/{slot_id}", follow_redirects=False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [f.result() for f in
                     [pool.submit(book, pid) for pid in two_patients]]

    codes = sorted(r.status_code for r in responses)
    assert codes == [302, 409]             # one books, one rejected
    assert Appointment.query.count() == 1
    assert Slot.query.get(slot_id).status == "BOOKED"
```

For SQLite, use a **file-based** test DB with WAL for this test (in-memory DBs do not share well across threads). For MySQL CI, the same test runs against the container with `FOR UPDATE` enabled.

### 16.4 Test data strategy

- `tests/factories.py` helpers: `create_user(role=...)`, `create_department()`, `create_doctor(dept, avg=15)`, `create_schedule(doctor)`, `create_slot(doctor, date, time, status)`, `create_appointment(...)`.
- Deterministic dates relative to `today` (e.g., `today + 3 days`) so tests never expire.
- Seed script (`seed.py`) creates a demo dataset: 8 departments, 12 doctors, schedules, 30 days of slots, 2 demo patients, 1 admin. Credentials printed to console and documented in README (dev only).

### 16.5 Definition of test success

- `pytest -q` → all tests pass.
- `pytest --cov=app --cov-report=term-missing` → ≥ 85%.
- No test depends on execution order.
- Concurrency test run 20 times in a loop without a failure.
- Manual checklist for Chrome DevTools device toolbar: iPhone SE, iPad, 1440 px desktop.

---

## 17. Step-by-Step Development Process

### Phase 0 — Setup (0.5 day)
1. Create venv, install dependencies, pin versions.
2. Create app factory, config classes, `.env.example`, extensions.
3. Set up Git, `.gitignore`, README skeleton.
4. Create empty SQLite DB and confirm `flask run`.

**Exit:** `/` returns a placeholder page; `pytest` collects 0 tests without error.

### Phase 1 — Database and auth (2 days)
1. Implement `User`, `PatientProfile` models + role constants.
2. Registration/login/logout forms, routes, templates.
3. Flask-Login setup, role decorator, error pages.
4. Tests T01–T03, T22.

**Exit:** patient can register, log in, log out; admin/doctor/patient land on the right page.

### Phase 2 — Departments, doctors, schedules (2 days)
1. Department + doctor + schedule models and seed data.
2. Public/patient department grid, doctor list, doctor profile.
3. Admin CRUD for departments/doctors.
4. Slot generation service + admin schedule editor + leave blocking.
5. Tests T04–T06, T19.

**Exit:** data-driven department and doctor pages; slots generated for next 30 days.

### Phase 3 — Booking engine (3 days)
1. Slot listing API with status/summary.
2. Booking service: validation, atomic claim, appointment insert, booking ID.
3. Booking wizard UI with date pills, slot grid, summary, confirmation.
4. Email service + confirmation template.
5. Tests T07–T11, T15.

**Exit:** two browsers cannot book the same slot; confirmation + email work.

### Phase 4 — Patient management (1.5 days)
1. Dashboard cards and upcoming appointments.
2. Appointment history filters and detail page.
3. Cancellation flow + rules + slot release.
4. Waiting-time service and live wait widget.
5. Tests T12–T14, T17, T20.

**Exit:** full patient lifecycle works, cancelled slot can be rebooked.

### Phase 5 — Doctor and admin dashboards (2.5 days)
1. Doctor dashboard, daily schedule, check-in/complete/no-show, queue ordering.
2. Admin KPIs + Chart.js endpoints + charts.
3. Admin appointment oversight, patient management.
4. Tests T16, T18.

**Exit:** all three dashboards functional with real data.

### Phase 6 — UI polish and responsiveness (2 days)
1. Landing page hero, sections, images, animations.
2. Design tokens, components, consistent forms/tables/badges.
3. Mobile sidebar, bottom nav, responsive tables and slot grid.
4. Loading skeletons, toasts, empty states, 404/403/409 pages.
5. Accessibility pass (labels, focus, contrast, reduced motion).
6. Tests T21 + manual device checks.

**Exit:** polished, demo-ready on phone, tablet, desktop.

### Phase 7 — Hardening and testing (1.5 days)
1. Rate limiting, security headers, audit logging.
2. Full test suite green, coverage report, 20× concurrency loop.
3. Input validation review, error-message review.
4. Seed data and demo script.

### Phase 8 — Documentation and viva prep (1 day)
1. README: setup, features, screenshots, demo accounts.
2. `docs/test-report.md`: 20 test cases with actual results.
3. ERD image, architecture diagram, screenshots.
4. Project report chapters and presentation slides.
5. Mock viva: explain slot locking, transaction isolation, waiting-time formula.

**Total estimate:** ~16 working days (3–4 weeks at college pace).

### 17.1 Git workflow

- Branches: `main` (stable), `feature/auth`, `feature/booking`, `feature/admin`, `feature/ui`.
- Commit style: `feat(booking): atomic slot claim with rowcount check`, `test(concurrency): two-patient race`.
- Merge only when tests pass; tag `v1.0-demo` for submission.

---

## 18. Seed Data and Demo Script

### 18.1 Demo accounts

| Role | Email | Password | Notes |
|---|---|---|---|
| Admin | `admin@mediqueue.local` | `Admin@123` | Full dashboard |
| Doctor | `dr.arjun@mediqueue.local` | `Doctor@123` | Cardiology, avg 15 min |
| Patient A | `asha@example.com` | `Patient@123` | Has upcoming booking |
| Patient B | `ravi@example.com` | `Patient@123` | Used for conflict demo |

### 18.2 Five-minute demo flow

1. **Landing** → show hero, departments, doctors, mobile view.
2. **Register** a new patient live → login.
3. **Book**: Cardiology → Dr. Arjun → tomorrow → show 1:00 PM **Available** → book → confirmation with ID + wait time.
4. **Email**: open console/mail file showing confirmation.
5. **Conflict**: log in as Patient B in a second browser → same doctor/date → 1:00 PM is **Booked/disabled** → book 2:00 PM. (Optional: run the concurrency test on screen.)
6. **Cancel**: Patient A cancels 1:00 PM → slot returns to Available → Patient B could book it (or admin view shows it).
7. **Doctor**: log in as Dr. Arjun → daily schedule → check in a patient → complete → wait time of next patient recalculates.
8. **Admin**: dashboard charts, counts, add a department/doctor, view all appointments.
9. **Responsive**: DevTools device toolbar → iPhone → show bottom nav and single-column slot grid.

---

## 19. Deliverables Checklist

| # | Deliverable | Location / format |
|---|---|---|
| 1 | Project plan (this document) | `HOSPITAL_PROJECT_PLAN.md` |
| 2 | Architecture diagram | `docs/architecture.png` + README section |
| 3 | ER diagram | `docs/ERD.png` |
| 4 | SQL schema / migrations | `migrations/` + `docs/schema.sql` |
| 5 | Working Flask application | repository root |
| 6 | Responsive frontend (all pages) | `app/templates`, `app/static` |
| 7 | Seed/demo data | `seed.py` |
| 8 | Automated test suite (≥ 20 cases) | `tests/` |
| 9 | Coverage report | `docs/coverage.html` |
| 10 | Test report with actual results | `docs/test-report.md` |
| 11 | Screenshots (desktop + mobile) | `docs/screenshots/` |
| 12 | README with setup and demo accounts | `README.md` |
| 13 | Project report (college format) | `docs/project-report.md` / PDF |
| 14 | Presentation slides + viva notes | `docs/viva.md` |

---

## 20. Acceptance Criteria (Definition of Done)

The project is complete when **all** of the following are true:

1. A new patient can register, log in, and log out securely.
2. A patient can navigate department → doctor → date → slot and book.
3. A successful booking creates exactly one `appointments` row, marks the slot `BOOKED`, and shows a booking ID + details + estimated wait.
4. The same doctor/date/time slot can never have two appointments — verified by automated test and by two browsers.
5. Concurrent booking attempts yield exactly one success and one friendly conflict, with no server error.
6. Booked slots display as unavailable (locked) and available slots as green/available.
7. A patient can view and cancel an eligible appointment; the slot reopens only when rules allow.
8. A doctor sees only their own daily schedule and can progress patient statuses.
9. An admin can manage doctors, departments, schedules, and patients, and sees accurate KPI cards and charts.
10. Confirmation and cancellation emails are generated and logged.
11. Waiting time and queue position are computed correctly and displayed with an "estimate" label.
12. The UI is responsive at 375 px, 768 px, and 1440 px, with no horizontal scroll on main flows.
13. All 20 required test areas are covered by passing automated tests; coverage ≥ 85%.
14. Security checks pass: role protection, CSRF, hashed passwords, rate limiting, audit log.
15. README + seed script let a fresh machine run the project in under 10 minutes.

---

## 21. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Race condition double-books a slot | Breaks the core requirement | Unique constraint + atomic conditional update + concurrency test (non-negotiable) |
| SQLite `database is locked` under load | 500 errors during demo | WAL mode, `timeout=15`, short transactions, retry once; switch to MySQL for final demo if needed |
| Timezone confusion (server vs patient) | Wrong slot times | Store hospital-local naive times; one `TIMEZONE` setting; render consistently; document assumption |
| Email deliverability | Demo email not visible | Development mailer writes to console/file; show it live; production uses SMTP env vars |
| Scope creep (payments, chat, AI) | Missed deadline | Non-goals list enforced; stretch features only after Phase 7 |
| Weekday/time bugs in slot generation | Missing or wrong slots | Pure function + unit tests with fixed dates; idempotent generation |
| Overlapping schedules for a doctor | Duplicate slot generation | Unique constraint prevents duplicates; admin validation warns on overlap |
| Large image assets slow page | Poor demo experience | Compress to WebP/JPEG ≤ 200 KB, `loading="lazy"`, fixed aspect ratios |
| Cancellation abuse | Slot churn | Max cancellations per 30 days + cutoff + audit log |
| Data loss during development | Rework | Migrations from day one; nightly copy of `instance/hospital.db`; seed script reproducibility |

---

## 22. Future Enhancements (post-v1)

1. 5-minute slot hold (`HELD` + expiry) during checkout.
2. Reschedule without cancel-and-rebook.
3. SMS/WhatsApp reminders via Twilio.
4. QR-code check-in at reception.
5. Doctor running-late one-click that broadcasts new ETAs.
6. Multi-branch hospitals and room/resource scheduling.
7. Patient reviews and doctor ratings.
8. Waitlist for fully booked days (auto-offer cancelled slots).
9. PWA/offline mode and push notifications.
10. Role-based analytics export and hospital-wide reports.

---

## 23. Immediate Next Step

1. Confirm this plan (scope, rules, defaults such as 2-hour cancellation cutoff and 30-day booking window).
2. Scaffold the Flask app and database models.
3. Build auth → departments/doctors → slots → booking → dashboards → UI polish → tests, in that order.
4. Seed demo data and run the five-minute demo script.

> **Build rule:** never implement booking with a JavaScript `disabled` attribute alone. The database constraint is the source of truth; the UI only reflects it.

---

*End of plan — ready for build.*
