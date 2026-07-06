from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from joborders.models import JobOrder
from trucks.models import Truck
from pms.models import PMSchedule
from .decorators import role_required
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm


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
def dashboard(request):
    user = request.user
    open_jo_count = JobOrder.objects.exclude(status='CLOSED').count()
    active_truck_count = Truck.objects.filter(status='ACTIVE').count()
    my_assigned_count = JobOrder.objects.filter(
        assigned_to=user
    ).exclude(status='CLOSED').count()
    overdue_pm = PMSchedule.objects.filter(
        is_active=True,
        truck__status='ACTIVE'
    ).select_related('truck', 'task_template')
    due_now = []
    for pm in overdue_pm:
        st = pm.status()
        if st in ('overdue', 'due'):
            due_now.append(pm)
    recent_jobs = JobOrder.objects.select_related(
        'truck', 'assigned_to'
    ).order_by('-created_at')[:10]
    context = {
        'open_jo_count': open_jo_count,
        'active_truck_count': active_truck_count,
        'my_assigned_count': my_assigned_count,
        'overdue_pm_count': sum(1 for p in due_now if p.status() == 'overdue'),
        'due_pm_list': due_now[:10],
        'recent_jobs': recent_jobs,
    }
    return render(request, 'accounts/dashboard.html', context)


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
