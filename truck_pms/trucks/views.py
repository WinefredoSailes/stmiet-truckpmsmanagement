import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from accounts.decorators import role_required
from accounts.models import User
from .models import Truck
from .forms import TruckForm, TruckImportForm, IMPORT_FIELDS
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
    search = request.GET.get('pm_search', '').strip()
    pm_schedules = PMSchedule.objects.filter(truck=truck).select_related(
        'task_template__category'
    )
    if search:
        pm_schedules = pm_schedules.filter(
            Q(task_template__name__icontains=search) |
            Q(task_template__category__name__icontains=search)
        )
    pm_list = list(pm_schedules)
    if not search:
        pm_list.sort(key=lambda s: (
            'overdue' not in s.status(),
            'due' not in s.status(),
        ))
    job_orders = truck.job_orders.select_related(
        'assigned_to', 'created_by', 'contractor'
    ).order_by('-created_at')[:20]
    service_logs = truck.service_logs.select_related(
        'performed_by'
    ).prefetch_related('parts').order_by('-performed_at')[:20]
    cr_fields = [
        truck.mv_file_no, truck.cr_number, truck.or_number,
        truck.denomination, truck.piston_displacement_cc,
        truck.no_of_cylinders, truck.series, truck.body_type,
        truck.body_no, truck.gross_weight_kg, truck.net_weight_kg,
        truck.shipping_weight_kg, truck.net_capacity_kg,
        truck.field_office_code, truck.lto_registered_address,
    ]
    context = {
        'truck': truck,
        'pm_schedules': pm_list,
        'job_orders': job_orders,
        'service_logs': service_logs,
        'cr_has_data': any(cr_fields),
        'pm_search': search,
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


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def truck_export_csv(request):
    trucks = Truck.objects.all().order_by('unit_number')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="trucks.csv"'
    writer = csv.writer(response)
    writer.writerow(IMPORT_FIELDS)
    for t in trucks:
        row = [getattr(t, f, '') for f in IMPORT_FIELDS]
        writer.writerow(row)
    return response


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def truck_import_csv(request):
    results = None
    if request.method == 'POST':
        form = TruckImportForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data['csv_file']
            file.seek(0)
            decoded = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            created = 0
            updated = 0
            errors = []
            for row_num, row in enumerate(reader, start=2):
                unit = row.get('unit_number', '').strip()
                if not unit:
                    errors.append(f'Row {row_num}: missing unit_number, skipped.')
                    continue
                data = {}
                nullable = {
                    'tank_capacity_liters', 'piston_displacement_cc',
                    'no_of_cylinders', 'gross_weight_kg', 'net_weight_kg',
                    'shipping_weight_kg', 'net_capacity_kg', 'or_expiry',
                }
                integer_fields = {'year', 'current_mileage_km', 'no_of_cylinders'}
                decimal_fields = {
                    'tank_capacity_liters', 'current_engine_hours',
                    'piston_displacement_cc', 'gross_weight_kg',
                    'net_weight_kg', 'shipping_weight_kg', 'net_capacity_kg',
                }
                for f in IMPORT_FIELDS:
                    val = row.get(f, '').strip()
                    if val == '':
                        if f in nullable:
                            data[f] = None
                        elif f == 'current_mileage_km':
                            data[f] = 0
                        elif f == 'current_engine_hours':
                            data[f] = 0
                        else:
                            data[f] = ''
                        continue
                    if f in integer_fields:
                        try:
                            data[f] = int(val)
                        except ValueError:
                            errors.append(f'Row {row_num}: {f} must be an integer, got "{val}".')
                            continue
                    elif f in decimal_fields:
                        try:
                            data[f] = float(val)
                        except ValueError:
                            errors.append(f'Row {row_num}: {f} must be a number, got "{val}".')
                            continue
                    else:
                        data[f] = val
                try:
                    truck, was_created = Truck.objects.update_or_create(
                        unit_number=unit, defaults=data
                    )
                    if was_created:
                        created += 1
                        templates = TaskTemplate.objects.all()
                        for tmpl in templates:
                            PMSchedule.objects.get_or_create(
                                truck=truck, task_template=tmpl,
                                defaults={'is_active': True}
                            )
                    else:
                        updated += 1
                except Exception as e:
                    errors.append(f'Row {row_num}: {e}')
            results = {'created': created, 'updated': updated, 'errors': errors}
            if errors:
                messages.warning(request, f'Import done: {created} created, {updated} updated, {len(errors)} error(s).')
            else:
                messages.success(request, f'Import complete: {created} created, {updated} updated.')
    else:
        form = TruckImportForm()
    return render(request, 'trucks/import.html', {
        'form': form, 'results': results, 'title': 'Import Trucks'
    })
