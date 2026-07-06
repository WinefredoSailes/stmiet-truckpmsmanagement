from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from accounts.decorators import role_required
from accounts.models import User
from joborders.models import JobOrder, JobOrderLineItem, LineItemPart
from pms.models import PMSchedule, TaskTemplate
from service_log.models import ServiceLogEntry
from trucks.models import Truck


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def mechanic_kpi(request):
    mechanics = User.objects.filter(
        role__in=[User.Role.MECHANIC, User.Role.ADMIN, User.Role.STAFF]
    )
    data = []
    for mech in mechanics:
        completed_jobs = JobOrder.objects.filter(
            assigned_to=mech, status='CLOSED'
        )
        total_completed = completed_jobs.count()
        total_labor = ServiceLogEntry.objects.filter(
            performed_by=mech
        ).aggregate(
            total_hours=Sum('labor_hours'),
            total_cost=Sum('parts_cost')
        )
        data.append({
            'mechanic': mech,
            'total_completed': total_completed,
            'total_labor_hours': total_labor['total_hours'] or 0,
            'total_parts_cost': total_labor['total_cost'] or 0,
        })
    return render(request, 'kpi/mechanic.html', {'data': data})


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def contractor_kpi(request):
    from contractors.models import Contractor
    contractors = Contractor.objects.filter(is_active=True)
    data = []
    for c in contractors:
        jobs = JobOrder.objects.filter(contractor=c)
        total_jobs = jobs.count()
        completed = jobs.filter(status='CLOSED').count()
        open_jobs = jobs.filter(status='OPEN').count()
        data.append({
            'contractor': c,
            'total_jobs': total_jobs,
            'completed': completed,
            'open': open_jobs,
        })
    return render(request, 'kpi/contractor.html', {'data': data})


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def truck_frequency(request):
    truck_id = request.GET.get('truck')
    trucks = Truck.objects.all().order_by('unit_number')
    if truck_id:
        trucks = trucks.filter(pk=truck_id)
    data = []
    for truck in trucks:
        logs = ServiceLogEntry.objects.filter(truck=truck)
        total_services = logs.count()
        total_cost = logs.aggregate(c=Sum('parts_cost'))['c'] or 0
        total_hours = logs.aggregate(h=Sum('labor_hours'))['h'] or 0
        top_actions = logs.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        job_types = JobOrder.objects.filter(
            truck=truck
        ).values('job_type').annotate(
            count=Count('id')
        ).order_by('-count')
        data.append({
            'truck': truck,
            'total_services': total_services,
            'total_cost': total_cost,
            'total_hours': total_hours,
            'top_actions': top_actions,
            'job_types': job_types,
        })
    return render(request, 'kpi/truck_frequency.html', {
        'data': data,
        'trucks': Truck.objects.all().order_by('unit_number'),
        'selected_truck': truck_id,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def predictive_analytics(request):
    # ── Failure Frequency ──────────────────────────────────
    breakdowns = JobOrder.objects.filter(
        job_type='BREAKDOWN', status='CLOSED'
    ).values('truck__unit_number').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    failure_labels = [b['truck__unit_number'] for b in breakdowns]
    failure_counts = [b['count'] for b in breakdowns]

    # ── PM Compliance Rate & Overdue (one pass) ────────────
    all_schedules = list(PMSchedule.objects.filter(
        is_active=True
    ).exclude(
        task_template__interval_type='VISUAL'
    ).select_related('truck', 'task_template'))
    total_pm = len(all_schedules)
    overdue_pm = ok_pm = due_pm = 0
    truck_overdue = {}
    for s in all_schedules:
        st = s.status()
        if st == 'overdue':
            overdue_pm += 1
            truck_overdue[s.truck.unit_number] = truck_overdue.get(s.truck.unit_number, 0) + 1
        elif st == 'ok':
            ok_pm += 1
        elif st == 'due':
            due_pm += 1
    no_data_pm = total_pm - overdue_pm - ok_pm - due_pm
    overdue_sorted = sorted(truck_overdue.items(), key=lambda x: x[1], reverse=True)
    overdue_trucks = [t for t, c in overdue_sorted[:10]]
    overdue_counts = [c for t, c in overdue_sorted[:10]]

    # ── Cost Trends (last 6 months) ────────────────────────
    six_months_ago = timezone.now() - timedelta(days=180)
    cost_data = ServiceLogEntry.objects.filter(
        performed_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('performed_at')
    ).values('month').annotate(
        parts=Sum('parts_cost'),
        hours=Sum('labor_hours')
    ).order_by('month')
    cost_labels = []
    parts_cost = []
    labor_cost = []
    for c in cost_data:
        cost_labels.append(c['month'].strftime('%b %Y') if c['month'] else '')
        parts_cost.append(float(c['parts'] or 0))
        labor_cost.append(float(c['hours'] or 0) * 250)

    # ── Most Replaced Parts ────────────────────────────────
    top_parts = LineItemPart.objects.values('part_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    part_labels = [p['part_name'] for p in top_parts]
    part_counts = [p['count'] for p in top_parts]

    return render(request, 'kpi/predictive.html', {
        'failure_labels': failure_labels,
        'failure_counts': failure_counts,
        'total_pm': total_pm,
        'ok_pm': ok_pm,
        'overdue_pm': overdue_pm,
        'due_pm': due_pm,
        'no_data_pm': no_data_pm,
        'cost_labels': cost_labels,
        'parts_cost': parts_cost,
        'labor_cost': labor_cost,
        'overdue_trucks': overdue_trucks,
        'overdue_counts': overdue_counts,
        'part_labels': part_labels,
        'part_counts': part_counts,
    })
