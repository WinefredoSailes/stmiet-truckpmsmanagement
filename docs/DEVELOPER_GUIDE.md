# Truck PMS & Servicing System — Developer Guide

> **Purpose:** Handoff documentation for developers taking over or extending the system.
>
> **Last updated:** July 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Tech Stack](#3-tech-stack)
4. [Local Development Setup](#4-local-development-setup)
5. [Project Architecture](#5-project-architecture)
6. [Key Design Decisions](#6-key-design-decisions)
7. [PM Schedule Status Logic](#7-pm-schedule-status-logic)
8. [Role & Permission System](#8-role--permission-system)
9. [Job Order Workflow](#9-job-order-workflow)
10. [Audit Trail (Service Log)](#10-audit-trail-service-log)
11. [SOP Manual System](#11-sop-manual-system)
12. [Training & OJT Module](#12-training--ojt-module)
13. [KPI & Analytics](#13-kpi--analytics)
14. [Static Files & Frontend](#14-static-files--frontend)
15. [Testing](#15-testing)
16. [Deployment](#16-deployment)
17. [Common Maintenance Tasks](#17-common-maintenance-tasks)

---

## 1. Project Overview

The Truck PMS & Servicing System is a Django 6.0 web application that manages:

- **Fleet assets** — trucks with 17 Certificate of Registration fields
- **Preventive Maintenance (PM)** — 23 categories, 154 task templates, per-truck schedules
- **Job Orders** — repair/PMS work orders with line items and parts tracking
- **Service Log** — immutable audit trail of all work performed
- **Contractors** — external vendor registry
- **KPI / Analytics** — mechanic performance, truck frequency, predictive analytics, trainee KPIs
- **Training** — OJT onboarding with attendance, task ratings, weekly reviews, holiday calendar
- **SOP Manual** — built-in bilingual handbook with 34 PM procedures

### Users / Roles

| Role | Count (seeded) |
|------|----------------|
| Super Admin | 1 (`admin`) |
| Admin | 1 (`miguel`) |
| Staff | 1 (`juan`) |
| Mechanic | 2 (`pedro`, `andres`) |
| Contractor | 1 (`contractor1`) |
| Trainee | 2 (`jose`, `maria`) |

---

## 2. Repository Structure

```
TRUCK-PMS-SERVICING-SYSTEM/
├── README.md                    # Project overview & quick setup
├── start.ps1                    # Windows quick-start script
├── .gitignore
├── docs/
│   ├── USER_GUIDE.md            # End-user manual
│   ├── DEVELOPER_GUIDE.md       # This file — developer handoff
│   ├── ORIENTATION_GUIDE.md     # Orientation presentation outline
│   └── SEED_ACCOUNTS.md         # Pre-seeded account reference
│
└── truck_pms/                   # Django project root
    ├── manage.py
    ├── Procfile                 # Render deployment entrypoint
    ├── requirements.txt         # Python dependencies
    ├── truck_pms/               # Django project settings
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py / asgi.py
    │
    ├── accounts/                # Custom User model, auth
    │   ├── models.py            # User (6 roles), role_required decorator
    │   ├── views.py             # Login, user CRUD (Super Admin only)
    │   ├── management/commands/
    │   │   └── seed_data.py     # Seeds users, trucks, PM templates
    │   └── templates/accounts/
    │
    ├── trucks/                  # Fleet management
    │   ├── models.py            # Truck (30+ fields incl. mileage/hours)
    │   ├── views.py             # CRUD + import/export + batch mileage update
    │   ├── forms.py             # TruckForm, TruckImportForm, MileageUpdateForm
    │   └── templates/trucks/
    │
    ├── pms/                     # Preventive Maintenance
    │   ├── models.py            # TaskCategory, TaskTemplate, PMSchedule
    │   ├── views.py             # Schedule list, sync, complete, category/template CRUD
    │   └── templates/pms/
    │
    ├── joborders/               # Work orders
    │   ├── models.py            # JobOrder (4 types, 5 states), LineItem, LineItemPart
    │   ├── views.py             # CRUD, close-flow, add/update/delete line items
    │   ├── tests.py             # 88 tests (model + view + E2E)
    │   └── templates/joborders/
    │
    ├── service_log/             # Immutable audit trail
    │   ├── models.py            # ServiceLogEntry, ServiceLogPart
    │   └── templates/service_log/
    │
    ├── contractors/             # External vendors
    │   └── models.py + views.py
    │
    ├── kpi/                     # Analytics
    │   ├── views.py             # Mechanic KPI, contractor rates, predictive, trainee KPIs
    │   └── templates/kpi/
    │
    ├── training/                # OJT module
    │   ├── models.py            # Training, Attendance, TaskRating, WeeklyReview, Holiday
    │   ├── views.py             # Dashboard, check-in/out, ratings, reviews, holidays
    │   ├── tests.py
    │   └── templates/training/
    │
    ├── sop/                     # SOP Manual
    │   ├── management/commands/
    │   │   └── build_sop.py     # Generates HTML SOP manual
    │   ├── templates/sop/       # Section templates (EN + TL)
    │   └── views.py             # Download & view pages
    │
    ├── core/                    # Shared infrastructure
    │   ├── context_processors.py # Sidebar menu builder (role-aware)
    │   ├── middleware.py         # Request timing middleware
    │   ├── static/
    │   │   ├── css/style.css    # Custom stylesheet (14KB)
    │   │   └── js/app.js        # Sidebar toggle, page loader, mobile menu
    │   └── templates/core/
    │       ├── base.html        # Base template (Bootstrap 5.3, sidebar, topbar)
    │       └── pagination.html
    │
    └── static/                  # Project-level static assets
        ├── favicon-truck-pms.png
        ├── stmiet-trans-logo.png
        ├── stpc-trans-logo.png
        └── sop/
            ├── en.html          # Generated SOP (English)
            └── tl.html          # Generated SOP (Tagalog)
```

---

## 3. Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 6.0 |
| **Database** | SQLite (local), PostgreSQL (production on Render) |
| **Frontend** | Django Templates + Bootstrap 5.3 + Bootstrap Icons |
| **Font** | Inter (Google Fonts) |
| **CSS** | Custom single stylesheet (`style.css`, ~14KB) + Bootstrap utilities |
| **JS** | Custom `app.js` (~40 lines) + Bootstrap JS bundle (CDN) |
| **Static** | WhiteNoise (production) |
| **Server** | Gunicorn |
| **PDF** | WeasyPrint (optional — HTML print fallback) |

---

## 4. Local Development Setup

### Prerequisites

- Python 3.11+
- Git
- pip

### Steps

```bash
# 1. Clone the repository
git clone <repo-url> truck-pms
cd truck-pms

# 2. Navigate to the Django project
cd truck_pms

# 3. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set environment variables (Windows PowerShell)
$env:DJANGO_SECRET_KEY = 'dev-secret-key-change-in-production'
$env:DJANGO_DEBUG = 'True'

# 6. Run migrations
python manage.py migrate

# 7. Seed initial data
python manage.py seed_data

# 8. Generate SOP manual
python manage.py build_sop

# 9. Start development server
python manage.py runserver 0.0.0.0:8000
```

Or use the quick-start script from the project root:

```powershell
.\start.ps1
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | **Yes** | — | Django secret key |
| `DJANGO_DEBUG` | No | `False` | Enable debug mode |
| `DJANGO_ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | No | `http://localhost,http://127.0.0.1` | Comma-separated origins |
| `DATABASE_URL` | No | SQLite (local) | PostgreSQL connection string |

---

## 5. Project Architecture

### App Dependency Graph

```
accounts ───> (provides User model to all apps)
    │
    ├──> trucks ──> pms
    │                   │
    │                   ▼
    └──> joborders ──> service_log
    │       │
    │       ▼
    ├──> contractors
    ├──> kpi
    ├──> training
    ├──> sop
    └──> core (base template, context, middleware)
```

### Key Model Relationships

```
TaskCategory (23 categories)
    └── TaskTemplate (154 templates)
            └── PMSchedule (per-truck schedules, ~154 per truck)
                    │
                    ├── Truck (fleet asset model)
                    │
                    └── JobOrder (optional — PM schedules can be completed directly)
                            │
                            ├── JobOrderLineItem (scope-of-work items)
                            │       └── LineItemPart (parts used)
                            │
                            └── ServiceLogEntry (audit record)
                                    └── ServiceLogPart (parts breakdown)
```

---

## 6. Key Design Decisions

### No Stored "Status" Field on PMSchedule

The `PMSchedule.status()` method is computed live (not a database field). It compares the truck's current mileage/hours against the schedule's last-recorded values + interval. This means:

- **Updating `truck.current_mileage_km` instantly changes all PM schedule statuses**
- No need to run a cron job or background task
- The `batch_update_mileage` view (Staff+) is the primary workflow for updating readings from Cartrack

### PM Completion Workflow

There are **two paths** to completing a PM:

1. **Direct ✅ Mark Complete** (primary path) — creates a `ServiceLogEntry` without requiring a Job Order. Supports parts entry and labor hours inline.
2. **Via Job Order** — legacy path. PM type Job Orders can still record work, but there is no auto-population of PM schedules as line items.

The "PM checklist" on Job Order creation was **removed** to eliminate confusion between PM completion and JO line items.

### Audit Trail

`ServiceLogEntry` is an **immutable record** — it is created on PM completion or JO close and should not be edited. Parts are stored in a separate `ServiceLogPart` model (ForeignKey to `ServiceLogEntry`) for itemized cost breakdown.

### Role-Based Sidebar

The sidebar is built dynamically in `core/context_processors.py` — each role sees exactly the sections/links they need. The mechanic role only sees "My Assignments" under Work Orders, not the full Job Order list.

---

## 7. PM Schedule Status Logic

Located in `pms/models.py` (`PMSchedule.status()`):

| Type | Calculation | "Due" Threshold | Overdue |
|------|-------------|-----------------|---------|
| `MILEAGE` | `truck.current_mileage_km >= last_mileage_km + interval_value` | Within 10% of interval | Past interval |
| `HOURS` | `truck.current_engine_hours >= last_engine_hours + interval_value` | Within 10% of interval | Past interval |
| `CALENDAR` | `now() >= last_completed_at + interval_value days` | Within 10% of interval | Past interval |
| `VISUAL` | Always `"visual"` | N/A | N/A |
| `INACTIVE` | Always `"inactive"` | N/A | N/A |

The 10% grace threshold means: if `last_mileage_km = 1000` and `interval_value = 5000`, the schedule shows **due** at 5500 km and **overdue** at 6000 km.

---

## 8. Role & Permission System

### Roles (in `accounts/models.py`)

```python
class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        ADMIN       = 'ADMIN', 'Admin'
        STAFF       = 'STAFF', 'Staff'
        MECHANIC    = 'MECHANIC', 'Mechanic'
        CONTRACTOR  = 'CONTRACTOR', 'Contractor'
        TRAINEE     = 'TRAINEE', 'Trainee'
```

### Permission Decorator

`@role_required(*roles)` in `accounts/decorators.py` — checks `request.user.role` against allowed roles. Used on every view.

### Sidebar Access (in `core/context_processors.py`)

| Section | Super Admin | Admin | Staff | Mechanic | Contractor | Trainee |
|---------|:-----------:|:-----:|:-----:|:--------:|:----------:|:-------:|
| Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Fleet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Update Mileage | ✅ | ✅ | ✅ | — | — | — |
| PMS Schedules | ✅ | ✅ | ✅ | — | — | — |
| PM Categories | ✅ | ✅ | — | — | — | — |
| PM Templates | ✅ | ✅ | — | — | — | — |
| Job Orders | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| My Assignments | — | — | — | ✅ | ✅ | — |
| Service Ledger | ✅ | ✅ | — | — | — | — |
| Contractors | ✅ | ✅ | — | — | — | — |
| KPI Reports | ✅ | ✅ | — | — | — | — |
| Training | ✅ | ✅ | ✅ | — | — | ✅ |
| User Management | ✅ | — | — | — | — | — |
| SOP Manual | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 9. Job Order Workflow

### Types

| Type | Description |
|------|-------------|
| `REPAIR` | Unscheduled repair work |
| `PMS` | Preventive maintenance service |
| `CONTRACTOR` | Work assigned to external vendor |
| `OTHER` | Miscellaneous |

### States

```
DRAFT ──> OPEN ──> IN_PROGRESS ──> COMPLETED ──> CLOSED
                                            │
                                            └──> CANCELLED
```

- **DRAFT**: Being built up, not yet assigned
- **OPEN**: Created, waiting for work to start
- **IN_PROGRESS**: Mechanic/contractor has started
- **COMPLETED**: Work done, pending review & close
- **CLOSED**: Final state — triggers `ServiceLogEntry` creation and PM schedule updates
- **CANCELLED**: Aborted before completion

### Close Flow

Closing a Job Order:
1. Sets status to `CLOSED`
2. Creates a `ServiceLogEntry` for each PM line item
3. Updates `PMSchedule.last_completed_at`, `last_mileage_km`, `last_engine_hours`
4. Records total parts cost from `LineItemPart` records

---

## 10. Audit Trail (Service Log)

### Models

```python
class ServiceLogEntry(models.Model):
    truck = ForeignKey(Truck)
    job_order = ForeignKey(JobOrder, nullable=True)  # null for direct PM complete
    performed_by = ForeignKey(User)
    task_template = ForeignKey(TaskTemplate)
    mileage_at_service = IntegerField()
    engine_hours_at_service = DecimalField()
    labor_hours = DecimalField()
    total_parts_cost = DecimalField()
    notes = TextField()
    performed_at = DateTimeField(auto_now_add=True)

class ServiceLogPart(models.Model):
    service_log = ForeignKey(ServiceLogEntry, related_name='parts')
    part_name = CharField(max_length=200)
    quantity = IntegerField()
    unit_cost = DecimalField()
```

The service ledger (`/service-log/all/` for Admin, `/service-log/truck/<pk>/` per truck) displays all entries with collapsible parts detail rows.

---

## 11. SOP Manual System

### Location

- Source templates: `sop/templates/sop/en/` and `sop/templates/sop/tl/`
- Generated output: `static/sop/en.html` and `static/sop/tl.html`
- Generator command: `python manage.py build_sop`

### Architecture

The SOP uses Django's template engine to compose a full HTML manual. Each section is a partial template (e.g., `_procedure.html`) included from the chapter files. The `build_sop` command renders the templates to static HTML files.

### Current Content

- **34 procedures** across 23 PM categories
- **Bilingual**: English and Tagalog versions
- **Sections**: 8 chapters of PM procedures + Chapter 9 (Documentation)
- **Standardized format**: Purpose → Scope → Frequency → PPE → Tools → Step-by-Step → Acceptance Criteria → Safety → Tip → Documentation → Sign-off

### WeasyPrint (Optional)

If WeasyPrint is installed, `build_sop` generates PDFs. Otherwise it falls back to HTML output (print via Ctrl+P → "Save as PDF").

---

## 12. Training & OJT Module

### Models

```python
class Training(models.Model):
    trainee = ForeignKey(User)
    supervisor = ForeignKey(User)
    truck = ForeignKey(Truck, nullable=True)
    start_date = DateField()
    status = CharField(choices=[ACTIVE, COMPLETED, WITHDRAWN])

class Attendance(models.Model):
    training = ForeignKey(Training)
    date = DateField()
    check_in = DateTimeField()
    check_out = DateTimeField(nullable=True)
    is_holiday = BooleanField()

class TaskRating(models.Model):
    training = ForeignKey(Training)
    task_template = ForeignKey(TaskTemplate)
    rating = IntegerField(1-5)
    rated_by = ForeignKey(User)

class WeeklyReview(models.Model):
    training = ForeignKey(Training)
    week_number = IntegerField()
    supervisor_rating = IntegerField(1-5)
    notes = TextField()

class Holiday(models.Model):
    date = DateField(unique=True)
    name = CharField(max_length=100)
```

### Trainee KPI Calculation

```
Trainee Score = (attendance_rate × 0.50)
              + (avg_task_rating × 0.10)
              + (avg_supervisor_review × 0.20)
              + (tasks_completed / total_tasks × 0.20)
```

Attendance is holiday-aware — holidays don't count as missed days.

---

## 13. KPI & Analytics

| View | URL | Access | Description |
|------|-----|--------|-------------|
| Mechanic KPI | `/kpi/mechanic/` | Admin+ | Per-mechanic stats: JOs completed, parts cost, labor hours |
| Contractor Rates | `/kpi/contractor/` | Admin+ | Contractor performance |
| Truck Frequency | `/kpi/truck-frequency/` | Admin+ | Which trucks get the most work orders |
| Predictive | `/kpi/predictive/` | Admin+ | Forecast future maintenance needs |
| Trainee KPI | `/kpi/trainee/` | Staff+, Trainee | Weighted performance score |

---

## 14. Static Files & Frontend

### Organization

```
core/static/
├── css/
│   └── style.css          # All custom CSS (~14KB, CSS variables)
└── js/
    └── app.js             # Sidebar, loader, mobile menu (~40 lines)

static/                     # Project-level static assets
├── favicon-truck-pms.png   # Browser tab icon
├── stmiet-trans-logo.png   # Company logo
├── stpc-trans-logo.png     # Partner logo
└── sop/
    ├── en.html             # Generated SOP English
    └── tl.html             # Generated SOP Tagalog
```

### CDN Dependencies

- Bootstrap 5.3 CSS + JS
- Bootstrap Icons 1.11.3
- Google Fonts (Inter)

### Conventions

- CSS uses custom properties (`--sidebar-width`, `--primary-color`, etc.) for theming
- All JavaScript is intentionally kept minimal — no framework beyond Bootstrap
- Templates use BEM-like class naming with Bootstrap utility classes
- Sidebar is fully responsive (collapsible on desktop, drawer on mobile)

---

## 15. Testing

### Test Suite

- **88 tests total** in two files:
  - `joborders/tests.py` — model tests + view tests + E2E tests
  - `training/tests.py` — model tests

### Running Tests

```bash
cd truck_pms
$env:DJANGO_SECRET_KEY='test-key'
python manage.py test joborders.tests training.tests
```

### Test Coverage Areas

- User creation and role assignment
- Truck CRUD and PM schedule auto-creation
- Truck import/export CSV
- Job Order CRUD, close-flow, line items, parts
- PM schedule status calculation (MILEAGE, CALENDAR, VISUAL, INACTIVE)
- Direct PM completion (✅ Mark Complete)
- Service log creation and parts tracking
- Role-based access (every view tested per role)
- KPI views
- Training module
- Login/redirect behavior by role

---

## 16. Deployment

### Production Environment (Render)

Render deployment uses the settings in `truck_pms/Procfile`:

```
web: gunicorn truck_pms.wsgi --log-file -
```

**Build Command:**
```
pip install -r requirements.txt
  && python manage.py collectstatic --noinput
  && python manage.py migrate
  && python manage.py seed_data
  && python manage.py build_sop
```

**Important:** `seed_data` is **idempotent** — it checks for existing users/trucks before creating. Running it on every deploy ensures new seed data is applied without duplicating existing records.

### Environment Variables (Production)

| Variable | Value Example |
|----------|--------------|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` |
| `DJANGO_SECRET_KEY` | Long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com,localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com,http://localhost` |

---

## 17. Common Maintenance Tasks

### Adding a New PM Category

1. Create a `TaskCategory` via Sidebar → Preventive Maintenance → PM Categories (Admin+)
2. Create `TaskTemplate` records under the new category
3. Run `python manage.py sync_pm` or use the "Sync PM" button on the PMS Schedules page
4. Add the corresponding SOP procedure in `sop/templates/sop/en/` and `sop/templates/sop/tl/`
5. Regenerate SOP: `python manage.py build_sop`

### Adding a New Truck Field

1. Add field to `Truck` model in `trucks/models.py`
2. Create and run migration: `python manage.py makemigrations && python manage.py migrate`
3. Add field to `TruckForm` in `trucks/forms.py`
4. Add field to the CSV import mapping in `trucks/forms.py` (`IMPORT_FIELDS`)
5. Add field display to `trucks/templates/trucks/detail.html` and `trucks/templates/trucks/list.html`
6. Update the truck detail template and export CSV view

### Updating Mileage/Engine Hours

Two methods:
1. **Batch** (recommended): Sidebar → Fleet → Update Mileage — enter all active trucks at once
2. **Quick**: Truck detail page → inline form at top of Truck Details card

Both methods are restricted to Staff, Admin, and Super Admin.

### Regenerating the SOP Manual

```bash
cd truck_pms
python manage.py build_sop
```

This regenerates `static/sop/en.html` and `static/sop/tl.html`. The templates are in `sop/templates/sop/`.

### Seeding New Data

The `seed_data` command creates:
- 8 user accounts (if they don't exist)
- PM categories and templates (if they don't exist)
- Sample trucks (if none exist)
- PM schedules for all trucks

It is safe to re-run — it checks for existing records before creating.

### Collecting Static Files

```bash
cd truck_pms
python manage.py collectstatic --noinput
```

---

## Quick Reference

### Useful Commands

```bash
python manage.py check                          # System check
python manage.py test joborders.tests training.tests  # Run tests
python manage.py show_urls                      # List all URLs
python manage.py shell_plus                     # Django shell (if django-extensions installed)
```

### Docker (Not Yet Implemented)

There is no Dockerfile or docker-compose.yml yet. The project runs natively with Python and SQLite locally, PostgreSQL on Render.
