from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from accounts.decorators import role_required
from accounts.models import User
from .models import ServiceLogEntry
from trucks.models import Truck


@login_required
def truck_ledger(request, truck_pk):
    truck = get_object_or_404(Truck, pk=truck_pk)
    logs = ServiceLogEntry.objects.filter(truck=truck).select_related(
        'performed_by', 'job_order', 'line_item'
    ).order_by('-performed_at')
    return render(request, 'service_log/truck_ledger.html', {
        'truck': truck, 'logs': logs
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def full_ledger(request):
    truck_id = request.GET.get('truck')
    action = request.GET.get('action')
    logs = ServiceLogEntry.objects.select_related(
        'truck', 'performed_by', 'job_order'
    ).all()
    if truck_id:
        logs = logs.filter(truck_id=truck_id)
    if action:
        logs = logs.filter(action__icontains=action)
    logs = logs.order_by('-performed_at')
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    trucks = Truck.objects.all().order_by('unit_number')
    return render(request, 'service_log/full_ledger.html', {
        'page_obj': page_obj, 'logs': page_obj.object_list,
        'trucks': trucks,
        'selected_truck': truck_id,
        'selected_action': action,
    })
