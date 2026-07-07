from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from accounts.decorators import role_required
from accounts.models import User
from .models import JobOrder, JobOrderLineItem, LineItemPart
from .forms import (JobOrderForm, JobOrderLineItemForm,
                    LineItemPartForm, JobOrderStatusForm,
                    LineItemStatusForm)
from service_log.models import ServiceLogEntry
from pms.models import PMSchedule


@login_required
def job_order_list(request):
    user = request.user
    status = request.GET.get('status')
    job_type = request.GET.get('job_type')
    truck_id = request.GET.get('truck')
    orders = JobOrder.objects.select_related(
        'truck', 'assigned_to', 'contractor'
    )
    if user.role in (User.Role.MECHANIC, User.Role.CONTRACTOR):
        orders = orders.filter(assigned_to=user)
    else:
        orders = orders.all()
    if status:
        orders = orders.filter(status=status)
    if job_type:
        orders = orders.filter(job_type=job_type)
    if truck_id:
        orders = orders.filter(truck_id=truck_id)
    orders = orders.order_by('-created_at')
    paginator = Paginator(orders, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'joborders/list.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'selected_status': status,
        'selected_job_type': job_type,
        'selected_truck': truck_id,
    })


@login_required
def job_order_detail(request, pk):
    order = get_object_or_404(
        JobOrder.objects.select_related(
            'truck', 'assigned_to', 'created_by', 'contractor'
        ),
        pk=pk
    )
    if request.user.role in (User.Role.MECHANIC, User.Role.CONTRACTOR):
        if order.assigned_to != request.user:
            messages.error(request, 'You can only view job orders assigned to you.')
            return redirect('joborders:my_assignments')
    line_items = order.line_items.select_related(
        'category', 'task_template'
    ).prefetch_related('parts')
    logs = order.log_entries.select_related('performed_by').all()
    context = {
        'order': order,
        'line_items': line_items,
        'logs': logs,
    }
    return render(request, 'joborders/detail.html', context)


@login_required
def job_order_print(request, pk):
    order = get_object_or_404(
        JobOrder.objects.select_related(
            'truck', 'assigned_to', 'created_by', 'contractor'
        ),
        pk=pk
    )
    line_items = order.line_items.select_related(
        'category', 'task_template'
    ).prefetch_related('parts')
    logs = order.log_entries.select_related('performed_by').all()
    return render(request, 'joborders/print.html', {
        'order': order,
        'line_items': line_items,
        'logs': logs,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def job_order_create(request):
    if request.method == 'POST':
        form = JobOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            if order.job_type == 'CONTRACTOR':
                order.status = 'OPEN'
            order.save()
            messages.success(
                request,
                f'Job Order {order.jo_number} created.'
            )
            return redirect('joborders:detail', pk=order.pk)
    else:
        form = JobOrderForm()
        truck_id = request.GET.get('truck')
        if truck_id:
            form.fields['truck'].initial = truck_id
    return render(request, 'joborders/form.html', {
        'form': form, 'title': 'Create Job Order'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def job_order_update(request, pk):
    order = get_object_or_404(JobOrder, pk=pk)
    if order.status == 'CLOSED':
        messages.warning(request, 'Cannot edit a closed job order.')
        return redirect('joborders:detail', pk=pk)
    if request.method == 'POST':
        form = JobOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job order updated.')
            return redirect('joborders:detail', pk=pk)
    else:
        form = JobOrderForm(instance=order)
    return render(request, 'joborders/form.html', {
        'form': form,
        'title': f'Edit {order.jo_number}'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def job_order_close(request, pk):
    order = get_object_or_404(JobOrder, pk=pk)
    if request.method == 'POST':
        form = JobOrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            if order.status == 'CLOSED':
                order.completed_at = timezone.now()
                posted_mileage = form.cleaned_data.get('completed_mileage_km')
                posted_hours = form.cleaned_data.get('completed_engine_hours')
                order.completed_mileage_km = (
                    posted_mileage if posted_mileage is not None
                    else order.truck.current_mileage_km
                )
                order.completed_engine_hours = (
                    posted_hours if posted_hours is not None
                    else order.truck.current_engine_hours
                )
                for item in order.line_items.filter(status='PENDING'):
                    item.status = 'DONE'
                    item.save()
            order.save()
            ServiceLogEntry.objects.create(
                job_order=order,
                truck=order.truck,
                action=f'Job {order.get_status_display()}',
                description=f'Job order {order.jo_number} '
                            f'marked as {order.get_status_display()}',
                performed_by=request.user,
                mileage_at=order.completed_mileage_km,
                engine_hours_at=order.completed_engine_hours,
            )
            for item in order.line_items.all():
                if item.status == 'DONE' and item.task_template:
                    pm_schedule = PMSchedule.objects.filter(
                        truck=order.truck,
                        task_template=item.task_template
                    ).first()
                    if pm_schedule:
                        pm_schedule.last_completed_at = timezone.now()
                        pm_schedule.last_mileage_km = (
                            order.completed_mileage_km
                        )
                        pm_schedule.last_engine_hours = (
                            order.completed_engine_hours
                        )
                        pm_schedule.save()
            messages.success(
                request,
                f'Job order {order.jo_number} closed.'
            )
            return redirect('joborders:detail', pk=pk)
    else:
        form = JobOrderStatusForm(instance=order)
    return render(request, 'joborders/close_form.html', {
        'form': form, 'order': order
    })


@login_required
def my_assignments(request):
    user = request.user
    if user.role == User.Role.CONTRACTOR:
        orders = JobOrder.objects.filter(
            Q(contractor__isnull=False) & Q(assigned_to=user) |
            Q(contractor__contact_person=user.get_full_name())
        )
    else:
        orders = JobOrder.objects.filter(assigned_to=user)
    orders = orders.exclude(status='CLOSED').select_related('truck')
    orders = orders.order_by('-created_at')
    return render(request, 'joborders/my_assignments.html', {
        'orders': orders
    })


def _can_update_job(user, order):
    if user.role in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF):
        return True
    if user.role == User.Role.MECHANIC and order.assigned_to == user:
        return True
    if user.role == User.Role.CONTRACTOR and order.assigned_to == user:
        return True
    return False


@login_required
def update_line_item(request, pk):
    item = get_object_or_404(JobOrderLineItem, pk=pk)
    order = item.job_order
    if order.status == 'CLOSED':
        messages.warning(request, 'Cannot update line item on closed JO.')
        return redirect('joborders:detail', pk=order.pk)
    if not _can_update_job(request.user, order):
        messages.error(request, 'You can only update line items on job orders assigned to you.')
        return redirect('joborders:detail', pk=order.pk)
    if request.method == 'POST':
        form = LineItemStatusForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            ServiceLogEntry.objects.create(
                job_order=order,
                line_item=item,
                truck=order.truck,
                action=f'Line item: {item.get_status_display()}',
                description=(
                    f'{item.description[:100]} - '
                    f'{item.get_status_display()}'
                    f' ({item.actual_hours}h)'
                    if item.actual_hours else
                    f'{item.description[:100]} - '
                    f'{item.get_status_display()}'
                ),
                performed_by=request.user,
                mileage_at=order.truck.current_mileage_km,
                engine_hours_at=order.truck.current_engine_hours,
                labor_hours=item.actual_hours,
            )
            messages.success(request, 'Line item updated.')
            return redirect('joborders:detail', pk=order.pk)
    else:
        form = LineItemStatusForm(instance=item)
    return render(request, 'joborders/line_item_form.html', {
        'form': form, 'item': item, 'order': order
    })


@login_required
def add_line_item_part(request, item_pk):
    item = get_object_or_404(JobOrderLineItem, pk=item_pk)
    order = item.job_order
    if not _can_update_job(request.user, order):
        messages.error(request, 'You can only add parts to job orders assigned to you.')
        return redirect('joborders:detail', pk=order.pk)
    if request.method == 'POST':
        form = LineItemPartForm(request.POST)
        if form.is_valid():
            part = form.save(commit=False)
            part.line_item = item
            part.save()
            messages.success(request, 'Part added.')
            return redirect('joborders:detail', pk=item.job_order.pk)
    else:
        form = LineItemPartForm()
    return render(request, 'joborders/part_form.html', {
        'form': form, 'item': item
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def job_order_add_line_item(request, pk):
    order = get_object_or_404(JobOrder, pk=pk)
    if order.status == 'CLOSED':
        messages.warning(request, 'Cannot add line items to a closed JO.')
        return redirect('joborders:detail', pk=pk)
    if request.method == 'POST':
        form = JobOrderLineItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.job_order = order
            item.save()
            messages.success(request, f'Line item "{item.description}" added.')
            return redirect('joborders:detail', pk=pk)
    else:
        form = JobOrderLineItemForm()
    return render(request, 'joborders/line_item_form.html', {
        'form': form, 'order': order, 'creating': True
    })
