import logging
import hmac
import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)
from django.db.models import Q, Sum, Count, Max
from django.utils import timezone
from accounts.decorators import role_required
from accounts.models import User
from accounts.views import build_overview_context
from trucks.models import Truck
from .models import Driver, DriverAssignment, DailyLog
from .cartrack_import import import_cartrack_data
from . import performance
from datetime import date, timedelta


def _staff_or_above(user):
    return user.role in (User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.STAFF)


def _admin_or_above(user):
    return user.role in (User.Role.SUPER_ADMIN, User.Role.ADMIN)


def _active_driver(truck, log_date):
    return DriverAssignment.objects.filter(
        truck=truck,
        assigned_from__lte=log_date,
    ).filter(
        Q(assigned_until__isnull=True) | Q(assigned_until__gte=log_date)
    ).select_related('driver').first()


# ── Daily Log ──

@login_required
def daily_log_list(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    date_start_str = request.GET.get('start', '')
    date_end_str = request.GET.get('end', '')
    try:
        if date_start_str and date_end_str:
            date_start = timezone.datetime.strptime(date_start_str, '%Y-%m-%d').date()
            date_end = timezone.datetime.strptime(date_end_str, '%Y-%m-%d').date()
        else:
            date_str = request.GET.get('date', '')
            date_start = timezone.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()
            date_end = date_start
    except ValueError:
        date_start = timezone.localdate()
        date_end = date_start

    is_range = date_start != date_end

    if is_range:
        qs = DailyLog.objects.filter(
            date__gte=date_start, date__lte=date_end
        ).values('truck_id').annotate(
            total_dist=Sum('distance_traveled_km'),
            total_fuel=Sum('fuel_liters'),
            latest_mileage=Max('mileage_km'),
            latest_eng_hrs=Max('engine_hours'),
            log_count=Count('id'),
        )
        agg = {r['truck_id']: r for r in qs}
        trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
        rows = []
        for t in trucks:
            r = agg.get(t.pk)
            if not r:
                rows.append({'truck': t, 'log': None, 'is_agg': True})
                continue
            rows.append({
                'truck': t,
                'is_agg': True,
                'log': None,
                'days': r['log_count'],
                'mileage': r['latest_mileage'],
                'eng_hrs': round(float(r['latest_eng_hrs'] or 0), 2),
                'fuel': round(float(r['total_fuel'] or 0), 2) if r['total_fuel'] else None,
                'dist': round(float(r['total_dist'] or 0), 2),
            })
        return render(request, 'fleetops/daily_log.html', {
            'date_start': date_start,
            'date_end': date_end,
            'rows': rows,
            'is_range': True,
            'title': 'Daily Log Summary',
        })

    logs = DailyLog.objects.filter(date=date_start).select_related('truck', 'driver', 'created_by')
    log_map = {l.truck_id: l for l in logs}
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
    rows = []
    for t in trucks:
        rows.append({'truck': t, 'log': log_map.get(t.pk), 'is_agg': False})
    drivers = Driver.objects.all().order_by('name')
    return render(request, 'fleetops/daily_log.html', {
        'log_date': date_start,
        'rows': rows,
        'drivers': drivers,
        'is_range': False,
        'title': 'Daily Log',
    })


@login_required
def daily_log_load(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    if request.method == 'POST':
        log_date_str = request.POST.get('date', '')
        try:
            log_date = timezone.datetime.strptime(log_date_str, '%Y-%m-%d').date() if log_date_str else timezone.localdate()
        except ValueError:
            log_date = timezone.localdate()
        trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
        saved = 0
        for t in trucks:
            mileage_key = f'mileage_{t.pk}'
            hours_key = f'hours_{t.pk}'
            driver_key = f'driver_{t.pk}'
            fuel_key = f'fuel_{t.pk}'
            idle_hrs_key = f'idle_hrs_{t.pk}'
            idle_cnt_key = f'idle_cnt_{t.pk}'
            op_hrs_key = f'op_hrs_{t.pk}'
            dist_key = f'dist_{t.pk}'
            max_spd_key = f'max_spd_{t.pk}'
            avg_spd_key = f'avg_spd_{t.pk}'
            brake_key = f'brake_{t.pk}'
            accel_key = f'accel_{t.pk}'
            turn_key = f'turn_{t.pk}'
            speed_key = f'speed_{t.pk}'

            if mileage_key not in request.POST:
                continue

            log, created = DailyLog.objects.get_or_create(
                truck=t,
                date=log_date,
                defaults={
                    'mileage_km': int(request.POST.get(mileage_key, 0)),
                    'engine_hours': round(float(request.POST.get(hours_key, 0)), 2),
                    'data_source': DailyLog.DataSource.MANUAL,
                    'created_by': request.user,
                }
            )
            if not created:
                log.mileage_km = int(request.POST.get(mileage_key, log.mileage_km))
                log.engine_hours = round(float(request.POST.get(hours_key, float(log.engine_hours))), 2)
            if driver_key in request.POST and request.POST[driver_key]:
                try:
                    log.driver_id = int(request.POST[driver_key])
                except (ValueError, TypeError):
                    pass
            else:
                active = _active_driver(t, log_date)
                if active:
                    log.driver = active.driver
            if fuel_key in request.POST and request.POST[fuel_key]:
                log.fuel_liters = round(float(request.POST[fuel_key]), 2)
            if idle_hrs_key in request.POST and request.POST[idle_hrs_key]:
                log.idle_hours = round(float(request.POST[idle_hrs_key]), 2)
            if idle_cnt_key in request.POST and request.POST[idle_cnt_key]:
                log.idle_count = int(request.POST[idle_cnt_key])
            if op_hrs_key in request.POST and request.POST[op_hrs_key]:
                log.operating_hours = round(float(request.POST[op_hrs_key]), 2)
            if dist_key in request.POST and request.POST[dist_key]:
                log.distance_traveled_km = round(float(request.POST[dist_key]), 2)
            if max_spd_key in request.POST and request.POST[max_spd_key]:
                log.max_speed_kmh = round(float(request.POST[max_spd_key]), 1)
            if avg_spd_key in request.POST and request.POST[avg_spd_key]:
                log.avg_speed_kmh = round(float(request.POST[avg_spd_key]), 1)
            if brake_key in request.POST and request.POST[brake_key]:
                log.harsh_braking_count = int(request.POST[brake_key])
            if accel_key in request.POST and request.POST[accel_key]:
                log.harsh_acceleration_count = int(request.POST[accel_key])
            if turn_key in request.POST and request.POST[turn_key]:
                log.harsh_turning_count = int(request.POST[turn_key])
            if speed_key in request.POST and request.POST[speed_key]:
                log.speeding_count = int(request.POST[speed_key])
            log.save()
            saved += 1
        logger.info('daily_log_load: saved %d entries for %s by %s', saved, log_date, request.user.username)
        messages.success(request, f'Saved {saved} log entries for {log_date}.')
        return redirect(reverse('fleetops:daily_log') + f'?date={log_date}')
    return redirect('fleetops:daily_log')


# ── Fleet Performance (merged dashboard) ──

@login_required
def fleet_performance(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    date_start, date_end = performance.parse_range(request)
    context = build_overview_context(request.user)
    context.update(performance.compute_fleet_performance(date_start, date_end))
    context.update(performance.range_shortcuts())
    context['date_start'] = date_start
    context['date_end'] = date_end
    context['show_performance'] = True
    context['active_tab'] = 'performance'
    return render(request, 'accounts/dashboard.html', context)


# ── Drivers ──

@login_required
def driver_list(request):
    if not _admin_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    drivers = Driver.objects.all().order_by('name')
    return render(request, 'fleetops/driver_list.html', {
        'drivers': drivers,
        'title': 'Drivers',
    })


@login_required
def driver_create(request):
    if not _admin_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        license_number = request.POST.get('license_number', '').strip()
        license_expiry_str = request.POST.get('license_expiry', '')
        if not name or not license_number or not license_expiry_str:
            messages.error(request, 'Name, License Number, and Expiry are required.')
            return render(request, 'fleetops/driver_form.html', {'title': 'Add Driver'})
        try:
            license_expiry = timezone.datetime.strptime(license_expiry_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return render(request, 'fleetops/driver_form.html', {'title': 'Add Driver'})
        if Driver.objects.filter(license_number=license_number).exists():
            messages.error(request, f'Driver with license #{license_number} already exists.')
            return render(request, 'fleetops/driver_form.html', {'title': 'Add Driver'})
        Driver.objects.create(
            name=name,
            address=request.POST.get('address', ''),
            age=int(request.POST['age']) if request.POST.get('age') else None,
            license_number=license_number,
            license_expiry=license_expiry,
            mobile=request.POST.get('mobile', ''),
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'Driver {name} created.')
        return redirect('fleetops:driver_list')
    return render(request, 'fleetops/driver_form.html', {'title': 'Add Driver'})


@login_required
def driver_edit(request, pk):
    if not _admin_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        license_number = request.POST.get('license_number', '').strip()
        license_expiry_str = request.POST.get('license_expiry', '')
        if not name or not license_number or not license_expiry_str:
            messages.error(request, 'Name, License Number, and Expiry are required.')
            return render(request, 'fleetops/driver_form.html', {'driver': driver, 'title': 'Edit Driver'})
        try:
            license_expiry = timezone.datetime.strptime(license_expiry_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return render(request, 'fleetops/driver_form.html', {'driver': driver, 'title': 'Edit Driver'})
        dup = Driver.objects.filter(license_number=license_number).exclude(pk=pk).first()
        if dup:
            messages.error(request, f'License #{license_number} belongs to {dup.name}.')
            return render(request, 'fleetops/driver_form.html', {'driver': driver, 'title': 'Edit Driver'})
        driver.name = name
        driver.address = request.POST.get('address', '')
        driver.age = int(request.POST['age']) if request.POST.get('age') else None
        driver.license_number = license_number
        driver.license_expiry = license_expiry
        driver.mobile = request.POST.get('mobile', '')
        driver.notes = request.POST.get('notes', '')
        driver.save()
        messages.success(request, f'Driver {name} updated.')
        return redirect('fleetops:driver_list')
    return render(request, 'fleetops/driver_form.html', {'driver': driver, 'title': 'Edit Driver'})


@login_required
def driver_scorecard(request, pk):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    driver = get_object_or_404(Driver, pk=pk)
    assignments = DriverAssignment.objects.filter(driver=driver).select_related('truck')
    logs = DailyLog.objects.filter(driver=driver).select_related('truck').order_by('-date')[:90]
    total_dist = sum(float(l.distance_traveled_km) for l in logs)
    total_fuel = sum(float(l.fuel_liters or 0) for l in logs)
    total_op = sum(float(l.operating_hours) for l in logs)
    total_idle = sum(float(l.idle_hours) for l in logs)
    total_brake = sum(l.harsh_braking_count for l in logs)
    total_accel = sum(l.harsh_acceleration_count for l in logs)
    total_turn = sum(l.harsh_turning_count for l in logs)
    efficiency = round(total_dist / total_fuel, 2) if total_fuel > 0 else None
    utilization = round(total_op / (total_op + total_idle) * 100, 1) if (total_op + total_idle) > 0 else None
    harsh_per_100km = round((total_brake + total_accel + total_turn) / (total_dist / 100), 1) if total_dist > 0 else None
    return render(request, 'fleetops/driver_scorecard.html', {
        'driver': driver,
        'assignments': assignments,
        'logs': logs,
        'total_dist': round(total_dist, 2),
        'efficiency': efficiency,
        'utilization': utilization,
        'harsh_per_100km': harsh_per_100km,
        'total_harsh': total_brake + total_accel + total_turn,
        'title': f'Scorecard - {driver.name}',
    })


# ── Driver Assignments ──

@login_required
def assignment_list(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    active = DriverAssignment.objects.filter(
        assigned_until__isnull=True
    ).select_related('driver', 'truck').order_by('driver__name')
    history = DriverAssignment.objects.filter(
        assigned_until__isnull=False
    ).select_related('driver', 'truck').order_by('-assigned_until')[:50]
    return render(request, 'fleetops/assignment_list.html', {
        'active': active,
        'history': history,
        'title': 'Driver Assignments',
    })


@login_required
def assignment_create(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    if request.method == 'POST':
        driver_id = request.POST.get('driver')
        truck_id = request.POST.get('truck')
        assigned_from_str = request.POST.get('assigned_from', '')
        assigned_until_str = request.POST.get('assigned_until', '')
        if not driver_id or not truck_id or not assigned_from_str:
            messages.error(request, 'Driver, Truck, and Start Date are required.')
            return redirect('fleetops:assignment_create')
        try:
            assigned_from = timezone.datetime.strptime(assigned_from_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid start date.')
            return redirect('fleetops:assignment_create')
        assigned_until = None
        if assigned_until_str:
            try:
                assigned_until = timezone.datetime.strptime(assigned_until_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid end date.')
                return redirect('fleetops:assignment_create')
        driver = get_object_or_404(Driver, pk=driver_id)
        truck = get_object_or_404(Truck, pk=truck_id)
        DriverAssignment.objects.create(
            driver=driver, truck=truck,
            assigned_from=assigned_from, assigned_until=assigned_until,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, f'{driver.name} assigned to {truck.unit_number}.')
        return redirect('fleetops:assignment_list')
    drivers = Driver.objects.all().order_by('name')
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
    return render(request, 'fleetops/assignment_form.html', {
        'drivers': drivers,
        'trucks': trucks,
        'title': 'New Assignment',
    })


# ── Cartrack Pull ──

@login_required
def pull_cartrack(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    if request.method != 'POST':
        return redirect('fleetops:daily_log')

    date_str = request.POST.get('date', '')
    date_end_str = request.POST.get('date_end', '')
    try:
        import_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        import_date_end = timezone.datetime.strptime(date_end_str, '%Y-%m-%d').date() if date_end_str else import_date
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('fleetops:daily_log')

    data_types = []
    logger.info('pull_cartrack: date=%s date_end=%s user=%s',
                date_str, date_end_str, request.user.username)
    if request.POST.get('type_trips'):
        data_types.append('trips')
    if request.POST.get('type_events'):
        data_types.append('events')
    if request.POST.get('type_fuel'):
        data_types.append('fuel')
    if not data_types:
        data_types = ['trips']

    any_success = False
    date_label = ''
    all_errors = []

    if data_types:
        if import_date:
            c_result = import_cartrack_data(import_date=import_date, import_date_end=import_date_end, data_types=data_types)
        else:
            days_back = int(request.POST.get('days_back', 1))
            c_result = import_cartrack_data(days_back=days_back, data_types=data_types)

        imported = c_result.get('import_date', import_date or timezone.localdate())
        if isinstance(imported, date):
            date_label = imported.isoformat()
        else:
            date_label = str(imported)
        if c_result.get('import_date_end') and date_label != str(c_result['import_date_end']):
            date_label += f" – {c_result['import_date_end']}"

        if c_result['success'] and c_result['processed'] > 0:
            any_success = True
            fuel_info = ''
            fc = c_result.get('fuel_count', 0)
            fe = c_result.get('fuel_endpoint', '')
            if fc:
                fuel_info = f" | Fuel: {fc} entries"
                if fe:
                    fuel_info += f" ({fe})"
            messages.success(
                request,
                f"Cartrack import complete: {c_result['processed']} log(s) for {date_label}.{fuel_info}"
            )
        elif c_result['success']:
            msg = "No Cartrack data found for the selected date."
            if c_result['errors']:
                msg += ' ' + ' '.join(c_result['errors'])
            if c_result.get('trucks_found', 1) == 0:
                msg += ' No active trucks found.'
            all_errors.append(msg)
        else:
            all_errors.append(f"Cartrack import failed: {c_result.get('error', 'Unknown error')}")

    for err in all_errors:
        messages.warning(request, err)
    if not any_success and not all_errors:
        messages.warning(request, 'Nothing was imported. Select at least one data type.')
    if import_date == import_date_end:
        return redirect(reverse('fleetops:daily_log') + f'?date={import_date}')
    return redirect(reverse('fleetops:daily_log') + f'?start={import_date}&end={import_date_end}')


# ── Automated Sync (token-guarded) ──

@csrf_exempt
@require_POST
def sync_cartrack(request):
    """POST /fleetops/sync/ — Bearer SYNC_TOKEN guarded, runs last 7 days.

    Used by the GitHub Actions nightly job. Returns JSON summary.
    """
    token = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    expected = os.environ.get('SYNC_TOKEN', '')
    if not expected or not token or not hmac.compare_digest(token, expected):
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)

    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
    except (ValueError, UnicodeDecodeError):
        body = {}

    days_back = int(body.get('days_back', 7))
    days_back = min(max(days_back, 1), 31)
    data_types = body.get('data_types') or ['trips', 'events', 'fuel']

    # Rolling window ending yesterday (Manila local), self-healing across missed days
    end = timezone.localdate() - timedelta(days=1)
    start = end - timedelta(days=days_back - 1)

    logger.info('sync_cartrack: %s..%s data_types=%s', start, end, data_types)
    result = import_cartrack_data(import_date=start, import_date_end=end, data_types=data_types)

    end = result.get('import_date_end')
    start = result.get('import_date')
    payload = {
        'success': bool(result.get('success')),
        'processed': result.get('processed', 0),
        'date_start': start.isoformat() if isinstance(start, date) else str(start),
        'date_end': end.isoformat() if isinstance(end, date) else str(end),
        'errors': result.get('errors', []),
        'fuel_warnings': result.get('fuel_warnings', []),
        'trucks_found': result.get('trucks_found', 0),
        'data_types': data_types,
    }
    if not payload['success']:
        payload['error'] = result.get('error', 'Unknown error')
        return JsonResponse(payload, status=502)
    return JsonResponse(payload)


# ── Compliance Dashboard ──

@login_required
def compliance_dashboard(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
    drivers = Driver.objects.all().order_by('name')
    return render(request, 'fleetops/compliance_dashboard.html', {
        'trucks': trucks,
        'drivers': drivers,
        'title': 'Compliance & Expiries',
    })

