# Truck PMS & Servicing System

A Django-based Preventive Maintenance System for fuel tanker fleet management. Tracks repair/PMS history, job orders, contractor services, and mechanic KPI.

---

## Setup Guide

### Requirements
- Python 3.11+
- pip

### Installation

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

# 6. Seed initial data
python manage.py seed_data

# 7. Start server
python manage.py runserver 0.0.0.0:8000
```

### Default Accounts

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Super Admin |
| `miguel` | `password123` | Admin |
| `juan` | `password123` | Staff |
| `pedro` | `password123` | Mechanic |
| `andres` | `password123` | Mechanic |
| `contractor1` | `password123` | Contractor |

### Quick Start Script

```powershell
# Windows — run from project root
.\start.ps1
```

---

## User Guide

### 1. Roles & Access

| Role | Permissions |
|---|---|
| **Super Admin** | Full system access + User Management + Django admin (`/admin/`) |
| **Admin** | All except User Management. Can create/edit trucks, PM configs, contractors, view KPI |
| **Staff** | Create and manage job orders, view PM schedules |
| **Mechanic** | Views only assigned job orders. Can mark line items as Done, log hours/parts |
| **Contractor** | Same as Mechanic but limited to contractor-assigned JOs |

### 2. Fleet Management (Trucks)

**Navigation:** Sidebar → Trucks

- **Add Truck** — Register a new fuel tanker. Auto-creates all 45 PM schedules.
- **Edit Truck** — Update specs, mileage, engine hours, status (Active/Down/Retired).
- **Truck Detail** — Shows:
  - Specs (make, model, tank capacity, etc.)
  - PM Schedule status per task (OK / Due / Overdue / Visual)
  - Job Order history
  - Service history log

### 3. Preventive Maintenance Scheduling

**Navigation:** Sidebar → PMS Schedules

#### Task Categories & Templates

Defined in **PMS Schedules > Categories** and **Templates**:
- **23 categories** — Engine PM, Brakes, Tires, Tank Integrity, Valves, Vapor Recovery, etc.
- **45 task templates** — Each has:
  - **Interval types:** Mileage (km), Engine Hours, Calendar (days), Visual Inspection
  - **Values:** e.g., Oil change every 5,000 km; Tank test every 365 days
  - **Specialist flag:** Some tasks require electricians, welders, etc.

#### Schedule Management

- Each truck has its own PMSchedule for every template.
- Status auto-calculates:
  - **OK** — not yet due
  - **Due** — within 10% of interval
  - **Overdue** — past interval
  - **Visual** — visual inspection (no auto-schedule)
  - **No Data** — never completed
- **Sync All Trucks** button on PM Schedules page — applies any new templates to all trucks
- **Refresh icon** on truck detail — syncs just that truck

### 4. Job Orders

**Navigation:** Sidebar → Job Orders

#### States (3-state workflow)

```
Open → In Progress → Closed
```

#### Creating a Job Order

1. Click **New Job Order**
2. Select **Truck**, enter **Title/Description**
3. Set **Type**: PM / Repair / Inspection / Contractor Service
4. Set **Priority**: Low / Medium / High / Emergency
5. **Assign To**: Select a mechanic, or for Contractor type select a contractor company
6. Save → Add line items on the detail page

#### Line Items

Each JO can have multiple line items:
- **Task** description
- **Category** (Engine PM, Brakes, etc.)
- **Estimated / Actual hours**
- **Status**: Pending → In Progress → Done
- **Parts**: Add part name, quantity, unit cost

#### Mechanics / Contractors Flow

1. User assigned to a JO sees it in **My Assignments**
2. Opens JO → clicks green checkmark on a line item → marks Done, logs actual hours
3. Clicks box icon → adds parts used

#### Closing a Job Order

1. Admin/Staff opens the JO → clicks **Close Job Order**
2. Auto-closes all pending line items
3. Records current truck mileage/engine hours
4. Auto-updates PM schedules (resets next due)
5. Logs everything to Service History

### 5. Contractors

**Navigation:** Sidebar → Contractors

Register external service providers:
- Company name, contact person, mobile, email
- Skills/services (comma-separated)
- Track all JOs assigned to each contractor

### 6. Service Ledger

**Navigation:** Sidebar → Service Ledger

Immutable audit trail of every action:
- Filter by truck and action type
- View full history or per-truck from truck detail
- Shows: Date, Truck, JO#, Action, Description, Performed By, Labor Hours, Parts Cost

### 7. KPI Reports

**Navigation:** Sidebar → KPI Reports

| Report | What it shows |
|---|---|
| **Mechanic KPI** | Workers, specialization, jobs completed, total labor hours, parts cost |
| **Contractor KPI** | Companies, total jobs, completed vs open, completion rate |
| **Truck Frequency** | Per-truck: service count, cost, labor hours, most frequent actions, job type breakdown |

### 8. User Management (Super Admin only)

**Navigation:** Sidebar → User Management

- Create / Edit users
- Filter by role
- **Password reset** → click key icon → redirects to Django admin
- Roles: Super Admin, Admin, Staff, Mechanic, Contractor

### 9. Django Admin

**URL:** `http://127.0.0.1:8000/admin/` (Super Admin only)

Full CRUD for all models — use this for:
- Password resets
- Bulk operations
- Direct database management

---

## Architecture

### Apps

| App | Purpose |
|---|---|
| `accounts` | Custom User model with roles (SUPER_ADMIN, ADMIN, STAFF, MECHANIC, CONTRACTOR) |
| `trucks` | Truck/fleet asset management |
| `pms` | Task categories, task templates, per-truck PM schedules |
| `joborders` | Job Orders, line items, parts tracking |
| `service_log` | Immutable audit trail of all work done |
| `contractors` | External vendor registry |
| `kpi` | Computed tabular reports |
| `core` | Base template, shared CSS, form mixin |

### Key Models

```
TaskCategory ──1:N── TaskTemplate ──1:N── PMSchedule ──N:1── Truck
                                                    │
JobOrder ──1:N── JobOrderLineItem ──1:N── LineItemPart
    │
    └──1:N── ServiceLogEntry
```

### Tech Stack

- **Backend:** Django 6.0 + SQLite
- **Frontend:** Django Templates + Bootstrap 5.3 + Bootstrap Icons
- **Font:** Inter (Google Fonts)
- **CSS:** Custom stylesheet with CSS variables
