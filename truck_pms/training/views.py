from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count
from accounts.decorators import role_required
from accounts.models import User
from pms.models import TaskTemplate
from .models import Training, Attendance, TaskRating, WeeklyReview, Holiday


def _get_training_or_404(user):
    return get_object_or_404(Training, ojt=user, status='ACTIVE')


@login_required
def dashboard(request):
    user = request.user
    if user.role == User.Role.TRAINEE:
        return _ojt_dashboard(request, user)
    if user.role in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF):
        return _supervisor_dashboard(request, user)
    messages.warning(request, 'Training is only available for OJTs and supervisors.')
    return redirect('accounts:dashboard')


def _ojt_dashboard(request, user):
    try:
        training = Training.objects.get(ojt=user, status='ACTIVE')
    except Training.DoesNotExist:
        return render(request, 'training/no_training.html')

    today = timezone.localdate()
    attendance_today = Attendance.objects.filter(
        training=training, date=today
    ).first()
    recent_ratings = training.task_ratings.select_related(
        'supervisor', 'task_template'
    ).order_by('-created_at')[:10]
    recent_reviews = training.weekly_reviews.order_by('-week_start')[:5]
    avg_score = training.task_ratings.aggregate(
        avg=Avg('rating')
    )['avg'] or 0

    context = {
        'training': training,
        'attendance_today': attendance_today,
        'recent_ratings': recent_ratings,
        'recent_reviews': recent_reviews,
        'avg_score': round(avg_score, 1),
        'total_ratings': training.task_ratings.count(),
        'ojt': True,
    }
    return render(request, 'training/dashboard.html', context)


def _supervisor_dashboard(request, user):
    trainees = Training.objects.filter(
        supervisor=user, status='ACTIVE'
    ).select_related('ojt')
    recent_ratings = TaskRating.objects.filter(
        supervisor=user
    ).select_related('training__ojt', 'task_template').order_by('-created_at')[:20]
    recent_reviews = WeeklyReview.objects.filter(
        training__supervisor=user
    ).select_related('training__ojt').order_by('-week_start')[:5]

    context = {
        'trainees': trainees,
        'recent_ratings': recent_ratings,
        'recent_reviews': recent_reviews,
        'ojt': False,
    }
    return render(request, 'training/dashboard.html', context)


@login_required
@role_required(User.Role.TRAINEE)
def attendance_check_in(request):
    training = _get_training_or_404(request.user)
    today = timezone.localdate()
    if Attendance.objects.filter(training=training, date=today).exists():
        messages.info(request, 'Already checked in today.')
    else:
        Attendance.objects.create(training=training)
        messages.success(request, 'Checked in successfully.')
    return redirect('training:dashboard')


@login_required
@role_required(User.Role.TRAINEE)
def attendance_check_out(request):
    training = _get_training_or_404(request.user)
    today = timezone.localdate()
    att = Attendance.objects.filter(
        training=training, date=today, time_out__isnull=True
    ).first()
    if att:
        att.time_out = timezone.localtime().time()
        att.save()
        messages.success(request, 'Checked out successfully.')
    else:
        messages.warning(request, 'No active check-in found for today.')
    return redirect('training:dashboard')


@login_required
def attendance_list(request):
    user = request.user
    if user.role == User.Role.TRAINEE:
        training = get_object_or_404(Training, ojt=user)
        attendances = training.attendances.all()
    else:
        attendances = Attendance.objects.filter(
            training__supervisor=user
        ).select_related('training__ojt').order_by('-date', '-time_in')
    return render(request, 'training/attendance_list.html', {
        'attendances': attendances,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def rating_create(request):
    trainees = Training.objects.filter(
        supervisor=request.user, status='ACTIVE'
    ).select_related('ojt')
    templates = TaskTemplate.objects.select_related('category').order_by(
        'category__name', 'name'
    )

    if request.method == 'POST':
        training_id = request.POST.get('training')
        template_id = request.POST.get('task_template')
        task_name = request.POST.get('task_name', '')
        rating_val = request.POST.get('rating')
        comments = request.POST.get('comments', '')

        training = get_object_or_404(Training, pk=training_id, supervisor=request.user)
        template = None
        if template_id:
            template = get_object_or_404(TaskTemplate, pk=template_id)
            task_name = template.name

        TaskRating.objects.create(
            training=training,
            supervisor=request.user,
            task_template=template,
            task_name=task_name,
            rating=rating_val,
            comments=comments,
        )
        messages.success(request, f'Rating saved for {training.ojt.get_full_name() or training.ojt.username}.')
        return redirect('training:rating_list')

    return render(request, 'training/rating_form.html', {
        'trainees': trainees,
        'templates': templates,
    })


@login_required
def rating_list(request):
    user = request.user
    if user.role == User.Role.TRAINEE:
        training = get_object_or_404(Training, ojt=user)
        ratings = training.task_ratings.all()
    else:
        ratings = TaskRating.objects.filter(
            supervisor=user
        ).select_related('training__ojt', 'task_template').order_by('-created_at')
    return render(request, 'training/rating_list.html', {
        'ratings': ratings,
    })


@login_required
def rating_detail(request, pk):
    rating = get_object_or_404(
        TaskRating.objects.select_related(
            'training__ojt', 'supervisor', 'task_template'
        ),
        pk=pk,
    )
    return render(request, 'training/rating_detail.html', {'rating': rating})


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)
def review_create(request):
    if request.method == 'POST':
        training_id = request.POST.get('training')
        week_start = request.POST.get('week_start')
        week_end = request.POST.get('week_end')
        overall_score = request.POST.get('overall_score')
        strengths = request.POST.get('strengths', '')
        areas = request.POST.get('areas_for_improvement', '')
        notes = request.POST.get('supervisor_notes', '')

        training = get_object_or_404(Training, pk=training_id, supervisor=request.user)
        WeeklyReview.objects.create(
            training=training,
            week_start=week_start,
            week_end=week_end,
            overall_score=overall_score,
            strengths=strengths,
            areas_for_improvement=areas,
            supervisor_notes=notes,
        )
        messages.success(request, 'Weekly review created.')
        return redirect('training:review_list')

    trainees = Training.objects.filter(
        supervisor=request.user, status='ACTIVE'
    ).select_related('ojt')
    return render(request, 'training/review_form.html', {
        'trainees': trainees,
    })


@login_required
def review_list(request):
    user = request.user
    if user.role == User.Role.TRAINEE:
        training = get_object_or_404(Training, ojt=user)
        reviews = training.weekly_reviews.all()
    else:
        reviews = WeeklyReview.objects.filter(
            training__supervisor=user
        ).select_related('training__ojt').order_by('-week_start')
    return render(request, 'training/review_list.html', {
        'reviews': reviews,
    })


@login_required
def review_detail(request, pk):
    review = get_object_or_404(
        WeeklyReview.objects.select_related('training__ojt', 'training__supervisor'),
        pk=pk,
    )
    return render(request, 'training/review_detail.html', {'review': review})


@login_required
def ojt_detail(request, pk):
    training = get_object_or_404(
        Training.objects.select_related('ojt', 'supervisor'),
        pk=pk,
    )
    if not request.user.role == User.Role.TRAINEE and training.supervisor != request.user:
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.ADMIN):
            messages.error(request, 'Not authorized.')
            return redirect('training:dashboard')
    ratings = training.task_ratings.select_related('task_template').order_by('-created_at')[:20]
    reviews = training.weekly_reviews.order_by('-week_start')[:5]
    avg_score = training.task_ratings.aggregate(avg=Avg('rating'))['avg'] or 0
    return render(request, 'training/ojt_detail.html', {
        'training': training,
        'ratings': ratings,
        'reviews': reviews,
        'avg_score': round(avg_score, 1),
    })


@login_required
def ojt_rating_list(request, pk):
    training = get_object_or_404(Training, pk=pk)
    ratings = training.task_ratings.select_related(
        'supervisor', 'task_template'
    ).order_by('-created_at')
    return render(request, 'training/rating_list.html', {
        'ratings': ratings,
        'ojt_name': training.ojt.get_full_name() or training.ojt.username,
    })


@login_required
def ojt_review_list(request, pk):
    training = get_object_or_404(Training, pk=pk)
    reviews = training.weekly_reviews.order_by('-week_start')
    return render(request, 'training/review_list.html', {
        'reviews': reviews,
        'ojt_name': training.ojt.get_full_name() or training.ojt.username,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN)
def assign_training(request):
    if request.method == 'POST':
        ojt_id = request.POST.get('ojt')
        supervisor_id = request.POST.get('supervisor')
        start_date = request.POST.get('start_date')
        notes = request.POST.get('notes', '')

        ojt = get_object_or_404(User, pk=ojt_id, role=User.Role.TRAINEE)
        supervisor = get_object_or_404(User, pk=supervisor_id)

        if Training.objects.filter(ojt=ojt, status='ACTIVE').exists():
            messages.error(request, 'This OJT already has an active training.')
            return redirect('training:assign')

        Training.objects.create(
            ojt=ojt,
            supervisor=supervisor,
            start_date=start_date,
            notes=notes,
            status='ACTIVE',
        )
        messages.success(
            request,
            f'{ojt.get_full_name() or ojt.username} assigned to '
            f'{supervisor.get_full_name() or supervisor.username}.'
        )
        return redirect('training:dashboard')

    unassigned = User.objects.filter(
        role=User.Role.TRAINEE
    ).exclude(training_profile__status='ACTIVE')
    assigned = Training.objects.filter(
        ojt__role=User.Role.TRAINEE, status='ACTIVE'
    ).select_related('ojt', 'supervisor')
    supervisors = User.objects.filter(
        role__in=[User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF]
    )
    return render(request, 'training/assign.html', {
        'trainees': unassigned,
        'assigned': assigned,
        'supervisors': supervisors,
    })


@login_required
@role_required(User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF, User.Role.TRAINEE)
def holiday_list(request):
    year = request.GET.get('year', timezone.localdate().year)
    holidays = Holiday.objects.filter(date__year=year).order_by('date')
    selected_year = int(year)
    years = range(2024, 2031)
    return render(request, 'training/holiday_list.html', {
        'holidays': holidays,
        'selected_year': selected_year,
        'years': years,
    })
