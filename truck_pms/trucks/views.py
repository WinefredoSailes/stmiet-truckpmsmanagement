from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from accounts.decorators import role_required
from accounts.models import User
from .models import Truck
from .forms import TruckForm
from pms.models import PMSchedule, TaskTemplate, TaskCategory


@login_required
def truck_list(request):
    trucks = Truck.objects.all().order_by('unit_number')
    paginator = Paginator(trucks, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'trucks/list.html', {'page_obj': page_obj, 'trucks': page_obj.object_list})


@login_required
def truck_detail(request, pk):
    truck = get_object_or_404(Truck, pk=pk)
    pm_schedules = PMSchedule.objects.filter(truck=truck).select_related(
        'task_template__category'
    )
    job_orders = truck.job_orders.select_related(
        'assigned_to', 'created_by', 'contractor'
    ).order_by('-created_at')[:20]
    service_logs = truck.service_logs.select_related(
        'performed_by'
    ).order_by('-performed_at')[:20]
    context = {
        'truck': truck,
        'pm_schedules': pm_schedules,
        'job_orders': job_orders,
        'service_logs': service_logs,
    }
    return render(request, 'trucks/detail.html', context)


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def truck_create(request):
    if request.method == 'POST':
        form = TruckForm(request.POST)
        if form.is_valid():
            truck = form.save()
            templates = TaskTemplate.objects.all()
            for tmpl in templates:
                PMSchedule.objects.get_or_create(
                    truck=truck,
                    task_template=tmpl,
                    defaults={'is_active': True}
                )
            messages.success(
                request,
                f'Truck {truck.unit_number} created with '
                f'{templates.count()} PM schedules.'
            )
            return redirect('trucks:detail', pk=truck.pk)
    else:
        form = TruckForm()
    return render(request, 'trucks/form.html', {
        'form': form, 'title': 'Add Truck'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def truck_update(request, pk):
    truck = get_object_or_404(Truck, pk=pk)
    if request.method == 'POST':
        form = TruckForm(request.POST, instance=truck)
        if form.is_valid():
            form.save()
            messages.success(request, f'Truck {truck.unit_number} updated.')
            return redirect('trucks:detail', pk=truck.pk)
    else:
        form = TruckForm(instance=truck)
    return render(request, 'trucks/form.html', {
        'form': form, 'title': f'Edit {truck.unit_number}'
    })
