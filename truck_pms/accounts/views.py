from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth import login
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from fleetops.models import Driver
from fleetops.performance import compute_fleet_performance, parse_range, range_shortcuts
from joborders.models import JobOrder
from trucks.models import Truck
from pms.models import PMSchedule
from .decorators import role_required
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

_STAFF_ROLES = (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)


def build_overview_context(user):
    open_jo_count = JobOrder.objects.exclude(status='CLOSED').count()
    active_truck_count = Truck.objects.filter(status='ACTIVE').count()
    my_assigned_count = JobOrder.objects.filter(
        assigned_to=user
    ).exclude(status='CLOSED').count()
    schedules = PMSchedule.objects.filter(
        is_active=True,
        truck__status='ACTIVE'
    ).select_related('truck', 'task_template')
    due_now = []
    overdue_pm_count = 0
    for pm in schedules:
        st = pm.status()
        if st == 'overdue':
            overdue_pm_count += 1
        if st in ('overdue', 'due'):
            due_now.append(pm)
    last_30_days = timezone.localdate() - timedelta(days=30)
    recent_jobs = JobOrder.objects.select_related(
        'truck', 'assigned_to'
    ).filter(created_at__date__gte=last_30_days).order_by('-created_at')[:10]

    expiring_items = []
    for truck in Truck.objects.filter(status='ACTIVE').order_by('unit_number'):
        for item in truck.compliance_items():
            if item['status'] in ('overdue', 'due_soon'):
                expiring_items.append({
                    'truck': truck,
                    'label': item['label'],
                    'expiry': item['expiry'],
                    'ref_number': item['ref_number'],
                    'status': item['status'],
                })
    expiring_items.sort(key=lambda x: x['expiry'] or date.max)

    drivers_expiring = []
    for driver in Driver.objects.all().order_by('name'):
        st = driver.license_status()
        if st in ('overdue', 'due_soon'):
            drivers_expiring.append({
                'driver': driver,
                'label': 'Driver License',
                'expiry': driver.license_expiry,
                'license_number': driver.license_number,
                'status': st,
            })
    drivers_expiring.sort(key=lambda x: x['expiry'] or date.max)

    return {
        'open_jo_count': open_jo_count,
        'active_truck_count': active_truck_count,
        'my_assigned_count': my_assigned_count,
        'overdue_pm_count': overdue_pm_count,
        'due_pm_list': due_now[:10],
        'recent_jobs': recent_jobs,
        'expiring_items': expiring_items,
        'drivers_expiring': drivers_expiring,
    }


def trend_context(days=14):
    """14-day series (JO created / PM completed per day) for sparklines."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    jo_qs = JobOrder.objects.filter(
        created_at__date__gte=start
    ).values('created_at__date').annotate(n=Count('id'))
    jo_by_date = {r['created_at__date']: r['n'] for r in jo_qs}
    pm_qs = PMSchedule.objects.filter(
        last_completed_at__date__gte=start
    ).values('last_completed_at__date').annotate(n=Count('id'))
    pm_by_date = {r['last_completed_at__date']: r['n'] for r in pm_qs}
    day_labels, jo_series, pm_series = [], [], []
    cursor = start
    while cursor <= today:
        day_labels.append(cursor.strftime('%m/%d'))
        jo_series.append(jo_by_date.get(cursor, 0))
        pm_series.append(pm_by_date.get(cursor, 0))
        cursor += timedelta(days=1)
    return {
        'trend_days': day_labels,
        'trend_jo': jo_series,
        'trend_pm': pm_series,
    }


@login_required
def dashboard(request):
    user = request.user
    show_performance = user.role in _STAFF_ROLES
    context = build_overview_context(user)
    context.update(trend_context())
    if show_performance:
        date_start, date_end = parse_range(request)
        context.update(compute_fleet_performance(date_start, date_end))
        context.update(range_shortcuts())
        context['date_start'] = date_start
        context['date_end'] = date_end
    context['show_performance'] = show_performance
    context['active_tab'] = 'performance' if request.GET.get('tab') == 'performance' else 'overview'
    return render(request, 'accounts/dashboard.html', context)


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        user = form.get_user()
        if user.role == User.Role.CONTRACTOR:
            login(self.request, user)
            return redirect('joborders:my_assignments')
        if user.role == User.Role.TRAINEE:
            login(self.request, user)
            return redirect('training:dashboard')
        return super().form_valid(form)


@login_required
@role_required(User.Role.SUPER_ADMIN)
def user_list(request):
    role_filter = request.GET.get('role')
    users = User.objects.all().order_by('-is_active', 'username')
    if role_filter:
        users = users.filter(role=role_filter)
    paginator = Paginator(users, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'accounts/user_list.html', {
        'page_obj': page_obj, 'users': page_obj.object_list,
        'selected_role': role_filter,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN)
def user_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully.')
            return redirect('accounts:user_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Create User'})


@login_required
@role_required(User.Role.SUPER_ADMIN)
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User updated successfully.')
            return redirect('accounts:user_list')
    else:
        form = CustomUserChangeForm(instance=user)
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'Edit User: {user.username}'
    })
