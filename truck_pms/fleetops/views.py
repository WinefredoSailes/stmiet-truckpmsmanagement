from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Sum, Count, F, Case, Value, When, FloatField, Max
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
        return redirect(reverse('fleetops:daily_log') + f'?date={log_date}')
    return redirect('fleetops:daily_log')


# ── Fleet Performance Dashboard ──

@login_required
def fleet_performance(request):
    if not _staff_or_above(request.user):
        messages.error(request, 'Access denied.')
        return redirect('accounts:dashboard')
    start_str = request.GET.get('start', '')
    end_str = request.GET.get('end', '')
    week_str = request.GET.get('week', '')
    try:
        if start_str and end_str:
            date_start = timezone.datetime.strptime(start_str, '%Y-%m-%d').date()
            date_end = timezone.datetime.strptime(end_str, '%Y-%m-%d').date()
        elif week_str:
            date_start = timezone.datetime.strptime(week_str, '%Y-%m-%d').date()
            date_end = date_start + timedelta(days=6)
        else:
            today = date.today()
            date_start = today - timedelta(days=today.weekday())
            date_end = date_start + timedelta(days=6)
    except ValueError:
        today = date.today()
        date_start = today - timedelta(days=today.weekday())
        date_end = date_start + timedelta(days=6)
    qs = DailyLog.objects.filter(
        date__gte=date_start, date__lte=date_end
    ).values('truck_id').annotate(
        total_dist=Sum('distance_traveled_km'),
        total_fuel=Sum('fuel_liters'),
        total_op=Sum('operating_hours'),
        total_idle=Sum('idle_hours'),
        total_brake=Sum('harsh_braking_count'),
        total_accel=Sum('harsh_acceleration_count'),
        total_turn=Sum('harsh_turning_count'),
        avg_speed=Avg('avg_speed_kmh'),
        log_count=Count('id'),
        has_fuel=Count(Case(When(fuel_liters__gt=0, then=1), output_field=FloatField())),
    )
    qs_by_truck = {r['truck_id']: r for r in qs}
    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')
    perf = []
    for t in trucks:
        r = qs_by_truck.get(t.pk)
        if not r:
            continue
        d = float(r['total_dist'] or 0)
        f = float(r['total_fuel'] or 0)
        op = float(r['total_op'] or 0)
        idl = float(r['total_idle'] or 0)
        perf.append({
            'truck': t,
            'distance': round(d, 1),
            'fuel': round(f, 1) if r['has_fuel'] > 0 else None,
            'efficiency': round(d / f, 2) if f > 0 else None,
            'utilization': round(op / (op + idl) * 100, 1) if (op + idl) > 0 else None,
            'avg_speed': round(float(r['avg_speed'] or 0), 1) if r['avg_speed'] else None,
            'harsh_events': int(r['total_brake'] or 0) + int(r['total_accel'] or 0) + int(r['total_turn'] or 0),
            'log_count': r['log_count'],
        })
    return render(request, 'fleetops/fleet_performance.html', {
        'date_start': date_start,
        'date_end': date_end,
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

    # Truck-level SQL aggregation
    truck_qs = DailyLog.objects.filter(date__gte=start, date__lte=end).values('truck_id').annotate(
        dist=Sum('distance_traveled_km'),
        fuel=Sum('fuel_liters'),
        op=Sum('operating_hours'),
        idl=Sum('idle_hours'),
        bk=Sum('harsh_braking_count'),
        ac=Sum('harsh_acceleration_count'),
        tn=Sum('harsh_turning_count'),
        max_spd=Max('max_speed_kmh'),
        days=Count('id'),
    )
    qs_by_truck = {r['truck_id']: r for r in truck_qs}

    # Driver-level SQL aggregation
    driver_qs = DailyLog.objects.filter(date__gte=start, date__lte=end, driver__isnull=False).values(
        'driver_id', 'driver__name'
    ).annotate(
        dist=Sum('distance_traveled_km'),
        fuel=Sum('fuel_liters'),
        op=Sum('operating_hours'),
        idl=Sum('idle_hours'),
        bk=Sum('harsh_braking_count'),
        ac=Sum('harsh_acceleration_count'),
        tn=Sum('harsh_turning_count'),
    )

    trucks = Truck.objects.filter(status='ACTIVE').order_by('unit_number')

    # Preload active driver assignments
    active_assignments = {
        a.truck_id: a.driver.name
        for a in DriverAssignment.objects.filter(assigned_until__isnull=True).select_related('driver')
    }

    truck_rows, driver_scores, idle_report = [], [], []
    totals = {'dist': 0, 'fuel': 0, 'op': 0, 'idl': 0, 'bk': 0, 'ac': 0, 'tn': 0}

    for t in trucks:
        r = qs_by_truck.get(t.pk)
        if not r:
            continue
        d = float(r['dist'] or 0)
        f = float(r['fuel'] or 0)
        op = float(r['op'] or 0)
        idl = float(r['idl'] or 0)
        bk = int(r['bk'] or 0)
        ac = int(r['ac'] or 0)
        tn = int(r['tn'] or 0)
        max_spd = float(r['max_spd'] or 0) if r.get('max_spd') else 0
        days = r['days']
        util = round(op / (op + idl) * 100, 1) if (op + idl) > 0 else None
        idle_pct = round(idl / op * 100, 1) if op > 0 else None
        driver_name = active_assignments.get(t.pk) or 'Unassigned'

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
            'efficiency': round(d / f, 2) if f > 0 else None,
            'efficiency_kmpl': round(d / f, 2) if f > 0 else None,
            'efficiency_lph': round(f / op, 2) if op > 0 else None,
            'utilization': util,
            'idle_pct': idle_pct,
            'days': days,
        })
        idle_report.append(truck_rows[-1])
        totals['dist'] += d
        totals['fuel'] += f
        totals['op'] += op
        totals['idl'] += idl
        totals['bk'] += bk
        totals['ac'] += ac
        totals['tn'] += tn

    # Driver scores
    driver_scores = []
    for rd in driver_qs:
        d = float(rd['dist'] or 0)
        op = float(rd['op'] or 0)
        idl = float(rd['idl'] or 0)
        bk = int(rd['bk'] or 0)
        ac = int(rd['ac'] or 0)
        tn = int(rd['tn'] or 0)

        def _score(events, divisor, factor=5):
            if divisor <= 0: return 100
            return max(0, round(100 - (events / divisor * 100) * factor))

        brake_s = _score(bk, d)
        accel_s = _score(ac, d)
        turn_s = _score(tn, d)
        idle_pct = idl / (op + idl) * 100 if (op + idl) > 0 else 0
        idle_s = max(0, round(100 - idle_pct))
        avg_s = round((brake_s + accel_s + turn_s + idle_s) / 4, 2)
        driver_scores.append({
            'driver': {'name': rd['driver__name']},
            'distance': round(d, 1),
            'brake_score': brake_s,
            'accel_score': accel_s,
            'turn_score': turn_s,
            'idle_score': idle_s,
            'average_score': avg_s,
        })
    driver_scores.sort(key=lambda x: x['average_score'], reverse=True)

    ctx = {
        'start': start, 'end': end,
        'truck_rows': truck_rows,
        'driver_scores': driver_scores,
        'idle_report': idle_report,
        'total_distance': round(totals['dist'], 1),
        'total_fuel': round(totals['fuel'], 1),
        'total_operating': round(totals['op'], 2),
        'total_idle': round(totals['idl'], 2),
        'total_brake': totals['bk'],
        'total_accel': totals['ac'],
        'total_turn': totals['tn'],
        'total_efficiency': round(totals['dist'] / totals['fuel'], 2) if totals['fuel'] > 0 else None,
        'total_utilization': round(totals['op'] / (totals['op'] + totals['idl']) * 100, 1) if (totals['op'] + totals['idl']) > 0 else None,
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
