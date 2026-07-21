import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from accounts.decorators import role_required
from accounts.models import User
from trucks.models import Truck
from .models import TaskCategory, TaskTemplate, PMSchedule
from .forms import TaskCategoryForm, TaskTemplateForm, PMScheduleForm
from service_log.models import ServiceLogEntry


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def category_list(request):
    categories = TaskCategory.objects.annotate(
        template_count=Count('templates')
    ).order_by('name')
    return render(request, 'pms/category_list.html', {'categories': categories})


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def category_create(request):
    if request.method == 'POST':
        form = TaskCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created.')
            return redirect('pms:category_list')
    else:
        form = TaskCategoryForm()
    return render(request, 'pms/form.html', {
        'form': form, 'title': 'Add Task Category'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def category_update(request, pk):
    cat = get_object_or_404(TaskCategory, pk=pk)
    if request.method == 'POST':
        form = TaskCategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('pms:category_list')
    else:
        form = TaskCategoryForm(instance=cat)
    return render(request, 'pms/form.html', {
        'form': form, 'title': f'Edit {cat.name}'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def template_list(request):
    templates = TaskTemplate.objects.select_related('category').order_by(
        'category__name', 'name'
    )
    return render(request, 'pms/template_list.html', {'templates': templates})


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def template_create(request):
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task template created.')
            return redirect('pms:template_list')
    else:
        form = TaskTemplateForm()
    return render(request, 'pms/form.html', {
        'form': form, 'title': 'Add Task Template'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def template_update(request, pk):
    tmpl = get_object_or_404(TaskTemplate, pk=pk)
    if request.method == 'POST':
        form = TaskTemplateForm(request.POST, instance=tmpl)
        if form.is_valid():
            form.save()
            messages.success(request, 'Task template updated.')
            return redirect('pms:template_list')
    else:
        form = TaskTemplateForm(instance=tmpl)
    return render(request, 'pms/form.html', {
        'form': form, 'title': f'Edit {tmpl.name}'
    })


@login_required
def schedule_list(request):
    truck_id = request.GET.get('truck')
    status_filter = request.GET.get('status')
    search = request.GET.get('search', '').strip()
    schedules = PMSchedule.objects.select_related(
        'truck', 'task_template__category'
    ).all()
    if truck_id:
        schedules = schedules.filter(truck_id=truck_id)
    if search:
        schedules = schedules.filter(
            Q(task_template__name__icontains=search) |
            Q(task_template__category__name__icontains=search)
        )
    if status_filter:
        filtered = []
        for s in schedules:
            if s.status() == status_filter:
                filtered.append(s)
        schedules_list = filtered
    else:
        schedules_list = list(schedules)
    schedules_list.sort(key=lambda s: s.truck.unit_number)
    paginator = Paginator(schedules_list, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    trucks = Truck.objects.all().order_by('unit_number')
    return render(request, 'pms/schedule_list.html', {
        'page_obj': page_obj,
        'trucks': trucks,
        'selected_truck': truck_id,
        'selected_status': status_filter,
        'search': search,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def schedule_update(request, pk):
    schedule = get_object_or_404(PMSchedule, pk=pk)
    if request.method == 'POST':
        form = PMScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, 'PM schedule updated.')
            return redirect('pms:schedule_list')
    else:
        form = PMScheduleForm(instance=schedule)
    return render(request, 'pms/form.html', {
        'form': form,
        'title': f'Schedule: {schedule.truck.unit_number} - {schedule.task_template.name}'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def schedule_csv(request):
    truck_id = request.GET.get('truck')
    status_filter = request.GET.get('status')
    search = request.GET.get('search', '').strip()
    schedules = PMSchedule.objects.select_related(
        'truck', 'task_template__category'
    ).all()
    if truck_id:
        schedules = schedules.filter(truck_id=truck_id)
    if search:
        schedules = schedules.filter(
            Q(task_template__name__icontains=search) |
            Q(task_template__category__name__icontains=search)
        )
    if status_filter:
        filtered = []
        for s in schedules:
            if s.status() == status_filter:
                filtered.append(s)
        schedules_list = filtered
    else:
        schedules_list = list(schedules)
    schedules_list.sort(key=lambda s: s.truck.unit_number)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pm_schedules.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Truck', 'Task', 'Category', 'Interval', 'Last Completed',
        'Next Due', 'Status', 'Mechanic Remarks'
    ])
    now = timezone.now()
    for s in schedules_list:
        if s.task_template.interval_type == 'MILEAGE':
            interval = f"{s.task_template.interval_value} km"
            nxt = s.next_due_mileage()
            next_due = f"{nxt} km" if nxt else ''
        elif s.task_template.interval_type == 'HOURS':
            interval = f"{s.task_template.interval_value} hrs"
            nxt = s.next_due_hours()
            next_due = f"{nxt} hrs" if nxt else ''
        elif s.task_template.interval_type == 'CALENDAR':
            interval = f"{s.task_template.interval_value} days"
            nxt = s.next_due_date()
            next_due = nxt.strftime('%Y-%m-%d') if nxt else ''
        else:
            interval = 'Visual'
            next_due = ''
        last_done = s.last_completed_at.strftime(
            '%Y-%m-%d'
        ) if s.last_completed_at else ''
        writer.writerow([
            s.truck.unit_number,
            s.task_template.name,
            s.task_template.category.name,
            interval,
            last_done,
            next_due,
            s.status().upper(),
            ''
        ])
    return response


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def schedule_print(request):
    truck_id = request.GET.get('truck')
    status_filter = request.GET.get('status')
    search = request.GET.get('search', '').strip()
    schedules = PMSchedule.objects.select_related(
        'truck', 'task_template__category'
    ).all()
    if truck_id:
        schedules = schedules.filter(truck_id=truck_id)
    if search:
        schedules = schedules.filter(
            Q(task_template__name__icontains=search) |
            Q(task_template__category__name__icontains=search)
        )
    if status_filter:
        filtered = []
        for s in schedules:
            if s.status() == status_filter:
                filtered.append(s)
        schedules_list = filtered
    else:
        schedules_list = list(schedules)
    schedules_list.sort(key=lambda s: s.truck.unit_number)
    return render(request, 'pms/schedule_print.html', {
        'schedules': schedules_list,
        'now': timezone.now(),
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def schedule_pdf(request):
    truck_id = request.GET.get('truck')
    status_filter = request.GET.get('status')
    search = request.GET.get('search', '').strip()
    schedules = PMSchedule.objects.select_related(
        'truck', 'task_template__category'
    ).all()
    if truck_id:
        schedules = schedules.filter(truck_id=truck_id)
    if search:
        schedules = schedules.filter(
            Q(task_template__name__icontains=search) |
            Q(task_template__category__name__icontains=search)
        )
    if status_filter:
        filtered = []
        for s in schedules:
            if s.status() == status_filter:
                filtered.append(s)
        schedules_list = filtered
    else:
        schedules_list = list(schedules)
    schedules_list.sort(key=lambda s: s.truck.unit_number)
    from core.utils import render_pdf
    return render_pdf(request, 'pms/schedule_print.html', {
        'schedules': schedules_list,
        'now': timezone.now(),
    }, filename=f'pm-schedule-{timezone.now():%Y%m%d}.pdf')


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def sync_truck(request, truck_pk):
    truck = get_object_or_404(Truck, pk=truck_pk)
    templates = TaskTemplate.objects.all()
    created = 0
    for tmpl in templates:
        _, was_created = PMSchedule.objects.get_or_create(
            truck=truck,
            task_template=tmpl,
            defaults={'is_active': True}
        )
        if was_created:
            created += 1
    messages.success(
        request,
        f'Synced {created} PM templates to {truck.unit_number}.'
        f' ({templates.count() - created} already existed)'
    )
    return redirect('trucks:detail', pk=truck_pk)


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def sync_all_trucks(request):
    trucks = Truck.objects.all()
    templates = TaskTemplate.objects.all()
    total_created = 0
    for truck in trucks:
        for tmpl in templates:
            _, was_created = PMSchedule.objects.get_or_create(
                truck=truck,
                task_template=tmpl,
                defaults={'is_active': True}
            )
            if was_created:
                total_created += 1
    messages.success(
        request,
        f'Synced all trucks — {total_created} new schedule(s) created.'
    )
    return redirect('pms:schedule_list')


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def complete_task(request, pk):
    schedule = get_object_or_404(
        PMSchedule.objects.select_related('truck', 'task_template'),
        pk=pk,
    )
    truck = schedule.truck

    if request.method == 'POST':
        import re
        from django.utils.dateparse import parse_datetime

        raw_dt = request.POST.get('completed_at', '')
        if raw_dt:
            dt = parse_datetime(raw_dt)
        else:
            dt = timezone.now()
        mileage = request.POST.get('mileage_km', truck.current_mileage_km)
        hours = request.POST.get('engine_hours', truck.current_engine_hours)

        schedule.last_completed_at = dt
        schedule.last_mileage_km = mileage
        schedule.last_engine_hours = hours
        schedule.save()

        ServiceLogEntry.objects.create(
            truck=truck,
            action=f'PM completed: {schedule.task_template.name}',
            description=(
                f'PM task "{schedule.task_template.name}" marked complete '
                f'for {truck.unit_number} via direct completion.'
            ),
            performed_by=request.user,
            mileage_at=mileage,
            engine_hours_at=hours,
        )

        messages.success(
            request,
            f'"{schedule.task_template.name}" marked complete for '
            f'{truck.unit_number}.'
        )
        next_url = request.POST.get('next', 'pms:schedule_list')
        return redirect(next_url)

    now = timezone.now()
    return render(request, 'pms/complete_form.html', {
        'schedule': schedule,
        'truck': truck,
        'now': now,
    })


