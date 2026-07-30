from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from accounts.decorators import role_required
from accounts.models import User
from .models import ServiceLogEntry
from trucks.models import Truck


@login_required
def truck_ledger(request, truck_pk):
    truck = get_object_or_404(Truck, pk=truck_pk)
    today = timezone.localdate()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    action = request.GET.get('action')
    performed_by_id = request.GET.get('performed_by')
    logs = ServiceLogEntry.objects.filter(truck=truck).select_related(
        'performed_by', 'job_order', 'line_item'
    )
    if date_from:
        logs = logs.filter(performed_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(performed_at__date__lte=date_to)
    if action:
        logs = logs.filter(action__icontains=action)
    if performed_by_id:
        logs = logs.filter(performed_by_id=performed_by_id)
    logs = logs.order_by('-performed_at')
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    performers = User.objects.filter(
        service_log_entries__truck=truck
    ).distinct().order_by('username')
    return render(request, 'service_log/truck_ledger.html', {
        'truck': truck,
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'selected_action': action or '',
        'selected_performed_by': performed_by_id,
        'performers': performers,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def full_ledger(request):
    truck_id = request.GET.get('truck')
    action = request.GET.get('action')
    performed_by_id = request.GET.get('performed_by')
    today = timezone.localdate()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    logs = ServiceLogEntry.objects.select_related(
        'truck', 'performed_by', 'job_order'
    )
    if truck_id:
        logs = logs.filter(truck_id=truck_id)
    if action:
        logs = logs.filter(action__icontains=action)
    if performed_by_id:
        logs = logs.filter(performed_by_id=performed_by_id)
    if date_from:
        logs = logs.filter(performed_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(performed_at__date__lte=date_to)
    logs = logs.order_by('-performed_at')
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    trucks = Truck.objects.all().order_by('unit_number')
    performers = User.objects.filter(
        service_log_entries__isnull=False
    ).distinct().order_by('username')
    return render(request, 'service_log/full_ledger.html', {
        'page_obj': page_obj, 'logs': page_obj.object_list,
        'trucks': trucks,
        'selected_truck': truck_id,
        'selected_action': action or '',
        'selected_performed_by': performed_by_id,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'performers': performers,
    })
