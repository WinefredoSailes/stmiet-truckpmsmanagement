from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from accounts.decorators import role_required
from accounts.models import User
from .models import Contractor
from .forms import ContractorForm


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def contractor_list(request):
    contractors = Contractor.objects.all().order_by('company_name')
    paginator = Paginator(contractors, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'contractors/list.html', {'page_obj': page_obj, 'contractors': page_obj.object_list})


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def contractor_detail(request, pk):
    contractor = get_object_or_404(Contractor, pk=pk)
    job_orders = contractor.job_orders.select_related('truck').order_by('-created_at')[:20]
    return render(request, 'contractors/detail.html', {
        'contractor': contractor,
        'job_orders': job_orders,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def contractor_create(request):
    if request.method == 'POST':
        form = ContractorForm(request.POST)
        if form.is_valid():
            contractor = form.save()
            messages.success(request, f'Contractor {contractor.company_name} created.')
            return redirect('contractors:list')
    else:
        form = ContractorForm()
    return render(request, 'contractors/form.html', {
        'form': form, 'title': 'Add Contractor'
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def contractor_update(request, pk):
    contractor = get_object_or_404(Contractor, pk=pk)
    if request.method == 'POST':
        form = ContractorForm(request.POST, instance=contractor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Contractor {contractor.company_name} updated.')
            return redirect('contractors:list')
    else:
        form = ContractorForm(instance=contractor)
    return render(request, 'contractors/form.html', {
        'form': form, 'title': f'Edit {contractor.company_name}'
    })
