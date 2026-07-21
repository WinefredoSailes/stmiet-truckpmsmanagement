# System Orientation Guide — Truck PMS & Servicing

> Use this as your speaking outline. Items marked **🎯 Demo** = stop and show live on screen.

---

## 1. Opening (2 min)

**What this system is:**
- One place to manage our entire fleet's maintenance
- No more paper logs, whiteboards, or spreadsheets
- Tracks: PM schedules, repairs, parts, contractor work, and OJT training

**Key idea:** Every truck has ~154 PM tasks assigned to it. The system tells you what's due, when, and on which truck.

---

## 2. Logging In (3 min)

**🎯 Demo:** Open the login page, log in as `admin`.

- URL sent to each user individually
- Each role sees a **different sidebar**
- Your username and role badge appear in the top bar

| Role | After login you land on... |
|------|---------------------------|
| Admin / Staff / Mechanic | Main Dashboard |
| Contractor | My Assignments |
| OJT / Trainee | Training Dashboard |

---

## 3. Dashboard — The Home Screen (3 min)

**🎯 Demo:** Show the dashboard.

What you see at a glance:
- **Open job orders** count
- **Active trucks** count
- **Overdue & due PM** alerts (red/yellow badges)
- **Recent jobs** — last 10 created

> "This is your morning checkpoint. Check overdue PM first."

---

## 4. Trucks (3 min)

**🎯 Demo:** Click Trucks → pick a truck.

Each truck has:
- Basic info (plate, make, model, mileage, engine hours)
- Certificate of Registration (CR) fields
- **PM Schedule** — list of all 154 tasks with status badges
- **Job Orders** — recent work done
- **Service History** — audit log

**Status badges:**
| Color | Meaning |
|-------|---------|
| 🟢 OK | Not yet due |
| 🟡 DUE | Within 10% of interval |
| 🔴 OVERDUE | Past the interval |
| 🔵 VISUAL | Visual check (no auto-schedule) |
| ⚫ NO DATA | Never completed |

---

## 5. Recording PM Completion — The Short Way (5 min)

> **🎯 Demo:** Go to a truck detail → click ✅ on "Change Oil" → show form → submit → refresh to show updated status.

This is the feature added for us:

1. Go to **Truck Detail** or **PM Schedule List**
2. Find the task → click the green **✅**
3. The form shows:
   - Truck & task name (read-only)
   - **Completed At** — pre-filled to now
   - **Mileage** — pre-filled from truck's current reading
   - **Engine Hours** — pre-filled from truck's current reading
4. Click **Mark Complete** → done

**Who can do this:** Admin, Staff, Super Admin

> "For daily PM tasks like oil change, filter change, belt inspection — just find it and check it off. 10 seconds."

---

## 6. Job Orders — The Full Workflow (7 min)

**🎯 Demo:** Create a JO → add line items → show mechanic view → close JO.

Use this when you need:
- A mechanic assigned to do the work
- Parts tracking
- An audit trail of who did what

**Flow:**
1. **Staff/Admin** creates JO → selects truck, type, assigns mechanic
2. Adds **line items** (tasks to do)
3. **Mechanic** logs in → **My Assignments** → sees the JO
4. Mechanic marks each line item **DONE**, logs hours & parts
5. **Staff/Admin** reviews → clicks **Close Job Order**
6. System auto-updates PM schedules + writes to **Service Ledger**

**Job types:**
| Type | Use when... |
|------|------------|
| **PM** | Scheduled maintenance (oil change, greasing, etc.) |
| **Repair** | Something broke (leak, no start, vibration) |
| **Inspection** | Visual check, pre-trip, annual |
| **Contractor Service** | Outsourced work (welding, calibration) |

> "The short ✅ button is for quick recording. The JO workflow is for when work needs assigning, tracking, and parts logging."

---

## 7. PM Schedules Page (2 min)

**🎯 Demo:** Go to PM Schedule list → filter by truck → show ✅ and edit buttons.

- Full list of every task on every truck
- **Filter** by truck, status, or search by task/category name
- Each row shows: interval, last done, next due, status
- ✅ = Mark Complete (staff+)
- ✏️ = Edit (admin only) — for adjusting past dates

---

## 8. KPI & Reports (for Admins) (3 min)

**🎯 Demo:** Show KPI Reports and Predictive Analytics.

Mechanic KPI:
- Jobs completed, labor hours, parts cost per person

Truck Frequency:
- How often each truck is serviced, top actions, cost breakdown

Predictive Analytics:
- Charts: failure frequency, PM compliance, cost trends, overdue alerts, top replaced parts

Trainee KPIs:
- Weighted score: attendance (50%) + on-time (10%) + ratings (20%) + reviews (20%)
- Holiday-aware attendance rate
- Trend charts for ratings & reviews

---

## 9. OJT / Training Module (5 min)

### For Trainees

**🎯 Demo:** Log in as `jose` → show Training Dashboard.

- **Check In** when you arrive → **Check Out** when you leave
- View your **ratings** given by supervisor
- View **weekly reviews**
- **My KPIs** — see your weighted score, attendance rate, streak

### For Supervisors (Staff/Admin)

**🎯 Demo:** Log in as `admin` → show Training Dashboard / Trainee KPIs.

- See your active OJTs
- **New Rating** — rate a trainee on a specific task (1-5)
- **New Review** — weekly evaluation
- **Trainee KPIs** — drill into any trainee's performance

---

## 10. SOP Manual (2 min)

**🎯 Demo:** Click SOP Manual in sidebar → show PDF download + HTML view.

- **8 volumes** covering every procedure
- Each PM task has: required tools, PPE, step-by-step instructions
- Available in English and Filipino
- If PDF isn't generated, use **Ctrl+P → Save as PDF**

> "All the step-by-step procedures — how to change oil, what tools you need, safety protocols — are in this manual. Not in the README."

---

## 11. Quick Reference by Role

| Role | What you'll do daily |
|------|---------------------|
| **Admin** | Monitor dashboard, assign JOs, review KPI, manage PM, supervise OJTs |
| **Staff** | Create JOs, close JOs, ✅ mark PM complete, supervise OJTs |
| **Mechanic** | Check **My Assignments**, update line items, log parts |
| **Contractor** | Same as mechanic — see only your assigned JOs |
| **OJT / Trainee** | Check in/out, check My KPIs, review ratings |

---

## 12. Common Tasks Cheat Sheet

| I want to... | What I do |
|-------------|-----------|
| Record that oil change was done | Truck Detail → ✅ button → Mark Complete |
| Assign a repair to Pedro | Job Orders → New JO → select Pedro → add line items |
| See what's overdue today | Dashboard → check red overdue PM list |
| See how many jobs Miguel finished | KPI Reports → Mechanic KPI |
| Check in as OJT | Training Dashboard → Check In |
| Rate an OJT's performance | Training → New Rating |
| Find the procedure for brake inspection | SOP Manual → search for "Brakes" |
| Print the PM checklist for T-001 | Truck Detail → PM Schedule → Print button |

---

## 13. Walk-Through Exercise (10 min)

**🎯 Have each person do this on their own device:**

1. Log in with their account
2. **Everyone:** Find Truck T-001, see its PM schedule
3. **Admins/Staff:** Click ✅ on any DUE task, submit
4. **Mechanics:** Go to My Assignments
5. **Trainees:** Check in, then check out, then open My KPIs
6. **Everyone:** Open SOP Manual, browse a volume

---

## Tips for a Smooth Presentation

- **Before starting:** Have 2 browser tabs open — one logged in as admin, one as a trainee
- **Use the split screen:** Show the sidebar, then click each section
- **Keep it simple:** Don't explain all 154 tasks. Just show that they exist and that status colors tell the story
- **Emphasize the ✅ button:** That's the biggest UX change — it's the quickest way to record work
- **For trainees:** Show them My KPIs and explain the 50/10/20/20 scoring — they'll care about that
