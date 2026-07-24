from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Sum, Count, F
from django.utils import timezone
from accounts.decorators import role_required
from accounts.models import User
from trucks.models import Truck
from .models import Driver, DriverAssignment, DailyLog
from .cartrack_import import import_cartrack_data
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
    log_date_str = request.GET.get('date', '')
    try:
        log_date = timezone.datetime.strptime(log_date_str, '%Y-%m-%d').date() if log_date_str else date.today()
    except ValueError:
        log_date = date.today()
    logs = DailyLog.objects.filter(date=log_date).select_related('truck', 'driver', 'created_by')
    log_map = {l.truck_id: l for l in logs}
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
    rows = []
    for t in trucks:
        rows.append({'truck': t, 'log': log_map.get(t.pk)})
    drivers = Driver.objects.all().order_by('name')
    return render(request, 'fleetops/daily_log.html', {
        'log_date': log_date,
        'rows': rows,
        'drivers': drivers,
        'title': 'Daily Log Entry',
    })


@login_required
def daily_log_load(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    if request.method == 'POST':
        log_date_str = request.POST.get('date', '')
        try:
            log_date = timezone.datetime.strptime(log_date_str, '%Y-%m-%d').date() if log_date_str else date.today()
        except ValueError:
            log_date = date.today()
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

            if mileage_key not in request.POST:
                continue

            log, created = DailyLog.objects.get_or_create(
                truck=t,
                date=log_date,
                defaults={
                    'mileage_km': int(request.POST.get(mileage_key, 0)),
                    'engine_hours': round(float(request.POST.get(hours_key, 0)), 1),
                    'data_source': DailyLog.DataSource.MANUAL,
                    'created_by': request.user,
                }
            )
            if not created:
                log.mileage_km = int(request.POST.get(mileage_key, log.mileage_km))
                log.engine_hours = round(float(request.POST.get(hours_key, float(log.engine_hours))), 1)
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
                log.distance_traveled_km = round(float(request.POST[dist_key]), 1)
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
            if log.data_source == DailyLog.DataSource.MANUAL:
                log.data_source = DailyLog.DataSource.MANUAL
            log.save()
            saved += 1
        messages.success(request, f'Saved {saved} log entries for {log_date}.')
        return redirect('fleetops:daily_log') + f'?date={log_date}'
    return redirect('fleetops:daily_log')


# ── Fleet Performance Dashboard ──

@login_required
def fleet_performance(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    week_start_str = request.GET.get('week', '')
    try:
        if week_start_str:
            week_start = timezone.datetime.strptime(week_start_str, '%Y-%m-%d').date()
        else:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
    except ValueError:
        week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=6)
    logs = DailyLog.objects.filter(
        date__gte=week_start, date__lte=week_end
    ).select_related('truck')
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
    perf = []
    for t in trucks:
        t_logs = [l for l in logs if l.truck_id == t.pk]
        if not t_logs:
            continue
        total_dist = sum(float(l.distance_traveled_km) for l in t_logs)
        total_fuel = sum(float(l.fuel_liters or 0) for l in t_logs)
        total_op = sum(float(l.operating_hours) for l in t_logs)
        total_idle = sum(float(l.idle_hours) for l in t_logs)
        total_brake = sum(l.harsh_braking_count for l in t_logs)
        total_accel = sum(l.harsh_acceleration_count for l in t_logs)
        total_turn = sum(l.harsh_turning_count for l in t_logs)
        avg_speed = sum(float(l.avg_speed_kmh or 0) for l in t_logs if l.avg_speed_kmh)
        speed_count = sum(1 for l in t_logs if l.avg_speed_kmh)
        efficiency = round(total_dist / total_fuel, 2) if total_fuel > 0 else None
        utilization = round(total_op / (total_op + total_idle) * 100, 1) if (total_op + total_idle) > 0 else None
        perf.append({
            'truck': t,
            'distance': round(total_dist, 1),
            'fuel': round(total_fuel, 1),
            'efficiency': efficiency,
            'utilization': utilization,
            'avg_speed': round(avg_speed / speed_count, 1) if speed_count > 0 else None,
            'harsh_events': total_brake + total_accel + total_turn,
            'log_count': len(t_logs),
        })
    return render(request, 'fleetops/fleet_performance.html', {
        'week_start': week_start,
        'week_end': week_end,
        'performance': perf,
        'title': 'Fleet Performance',
    })


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
        'total_dist': round(total_dist, 1),
        'efficiency': efficiency,
        'utilization': utilization,
        'harsh_per_100km': harsh_per_100km,
        'total_harsh': total_brake + total_accel + total_turn,
        'title': f'Scorecard - {driver.name}',
    })


# ── Weekly Performance Report ──

@login_required
def weekly_report(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    start_str = request.GET.get('start', '')
    end_str = request.GET.get('end', '')
    try:
        start = timezone.datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else date.today() - timedelta(days=6)
        end = timezone.datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else date.today()
    except ValueError:
        start = date.today() - timedelta(days=6)
        end = date.today()

    logs = DailyLog.objects.filter(date__gte=start, date__lte=end).select_related('truck', 'driver')
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')

    truck_rows = []
    driver_data = {}
    total_dist = total_fuel = total_op = total_idle = 0
    total_brake = total_accel = total_turn = total_speed = 0

    for t in trucks:
        t_logs = [l for l in logs if l.truck_id == t.pk]
        if not t_logs:
            continue
        d = sum(float(l.distance_traveled_km) for l in t_logs)
        f = sum(float(l.fuel_liters or 0) for l in t_logs)
        op = sum(float(l.operating_hours) for l in t_logs)
        idl = sum(float(l.idle_hours) for l in t_logs)
        bk = sum(l.harsh_braking_count for l in t_logs)
        ac = sum(l.harsh_acceleration_count for l in t_logs)
        tn = sum(l.harsh_turning_count for l in t_logs)
        max_spd = max((float(l.max_speed_kmh or 0) for l in t_logs), default=0)
        days = len(t_logs)
        eff = round(d / f, 2) if f > 0 else None
        eff_kmpl = round(d / f, 2) if f > 0 else None  # km/L
        eff_lph = round(f / op, 2) if op > 0 else None  # L/hr
        util = round(op / (op + idl) * 100, 1) if (op + idl) > 0 else None

        driver_name = t_logs[-1].driver.name if t_logs[-1].driver else 'Unassigned'

        truck_rows.append({
            'truck': t,
            'driver_name': driver_name,
            'distance': round(d, 1),
            'fuel': round(f, 1),
            'operating_hours': round(op, 2),
            'idle_hours': round(idl, 2),
            'brake': bk, 'accel': ac, 'turn': tn,
            'harsh_total': bk + ac + tn,
            'max_speed': max_spd,
            'efficiency': eff,
            'efficiency_kmpl': eff_kmpl,
            'efficiency_lph': eff_lph,
            'utilization': util,
            'days': days,
        })

        total_dist += d
        total_fuel += f
        total_op += op
        total_idle += idl
        total_brake += bk
        total_accel += ac
        total_turn += tn

        # Aggregate by driver
        for l in t_logs:
            drv = l.driver
            if not drv:
                continue
            if drv.pk not in driver_data:
                driver_data[drv.pk] = {
                    'driver': drv,
                    'distance': 0, 'fuel': 0, 'op': 0, 'idl': 0,
                    'brake': 0, 'accel': 0, 'turn': 0,
                }
            dd = driver_data[drv.pk]
            dd['distance'] += float(l.distance_traveled_km)
            dd['fuel'] += float(l.fuel_liters or 0)
            dd['op'] += float(l.operating_hours)
            dd['idl'] += float(l.idle_hours)
            dd['brake'] += l.harsh_braking_count
            dd['accel'] += l.harsh_acceleration_count
            dd['turn'] += l.harsh_turning_count

    # Calculate driver scores
    driver_scores = []
    for dd in driver_data.values():
        d = dd['distance']
        op = dd['op']
        idl = dd['idl']
        bk = dd['brake']
        ac = dd['accel']
        tn = dd['turn']
        # Score: 100 minus events per 100km × factor, min 0
        def _score(events, divisor, factor=5):
            if divisor <= 0:
                return 100
            return max(0, round(100 - (events / divisor * 100) * factor))
        idle_pct = idl / (op + idl) * 100 if (op + idl) > 0 else 0
        brake_s = _score(bk, d)
        accel_s = _score(ac, d)
        turn_s = _score(tn, d)
        idle_s = max(0, round(100 - idle_pct))
        avg_s = round((brake_s + accel_s + turn_s + idle_s) / 4, 2)
        driver_scores.append({
            'driver': dd['driver'],
            'distance': round(d, 1),
            'brake_score': brake_s,
            'accel_score': accel_s,
            'turn_score': turn_s,
            'idle_score': idle_s,
            'average_score': avg_s,
        })
    driver_scores.sort(key=lambda x: x['average_score'], reverse=True)

    # Idle report
    idle_report = []
    for tr in truck_rows:
        if tr['idle_hours'] > 0 or tr['operating_hours'] > 0:
            idle_report.append(tr)

    ctx = {
        'start': start, 'end': end,
        'truck_rows': truck_rows,
        'driver_scores': driver_scores,
        'idle_report': idle_report,
        'total_distance': round(total_dist, 1),
        'total_fuel': round(total_fuel, 1),
        'total_operating': round(total_op, 2),
        'total_idle': round(total_idle, 2),
        'total_brake': total_brake,
        'total_accel': total_accel,
        'total_turn': total_turn,
        'total_efficiency': round(total_dist / total_fuel, 2) if total_fuel > 0 else None,
        'total_utilization': round(total_op / (total_op + total_idle) * 100, 1) if (total_op + total_idle) > 0 else None,
        'title': 'Weekly Performance Report',
    }
    return render(request, 'fleetops/weekly_report.html', ctx)


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

    date_str = request.POST.get('date', '')
    try:
        import_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('fleetops:daily_log')

    data_types = []
    if request.POST.get('type_trips'):
        data_types.append('trips')
    if request.POST.get('type_events'):
        data_types.append('events')
    if request.POST.get('type_fuel'):
        data_types.append('fuel')
    if not data_types:
        data_types = ['trips']

    if import_date:
        result = import_cartrack_data(import_date=import_date, data_types=data_types)
    else:
        days_back = int(request.POST.get('days_back', 1))
        result = import_cartrack_data(days_back=days_back, data_types=data_types)

    if result['success']:
        if result['processed'] > 0:
            messages.success(
                request,
                f"Cartrack import complete: {result['processed']} log(s) for {result['import_date']}."
            )
        else:
            msg = "No Cartrack data found for the selected date."
            if result['errors']:
                msg += ' ' + ' '.join(result['errors'])
            if result['trucks_found'] == 0:
                msg += ' No active trucks found.'
            messages.warning(request, msg)
    else:
        messages.error(request, f"Cartrack import failed: {result['error']}")
    return redirect('fleetops:daily_log')


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
