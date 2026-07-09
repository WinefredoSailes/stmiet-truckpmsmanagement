# Truck PMS & Servicing System

A Django-based Preventive Maintenance System for internal fuel tanker fleet management. Tracks maintenance schedules, job orders (repairs/PMS), parts usage, contractor services, mechanic KPI, and OJT training — all in one system.

**Live:** https://stmiet-truckpmsmanagement.onrender.com

---

## Table of Contents

- [Setup Guide](#setup-guide)
- [Default Accounts](#default-accounts)
- [Quick Start](#quick-start-script)
- [Deployment to Render](#deployment-to-render)
- [Architecture](#architecture)
- [User Guide](#user-guide)

---

## Setup Guide

### Requirements
- Python 3.11+
- pip

### Local Installation

```bash
# 1. Navigate to project
cd truck_pms

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run migrations
python manage.py migrate

# 6. Seed initial data (users, trucks, PM templates, etc.)
python manage.py seed_data

# 7. Start server
python manage.py runserver 0.0.0.0:8000
```

### Default Accounts

| Username | Password | Role | Notes |
|---|---|---|---|
| `admin` | `admin123` | **Super Admin** | Full access + User Management |
| `miguel` | `password123` | **Admin** | Can manage trucks, PM, JOs, contractors |
| `juan` | `password123` | **Staff** | Can create/manage JOs, view PM |
| `pedro` | `password123` | **Mechanic** | Engine specialist — sees assigned JOs only |
| `andres` | `password123` | **Mechanic** | Brakes specialist |
| `contractor1` | `password123` | **Contractor** | Limited to contractor-assigned JOs |

> **Note:** OJT/Trainee accounts must be created manually via User Management since they need a supervisor assignment.

### Quick Start Script

```powershell
# Windows — run from project root (creates venv, installs deps, migrates, seeds)
.\start.ps1
```

---

## Deployment to Render

### Prerequisites
1. Push your code to a GitHub repository.
2. Create a **Render account** at https://render.com.
3. Create a **PostgreSQL** database on Render (free tier works).

### Steps

1. **Dashboard → New → Web Service**
2. Connect your GitHub repo.
3. Configure:

| Setting | Value |
|---|---|
| **Name** | `stmiet-truckpms` (or your choice) |
| **Region** | Singapore (or nearest to fleet) |
| **Branch** | `main` |
| **Root Directory** | `truck_pms` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py seed_data` |
| **Start Command** | `gunicorn truck_pms.wsgi --log-file -` |
| **Plan** | Free |

4. Add **Environment Variables**:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your PostgreSQL internal connection string (from Render PostgreSQL dashboard) |
| `DJANGO_SECRET_KEY` | A long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com,localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com,http://localhost` |

5. Click **Create Web Service**. Render will build and deploy automatically.
6. Your app is live at `https://your-service-name.onrender.com`.

> **Auto-deploy is OFF** by default. After pushing changes, trigger **Manual Deploy → Deploy Latest Commit** from the Render dashboard.

---

## Architecture

### Apps

| App | Purpose |
|---|---|
| `accounts` | Custom User model with 6 roles (SUPER_ADMIN, ADMIN, STAFF, MECHANIC, CONTRACTOR, TRAINEE) |
| `trucks` | Truck/fleet asset management with 17 Certificate of Registration fields |
| `pms` | Task categories (23), task templates (154), per-truck PM schedules with auto-status |
| `joborders` | Job Orders, line items, parts tracking, close-flow with PM schedule update |
| `service_log` | Immutable audit trail of all work done (populated on JO close) |
| `contractors` | External vendor registry (skills, contact, history) |
| `kpi` | Computed reports: mechanic KPI, contractor rates, truck frequency, predictive analytics |
| `training` | OJT onboarding: attendance check-in/out, task ratings (1-5), weekly reviews |
| `sop` | SOP Manual — PDF generator (WeasyPrint), full 8-volume handbook with browser-print fallback |
| `core` | Base template, shared CSS, form mixin, request-timing middleware, sidebar context processor |

### Key Model Relationships

```
TaskCategory ──1:N── TaskTemplate ──1:N── PMSchedule ──N:1── Truck
                                                    │
                                                    ▼
JobOrder ──1:N── JobOrderLineItem ──1:N── LineItemPart
    │
    └──1:N── ServiceLogEntry

Training ──1:N── Attendance
         ├── TaskRating (links to TaskTemplate)
         └── WeeklyReview
```

### Status Calculation (PM Schedule)

Each PMSchedule's `status()` method runs live (no stored field):

- **MILEAGE**: compares `truck.current_mileage_km` against `last_mileage_km + interval_value`
- **HOURS**: compares `truck.current_engine_hours` against `last_engine_hours + interval_value`
- **CALENDAR**: compares current datetime against `last_completed_at + interval_value` days
- **VISUAL**: always returns `"visual"` (no auto-calculation)
- **"Due" threshold**: within 10% of the interval value

### Tech Stack

- **Backend:** Django 6.0 + PostgreSQL (production) / SQLite (local)
- **Frontend:** Django Templates + Bootstrap 5.3 + Bootstrap Icons
- **Font:** Inter (Google Fonts)
- **CSS:** Custom stylesheet with CSS variables
- **Static:** WhiteNoise for production static file serving
- **Server:** Gunicorn

---

## User Guide

> **Full user documentation** is available in [USER_GUIDE.md](USER_GUIDE.md) — covers every feature, role-by-role workflow, and step-by-step procedures for the SOP handbook.

### SOP Manual

A downloadable SOP handbook is available at **Sidebar → SOP Manual** for all logged-in users.

- **English Edition:** Full 8-volume, 4-appendix manual covering 23 PM category procedures, repair workflow, safety, HAZMAT, training, and more.
- **Tagalog Edition:** Same content in Filipino (ready for translation).
- **Browser-Print Fallback:** If PDF is not yet generated, the system serves the full HTML page — use Ctrl+P → "Save as PDF."

Regenerate PDFs on content changes:
```bash
cd truck_pms
python manage.py build_sop
```

### Quick Reference by Role

| Role | Login Redirect | Key Features Available |
|---|---|---|
| **Super Admin** | Dashboard | Everything + User Management + Django Admin |
| **Admin** | Dashboard | All ops + Training (Assign + Supervise) + KPI + Predictive Analytics |
| **Staff** | Dashboard | Create/manage JOs, view PM, Training (Supervise OJTs) |
| **Mechanic** | Dashboard | My Assignments, line item status updates, parts logging |
| **Contractor** | My Assignments | Same as Mechanic, limited to own JOs |
| **OJT / Trainee** | Training Dashboard | Check-in/out, view ratings & reviews |
