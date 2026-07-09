# Truck PMS & Servicing System — User Guide

> **For:** Super Admins, Admins, Staff, Mechanics, Contractors, and OJTs/Trainees
>
> **Purpose:** Standard Operating Procedures (SOP) reference for daily fleet maintenance operations

---

## Table of Contents

1. [Roles & Access](#1-roles--access)
2. [Dashboard](#2-dashboard)
3. [Fleet Management (Trucks)](#3-fleet-management-trucks)
4. [Preventive Maintenance Scheduling](#4-preventive-maintenance-scheduling)
5. [Job Orders](#5-job-orders)
6. [Service Ledger](#6-service-ledger)
7. [Contractors](#7-contractors)
8. [KPI & Predictive Analytics](#8-kpi--predictive-analytics)
9. [OJT / Training Management](#9-ojt--training-management)
10. [User Management](#10-user-management-super-admin-only)
11. [Django Admin](#11-django-admin-super-admin-only)
12. [Common Tasks](#12-common-tasks)

---

## 1. Roles & Access

### Role Overview

| Role | Description | Sidebar Menu |
|---|---|---|
| **Super Admin** | Full system ownership. Can manage users, everything. | Dashboard, Trucks, PMS Schedules, PM Categories, PM Templates, Job Orders, Service Ledger, Contractors, KPI Reports, Predictive Analytics, User Management, Training, Assign Training |
| **Admin** | Operations manager. Can do everything except user management. | Same as Super Admin minus User Management + Assign Training |
| **Staff** | Shop floor supervisor. Creates/manages job orders, supervises OJTs. | Dashboard, Trucks, PMS Schedules, PM Categories, PM Templates, Job Orders, Service Ledger, Contractors, KPI Reports, Predictive Analytics, Training |
| **Mechanic** | Technician assigned to jobs. Can only see their own assignments. | Dashboard, Trucks, Job Orders, My Assignments |
| **Contractor** | External vendor. Same as Mechanic but limited to contractor JOs. | Trucks, My Assignments |
| **OJT / Trainee** | Under training. Checks in/out, views ratings and reviews. | Dashboard, Trucks, Training |

### Login Behavior by Role

| Role | After Login |
|---|---|
| Super Admin, Admin, Staff, Mechanic | Redirected to main Dashboard |
| Contractor | Redirected straight to **My Assignments** |
| OJT / Trainee | Redirected straight to **Training Dashboard** |

---

## 2. Dashboard

**Access:** All roles (sidebar → Dashboard)

The dashboard shows a quick-status overview:

- **Open Job Orders** count
- **Active Trucks** count
- **My Assigned Jobs** (for mechanics/contractors)
- **Overdue/Due PM** list — quick view of what needs attention
- **Recent Job Orders** — last 10 created

---

## 3. Fleet Management (Trucks)

**Access:** All roles
**Navigation:** Sidebar → Trucks

### Viewing Trucks

- The **Truck List** shows all registered trucks with plate number, make/model, status, mileage, engine hours.
- Click a truck to open its **Detail Page**.

### Truck Detail Page Layout

```
┌─────────────────────────┬─────────────────────────┐
│    TRUCK DETAILS        │    CERTIFICATE OF       │
│    Plate, Make, Model   │    REGISTRATION         │
│    Mileage, Status, etc.│    MV File, CR, OR, etc.│
├─────────────────────────┼─────────────────────────┤
│    PM SCHEDULE          │    JOB ORDERS           │
│    (list with status)   │    (recent JOs)         │
│                         ├─────────────────────────┤
│                         │    SERVICE HISTORY      │
│                         │    (recent logs)        │
└─────────────────────────┴─────────────────────────┘
```

### Adding a Truck

1. **Who:** Admin or Super Admin
2. Click **"Add Truck"** on the Truck List page
3. Fill in:
   - **Required:** Unit Number, Plate Number, Make, Model, Year
   - **Optional:** Chassis #, Engine #, Tank Capacity, Fuel Type, Status
   - **CR Fields** (Certificate of Registration — all optional): MV File No., CR/OR Numbers, Piston Displacement, Weight specs, LTO Address, etc.
4. Click **Save**
5. System **auto-creates 154 PM schedules** for the new truck

### Editing a Truck

1. Open truck detail page
2. Click **Edit** button
3. Update any fields
4. Click **Save**

### Truck Status

| Status | Meaning |
|---|---|
| **Active** | Truck is operational |
| **Down** | Currently out of service / under repair |
| **Retired** | Permanently decommissioned |

---

## 4. Preventive Maintenance Scheduling

**Access:** Staff+ (view), Admin+ (configure)
**Navigation:** Sidebar → PMS Schedules, PM Categories, PM Templates

### Task Categories & Templates

The system has **23 categories** and **154 task templates** covering:

| Category Group | Examples |
|---|---|
| Engine PM | Oil change, coolant flush, radiator hoses, belt inspection |
| Brakes | Brake lining, drum/disc inspection, air brake adjustment |
| Tires | Tire condition, tread depth, pressure |
| Tank & Valves | Overfill prevention, manlid gaskets, API adapters, camlocks |
| Vapor Recovery | Vapor recovery system, grounding, static discharge |
| Hoses & Couplings | Product piping, hoses, couplings |
| Safety | Horn, reflective tape, compartment labels, first aid, fall arrest |
| Electrical | Battery, alternator, starter, wiring/sensors |
| Lighting | Headlight, taillight, brake light, signal light, clearance light |
| Compliance | DOST stickers, HAZMAT placards, depot access, driver accreditation |
| Drivetrain | Differential, U-joints, wheel bearings |
| Water Brake | Water brake system (4 items) |
| And more... | HVAC, Hydraulics, Suspension, Exhaust, Body & Chassis |

### Interval Types

| Type | Based On | Example |
|---|---|---|
| **MILEAGE** | Odometer reading | Oil change every 5,000 km |
| **HOURS** | Engine hours | Belt inspection every 500 hrs |
| **CALENDAR** | Days since last done | Tank test every 365 days |
| **VISUAL** | No auto-schedule | Pre-trip inspection (checked manually) |

### PM Schedule Status Colors

| Status | Color | Meaning |
|---|---|---|
| **OK** | Green | Not yet due |
| **DUE** | Yellow | Within 10% of interval |
| **OVERDUE** | Red | Past the interval |
| **VISUAL** | Blue | Visual inspection (no schedule) |
| **NO DATA** | Gray | Never completed |

### How PM Schedules Update

When a **Job Order is Closed**, the system automatically:
1. Records the truck's current mileage/engine hours
2. Updates `last_completed_at`, `last_mileage_km`, `last_engine_hours` on the relevant PM Schedule
3. Recalculates the next due date

### Syncing New Templates

If new templates are added later:
- **Sync All Trucks** button on PMS Schedules page — applies new templates to every truck
- **Refresh icon** on any truck detail page — syncs only that truck

### Searching PM Schedules

Use the search box on the PMS Schedules page to filter by task name or category name. Combine with truck and status filters.

---

## 5. Job Orders

**Access:** All roles
**Navigation:** Sidebar → Job Orders

### 3-State Workflow

```
OPEN ──→ IN PROGRESS ──→ CLOSED
```

### Creating a Job Order

1. **Who:** Admin or Staff
2. Click **"New Job Order"**
3. Fill in:
   - **Truck** — select from dropdown
   - **Title** — brief description
   - **Type:** PM / Repair / Inspection / Contractor Service
   - **Priority:** Low / Medium / High / Emergency
   - **Assign To:** a mechanic (for PM/Repair/Inspection) or a **Contractor** (for Contractor type)
4. Click **Save**
5. You are redirected to the JO Detail page

### Adding Line Items (Tasks)

After creating a JO, add the actual work items:

1. On JO Detail page, click **"Add"** button next to "Line Items"
2. Fill in:
   - **Task Template** (optional — select from PM templates)
   - **Category** (optional)
   - **Description** (what needs to be done)
   - **Estimated Hours**
   - **Notes**
3. Click **Add**
4. Repeat for each task

### Adding Parts to a Line Item

1. On JO Detail page, click the **📦 (box) icon** on a line item row
2. Click **"Add Part"**
3. Enter:
   - **Part Name** (e.g., "Oil Filter", "Brake Pad Set")
   - **Quantity** (how many used)
   - **Unit Cost** (price per piece)
4. Click **Save**
5. The part appears in the expanded section with calculated total cost

> **Note:** Parts can be recorded regardless of source — withdrawn from storage or purchased on the spot. The system tracks cost only, not inventory.

### Mechanic / Contractor Workflow

1. Login → see "My Assignments" in sidebar
2. Click on a JO to open it
3. For each line item you complete:
   - Click the **✅ (green checkmark)** icon
   - Set status to **Done**
   - Enter **Actual Hours** worked
   - Add any notes
4. Click the **📦 box icon** to add parts used
5. Notify admin when all tasks are complete

### Closing a Job Order

1. **Who:** Admin or Staff
2. Open the JO → click **"Close Job Order"**
3. System displays a confirmation prompt with info about consequences
4. On the close form, optionally update:
   - **Completed Mileage** (defaults to truck's current mileage)
   - **Completed Engine Hours** (defaults to truck's current hours)
5. Click **"Close Job Order"** — this is irreversible
6. System automatically:
   - Marks all pending line items as Done
   - Records the JO's completion time
   - Creates a **Service Log Entry** for each line item
   - Updates the truck's **PM Schedule** (resets next due dates)
   - Logs everything to the **immutable Service Ledger**

### Editing a Job Order

- Click **Edit** on JO Detail page
- You can change: truck, title, description, priority, type, assigned person
- **Cannot edit a Closed JO**

### Job Order List Filters

Use the filter bar to narrow by:
- **Status** (Open / In Progress / Closed)
- **Job Type** (PM / Repair / Inspection / Contractor)
- **Truck**

---

## 6. Service Ledger

**Access:** Admin+
**Navigation:** Sidebar → Service Ledger

### What It Is

An **immutable audit trail** of every action performed. Once a JO is closed, all data is written to the service log and cannot be modified or deleted.

### What Gets Logged

| Event | Log Entry |
|---|---|
| Job Order Created | "Job order JO-2026-0001 created" |
| Line Item Done | "Line item: DONE — Oil Change (2.5h)" |
| Job Order Closed | "Job Closed — JO-2026-0001" |
| Mileage/Engine Hours | Recorded at each critical step |

### Viewing

- **Full Ledger** — all entries, filterable by truck and action type
- **Per-Truck Ledger** — accessible from the truck detail page via "Full Ledger" button

---

## 7. Contractors

**Access:** Admin+
**Navigation:** Sidebar → Contractors

### Registering a Contractor

1. Click **"Add Contractor"**
2. Enter: Company Name, Contact Person, Mobile, Email, Address
3. **Skills** — comma-separated list (e.g., "Welding, Calibration, Electrical")
4. Mark as **Active** to allow job order assignment

### Using Contractors in Job Orders

When creating a JO:
1. Set **Type** = "Contractor Service"
2. Select the **Contractor** company (instead of assigning a mechanic)
3. The JO is linked to the contractor for tracking

### Contractor KPI

See [KPI Section](#8-kpi--predictive-analytics).

---

## 8. KPI & Predictive Analytics

**Access:** Admin+
**Navigation:** Sidebar → KPI Reports, Predictive Analytics

### Mechanic / Staff KPI

| Column | Meaning |
|---|---|
| Mechanic | Name and specialization |
| Jobs Completed | Total closed JOs |
| Total Labor Hours | Sum of actual hours logged |
| Total Parts Cost | Sum of parts used |

### Contractor Performance

| Column | Meaning |
|---|---|
| Company | Contractor name |
| Total Jobs | All JOs assigned |
| Completed | Closed JOs |
| Open | Still in progress |

### Truck Service Frequency

Per-truck breakdown:
- Total services performed
- Total cost (parts)
- Total labor hours
- Top 5 most frequent actions
- Job type breakdown (PM vs Repair vs Inspection)

### Predictive Analytics

A Chart.js dashboard with 5 charts:

| Chart | What It Shows |
|---|---|
| **Failure Frequency** | Trucks with the most breakdowns (top 10) |
| **PM Compliance** | Donut chart: OK vs Due vs Overdue vs No Data |
| **Cost Trends** | Monthly parts + labor cost over last 6 months |
| **Overdue Alerts** | Trucks with the most overdue PM items |
| **Top Replaced Parts** | Most frequently used parts (top 10) |

All data is **live** — queries the database on every page load.

---

## 9. OJT / Training Management

**Access:** Varies by feature
**Navigation:** Sidebar → Training, Assign Training

### Overview

The training module allows onboarding OJTs (Trainees) with:
- **Daily attendance** (check-in/check-out)
- **Task ratings** (supervisor rates on specific PM tasks)
- **Weekly reviews** (supervisor evaluation)

### Setup: Assigning an OJT to Training

1. **Who:** Admin or Super Admin
2. First, create the OJT user in **User Management** with role **"OJT / Trainee"**
3. Go to **Sidebar → Assign Training**
4. Select the OJT, their **Supervisor**, and **Start Date**
5. Click **Assign**

### OJT Dashboard (OJT View)

When an OJT logs in, they see:

| Card | What It Shows |
|---|---|
| **Attendance** | Check In / Check Out button (daily). Shows today's time_in and time_out |
| **My Ratings** | Average score across all task ratings + total count |
| **Training Info** | Start date, supervisor name, status |
| **Recent Ratings** | Last 10 task ratings with scores |
| **Weekly Reviews** | Last 5 weekly review summaries |

#### Checking In / Out

1. OJT arrives → click **Check In** (records current time)
2. OJT leaves → click **Check Out** (records time_out)
3. Cannot check in twice on the same day

### Supervisor Dashboard (Supervisor View)

When a supervisor (Staff/Admin) logs in, they see:

| Section | What It Shows |
|---|---|
| **My OJTs** | List of active trainees, click to view profile |
| **Recent Ratings Given** | Last 20 ratings with OJT name and score |
| **Weekly Reviews** | Recent reviews with quick-access to create new |

### Creating a Task Rating

1. **Who:** Supervisor (Staff/Admin)
2. From sidebar or dashboard, click **"New Rating"**
3. Select:
   - **OJT** (your trainee)
   - **Rating** (1-5)
   - **PM Task** (optional — pick from existing 154 templates, or type a custom task name)
   - **Comments** (optional)
4. Click **Save Rating**

### Creating a Weekly Review

1. **Who:** Supervisor (Staff/Admin)
2. Click **"New Review"**
3. Select:
   - **OJT**
   - **Week Start / Week End** dates
   - **Overall Score** (1-5)
   - **Strengths** (text)
   - **Areas for Improvement** (text)
   - **Supervisor Notes**
4. Click **Save Review**

---

## 10. User Management (Super Admin Only)

**Access:** Super Admin only
**Navigation:** Sidebar → User Management

### Features

- **List Users** — shows all users, filterable by role, paginated (50/page)
- **Create User** — set username, password, role, mobile, specialization, employee ID
- **Edit User** — update any user's details (including role changes)
- **Password Reset** — click the key icon → redirects to Django admin for reset

### Roles Available

| Role | When to Use |
|---|---|
| **Super Admin** | System owner (1-2 people max) |
| **Admin** | Operations manager |
| **Staff** | Supervisor / lead mechanic |
| **Mechanic** | Technician |
| **Contractor** | External vendor user account |
| **OJT / Trainee** | Under training |

---

## 11. Django Admin (Super Admin Only)

**URL:** `https://your-site.com/admin/`

Use the Django admin for:
- **Password resets** for any user
- **Bulk operations** (update multiple records)
- **Direct database editing** (when UI doesn't have the option)
- **Viewing raw data**

---

## 12. Common Tasks

### "I need to record a repair job"

1. Sidebar → Job Orders → **New Job Order**
2. Select truck, type = **Repair**, assign a mechanic
3. Save → on the detail page, click **Add** line items
4. Add each task (e.g., "Replace brake pads", "Resurface rotor")
5. Inform the mechanic
6. Mechanic logs in → **My Assignments** → marks tasks Done + adds parts
7. Admin/Staff → opens JO → **Close Job Order**

### "I need to run a PM schedule report"

1. Sidebar → **PMS Schedules**
2. Optionally filter by truck, status, or search by task name
3. Click **Print** for browser-printable landscape view
4. Click **CSV Export** for spreadsheet download

### "I need to see what work was done on a truck"

1. Sidebar → **Trucks** → click the truck
2. Two ways:
   - **Job Orders** section (right column) — recent JOs
   - **Service History** section (right column) — recent logs
3. Click **Full Ledger** for the complete history

### "I need to onboard a new OJT"

1. Sidebar → **User Management** → **Add User**
2. Set role = **OJT / Trainee**
3. Sidebar → **Assign Training**
4. Select the OJT, pick a supervisor, set start date
5. Inform supervisor to check their **Training** dashboard

### "A PM task was done but not through a JO"

1. Sidebar → **PMS Schedules** → search for the task → click the pencil icon to edit
2. Update `last_completed_at`, `last_mileage_km`, or `last_engine_hours` manually
3. The system recalculates the next due date automatically

### "I want to see how my mechanics are performing"

1. Sidebar → **KPI Reports** → **Mechanic KPI**
2. Shows: jobs completed, total labor hours, total parts cost per mechanic

### "The server is running slow, what's happening?"

Check the **terminal/console logs** for timing output from `RequestTimingMiddleware`. It logs:
- Total request duration (ms)
- Database query time (ms)
- Number of queries

Example output:
```
Request: GET /trucks/ took 185ms (DB: 42ms, 8 queries)
```

---

## Keyboard & UI Tips

- **Back buttons** — ← arrow in the topbar returns you to the previous page
- **Page loader** — a thin blue bar animates at the top during navigation
- **Login spinner** — favicon spins while logging in (min 300ms for smoothness)
- **Logout** — click Logout → confirm dialog → favicon spinner with "Logging out..."
- **Mobile** — the sidebar collapses; tap the ☰ icon to expand
- **Pagination** — all list pages show 50 items per page with page controls

---

*Document version 1.0 — July 2026*
