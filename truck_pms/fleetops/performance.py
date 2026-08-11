"""Shared fleet performance aggregation.

Single source of truth for the per-truck / fleet aggregates used by the
dashboard tabs and the retained ``fleetops:fleet_performance`` URL, so
both render identical numbers. Date handling is Manila-local
(``timezone.localdate``) to match the Cartrack importer.
"""
from datetime import timedelta

from django.db.models import Avg, Sum, Count, Case, When, FloatField, Max
from django.utils import timezone

from trucks.models import Truck
from .models import DailyLog, DriverAssignment

_DATE_FMT = '%Y-%m-%d'


def _default_week():
    """Current week (Monday to Sunday), Manila local."""
    today = timezone.localdate()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def range_shortcuts():
    """Date shortcuts for the Fleet Performance tab header."""
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    return {
        'this_week': week_start,
        'last7_start': today - timedelta(days=6),
        'last7_end': today,
    }


def parse_range(request):
    """Parse ``?start=``/``?end=`` (or ``?week=``) into a (start, end) pair.

    Invalid input falls back to the current Monday-to-Sunday week.
    """
    start_str = request.GET.get('start', '')
    end_str = request.GET.get('end', '')
    week_str = request.GET.get('week', '')
    date_start = date_end = None
    try:
        if start_str:
            date_start = timezone.datetime.strptime(start_str, _DATE_FMT).date()
        if end_str:
            date_end = timezone.datetime.strptime(end_str, _DATE_FMT).date()
    except ValueError:
        date_start = date_end = None
    if week_str:
        try:
            date_start = timezone.datetime.strptime(week_str, _DATE_FMT).date()
            date_end = date_start + timedelta(days=6)
        except ValueError:
            date_start = date_end = None
    if date_start is None and date_end is None:
        return _default_week()
    if date_start is None:
        date_start = date_end
    if date_end is None:
        date_end = date_start
    if date_start > date_end:
        date_start, date_end = date_end, date_start
    return date_start, date_end


def _spark_points(values, width=100, height=28):
    """Normalize values into a polyline points string for an inline SVG."""
    if not values or max(values) <= 0:
        return ''
    mx = max(values)
    step = width / (len(values) - 1) if len(values) > 1 else width
    pts = []
    for i, v in enumerate(values):
        x = round(i * step, 1)
        y = round(height - 2 - (v / mx) * (height - 4), 1)
        pts.append(f'{x},{y}')
    return ' '.join(pts)


def _score(events, divisor, factor=5):
    if divisor <= 0:
        return 100
    return max(0, round(100 - (events / divisor * 100) * factor))


def _driver_scores(start, end):
    qs = DailyLog.objects.filter(
        date__gte=start, date__lte=end, driver__isnull=False
    ).values('driver_id', 'driver__name').annotate(
        dist=Sum('distance_traveled_km'),
        op=Sum('operating_hours'),
        idl=Sum('idle_hours'),
        bk=Sum('harsh_braking_count'),
        ac=Sum('harsh_acceleration_count'),
        tn=Sum('harsh_turning_count'),
    )
    scores = []
    for rd in qs:
        d = float(rd['dist'] or 0)
        op = float(rd['op'] or 0)
        idl = float(rd['idl'] or 0)
        brake_s = _score(int(rd['bk'] or 0), d)
        accel_s = _score(int(rd['ac'] or 0), d)
        turn_s = _score(int(rd['tn'] or 0), d)
        idle_pct = idl / (op + idl) * 100 if (op + idl) > 0 else 0
        idle_s = max(0, round(100 - idle_pct))
        scores.append({
            'driver': {'name': rd['driver__name']},
            'distance': round(d, 2),
            'brake_score': brake_s,
            'accel_score': accel_s,
            'turn_score': turn_s,
            'idle_score': idle_s,
            'average_score': round((brake_s + accel_s + turn_s + idle_s) / 4, 2),
        })
    scores.sort(key=lambda x: x['average_score'], reverse=True)
    return scores


def fleet_trend(start, end):
    """Daily fleet distance/fuel totals (zero-filled) for trend charts."""
    qs = DailyLog.objects.filter(
        date__gte=start, date__lte=end
    ).values('date').annotate(
        dist=Sum('distance_traveled_km'),
        fuel=Sum('fuel_liters'),
    )
    by_date = {r['date']: r for r in qs}
    days, dist, fuel = [], [], []
    cursor = start
    while cursor <= end:
        r = by_date.get(cursor)
        days.append(cursor.strftime('%m/%d'))
        dist.append(round(float(r['dist'] or 0), 1) if r else 0)
        fuel.append(round(float(r['fuel'] or 0), 1) if r else 0)
        cursor += timedelta(days=1)
    return {'days': days, 'dist': dist, 'fuel': fuel}


def compute_fleet_performance(start, end):
    """Aggregate ``DailyLog`` rows between ``start`` and ``end`` inclusive.

    Returns a context dict: ``performance`` rows (per active truck),
    ``driver_scores``, ``idle_report`` and fleet totals. Fuel is only
    reported for trucks that have actual fuel logs (``has_fuel`` gating),
    matching the Cartrack behaviour where some trucks have no sensor.
    """
    truck_qs = DailyLog.objects.filter(
        date__gte=start, date__lte=end
    ).values('truck_id').annotate(
        dist=Sum('distance_traveled_km'),
        fuel=Sum('fuel_liters'),
        op=Sum('operating_hours'),
        idl=Sum('idle_hours'),
        bk=Sum('harsh_braking_count'),
        ac=Sum('harsh_acceleration_count'),
        tn=Sum('harsh_turning_count'),
        max_spd=Max('max_speed_kmh'),
        avg_speed=Avg('avg_speed_kmh'),
        days=Count('id'),
        has_fuel=Count(Case(When(fuel_liters__gt=0, then=1), output_field=FloatField())),
    )
    qs_by_truck = {r['truck_id']: r for r in truck_qs}

    series_qs = DailyLog.objects.filter(
        date__gte=start, date__lte=end
    ).values('truck_id', 'date').annotate(d=Sum('distance_traveled_km'))
    series_by_truck = {}
    for r in series_qs:
        series_by_truck.setdefault(r['truck_id'], {})[r['date']] = float(r['d'] or 0)

    active_assignments = {
        a.truck_id: a.driver.name
        for a in DriverAssignment.objects.filter(assigned_until__isnull=True).select_related('driver')
    }

    rows = []
    totals = {'dist': 0.0, 'fuel': 0.0, 'op': 0.0, 'idl': 0.0, 'harsh': 0}
    for t in Truck.objects.filter(status='ACTIVE').order_by('unit_number'):
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
        has_fuel = r['has_fuel'] > 0
        row = {
            'truck': t,
            'driver_name': active_assignments.get(t.pk) or 'Unassigned',
            'distance': round(d, 2),
            'fuel': round(f, 1) if has_fuel else None,
            'operating_hours': round(op, 2),
            'idle_hours': round(idl, 2),
            'brake': bk,
            'accel': ac,
            'turn': tn,
            'harsh_total': bk + ac + tn,
            'max_speed': round(float(r['max_spd'] or 0), 1) if r.get('max_spd') else None,
            'avg_speed': round(float(r['avg_speed'] or 0), 1) if r.get('avg_speed') else None,
            'efficiency': round(d / f, 2) if has_fuel and f > 0 else None,
            'efficiency_lph': round(f / op, 2) if has_fuel and op > 0 else None,
            'utilization': round(op / (op + idl) * 100, 1) if (op + idl) > 0 else None,
            'idle_pct': round(idl / op * 100, 1) if op > 0 else None,
            'days': r['days'],
            'log_count': r['days'],
        }
        series = []
        cursor = start
        while cursor <= end:
            series.append(round(series_by_truck.get(t.pk, {}).get(cursor, 0), 1))
            cursor += timedelta(days=1)
        row['spark'] = series
        row['spark_points'] = _spark_points(series)
        rows.append(row)
        totals['dist'] += d
        totals['fuel'] += f
        totals['op'] += op
        totals['idl'] += idl
        totals['harsh'] += bk + ac + tn

    return {
        'performance': rows,
        'driver_scores': _driver_scores(start, end),
        'idle_report': sorted(rows, key=lambda r: r['idle_pct'] or 0, reverse=True),
        'fleet_trend': fleet_trend(start, end),
        'total_distance': round(totals['dist'], 2),
        'total_fuel': round(totals['fuel'], 1),
        'total_operating': round(totals['op'], 2),
        'total_idle': round(totals['idl'], 2),
        'total_harsh': totals['harsh'],
        'total_brake': sum(r['brake'] for r in rows),
        'total_accel': sum(r['accel'] for r in rows),
        'total_turn': sum(r['turn'] for r in rows),
        'total_efficiency': round(totals['dist'] / totals['fuel'], 2) if totals['fuel'] > 0 else None,
        'total_utilization': round(totals['op'] / (totals['op'] + totals['idl']) * 100, 1)
        if (totals['op'] + totals['idl']) > 0 else None,
        'truck_count': len(rows),
    }
