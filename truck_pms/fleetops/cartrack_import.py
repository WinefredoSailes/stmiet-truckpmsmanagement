import os
import base64
from datetime import date, timedelta, datetime
from django.db import models
from django.utils import timezone
from fleetops.models import DailyLog, DriverAssignment
from trucks.models import Truck

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

DEFAULT_API_URL = os.environ.get('CARTRACK_API_URL', 'https://fleetapi-ph.cartrack.com/rest')


def import_cartrack_data(import_date=None, import_date_end=None, days_back=1, api_token='', api_username='', api_url=None, dry_run=False, data_types=None):
    if not REQUESTS_AVAILABLE:
        return {'success': False, 'error': 'requests library required. Run: pip install requests'}

    api_url = api_url or DEFAULT_API_URL
    token = api_token or os.environ.get('CARTRACK_API_TOKEN', '')
    if not token:
        return {'success': False, 'error': 'No CARTRACK_API_TOKEN provided. Set env var or pass --api-token.'}

    username = api_username or os.environ.get('CARTRACK_API_USERNAME', 'SEVE00001')
    encoded = base64.b64encode(f'{username}:{token}'.encode()).decode()
    headers = {'Authorization': f'Basic {encoded}', 'Accept': 'application/json'}
    import_date = import_date or (date.today() - timedelta(days=days_back))
    import_date_end = import_date_end or import_date

    trucks = Truck.objects.filter(status='ACTIVE')

    result = {
        'success': True,
        'import_date': import_date,
        'import_date_end': import_date_end,
        'trucks_found': trucks.count(),
        'processed': 0,
        'errors': [],
        'dry_run': dry_run,
    }

    data_types = data_types or ['trips', 'events', 'fuel']
    trips = []
    events = []
    fuel_entries = []

    if 'trips' in data_types:
        t = _fetch_trips(headers, api_url, import_date, import_date_end)
        if t['error']:
            result['errors'].append(f'Trips API: {t["error"]}')
        trips = t['data']
    if 'events' in data_types:
        e = _fetch_events(headers, api_url, import_date, import_date_end)
        if e['error']:
            result['errors'].append(f'Events API: {e["error"]}')
        events = e['data']
    if 'fuel' in data_types:
        f = _fetch_fuel(headers, api_url, import_date, import_date_end)
        if f['error']:
            result['errors'].append(f'Fuel API: {f["error"]}')
        fuel_entries = f['data']

    if not trips and not events:
        result['errors'].append('No trip or event data returned from Cartrack API.')

    # Group data by date for range imports
    trips_by_date = _group_trips_by_date(trips, import_date)
    events_by_date = _group_events_by_date(events, import_date)
    fuel_by_date = _group_fuel_by_date(fuel_entries, import_date)

    current = import_date
    while current <= import_date_end:
        day_trips = trips_by_date.get(current, [])
        day_events_by_vehicle = events_by_date.get(current, {})
        day_fuel_by_vehicle = fuel_by_date.get(current, {})

        for truck in trucks:
            plate = truck.plate_number.upper()
            unit = truck.unit_number.upper()

            matching_trips = _matching_trips(day_trips, plate, unit)
            if not matching_trips:
                continue

            total_dist = sum(float(t.get('trip_distance', 0) or 0) for t in matching_trips) / 1000
            max_spd = max((t.get('max_speed', 0) or 0 for t in matching_trips), default=None)
            total_idle = sum(float(t.get('idle_time_seconds', 0) or 0) for t in matching_trips) / 3600
            total_op = sum(float(t.get('trip_duration_seconds', 0) or 0) for t in matching_trips) / 3600
            trips_brake = sum(int(t.get('harsh_braking_events', 0) or 0) for t in matching_trips)
            trips_accel = sum(int(t.get('harsh_acceleration_events', 0) or 0) for t in matching_trips)
            trips_turn = sum(int(t.get('harsh_cornering_events', 0) or 0) for t in matching_trips)
            total_idle_count = sum(int(t.get('events_idle', 0) or 0) for t in matching_trips)
            latest = max(matching_trips, key=lambda t: t.get('end_timestamp', ''))
            mileage = int(float(latest.get('end_odometer', 0) or 0) / 1000)
            eng_hrs = float(latest.get('clock_end', 0) or 0) / 3600

            ev = day_events_by_vehicle.get(plate, day_events_by_vehicle.get(unit, {}))
            fuel_l = day_fuel_by_vehicle.get(plate, day_fuel_by_vehicle.get(unit, None))

            defaults = {
                'mileage_km': mileage,
                'engine_hours': round(eng_hrs, 1),
                'fuel_liters': round(float(fuel_l), 2) if fuel_l else None,
                'idle_hours': round(total_idle, 2),
                'idle_count': total_idle_count,
                'operating_hours': round(total_op, 2),
                'distance_traveled_km': round(total_dist, 1),
                'max_speed_kmh': round(float(max_spd), 1) if max_spd else None,
                'avg_speed_kmh': round(total_dist / total_op, 1) if total_op > 0 else None,
                'harsh_braking_count': trips_brake + ev.get('brake', 0),
                'harsh_acceleration_count': trips_accel + ev.get('accel', 0),
                'harsh_turning_count': trips_turn + ev.get('turn', 0),
                'data_source': DailyLog.DataSource.CARTRACK,
            }

            active = DriverAssignment.objects.filter(
                truck=truck,
                assigned_from__lte=current,
            ).filter(
                models.Q(assigned_until__isnull=True) |
                models.Q(assigned_until__gte=current)
            ).select_related('driver').first()
            if active:
                defaults['driver'] = active.driver

            if dry_run:
                result['processed'] += 1
                continue

            DailyLog.objects.update_or_create(
                truck=truck,
                date=current,
                defaults=defaults,
            )
            result['processed'] += 1

        current += timedelta(days=1)

    return result


def _fetch_trips(headers, api_url, start_date, end_date=None):
    end_date = end_date or start_date
    try:
        params = {
            'limit': '1000',
            'start_timestamp': f'{start_date.strftime("%Y-%m-%d")} 00:00:00',
            'end_timestamp': f'{end_date.strftime("%Y-%m-%d")} 23:59:59',
        }
        resp = requests.get(f'{api_url}/trips', headers=headers, params=params, timeout=(3, 30))
        resp.raise_for_status()
        data = resp.json()
        items = data.get('data', data if isinstance(data, list) else [])
        return {'data': items, 'error': None}
    except Exception as e:
        status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        text = (getattr(e.response, 'text', '') or '')[:300] if hasattr(e, 'response') else ''
        return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})', 'response_text': text}


def _fetch_events(headers, api_url, start_date, end_date=None):
    end_date = end_date or start_date
    try:
        params = {
            'limit': '1000',
            'start_timestamp': f'{start_date.strftime("%Y-%m-%d")} 00:00:00',
            'end_timestamp': f'{end_date.strftime("%Y-%m-%d")} 23:59:59',
        }
        resp = requests.get(f'{api_url}/vehicles/events', headers=headers, params=params, timeout=(3, 30))
        resp.raise_for_status()
        data = resp.json()
        items = data.get('data', data if isinstance(data, list) else [])
        return {'data': items, 'error': None}
    except Exception as e:
        status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        text = (getattr(e.response, 'text', '') or '')[:300] if hasattr(e, 'response') else ''
        return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})', 'response_text': text}


def _fetch_fuel(headers, api_url, start_date, end_date=None):
    end_date = end_date or start_date
    try:
        params = {
            'limit': '1000',
            'start_timestamp': f'{start_date.strftime("%Y-%m-%d")} 00:00:00',
            'end_timestamp': f'{end_date.strftime("%Y-%m-%d")} 23:59:59',
        }
        resp = requests.get(f'{api_url}/fuel/fills', headers=headers, params=params, timeout=(3, 30))
        resp.raise_for_status()
        data = resp.json()
        items = data.get('data', data if isinstance(data, list) else [])
        return {'data': items, 'error': None}
    except Exception as e:
        status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        text = (getattr(e.response, 'text', '') or '')[:300] if hasattr(e, 'response') else ''
        return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})', 'response_text': text}


def _parse_date(ts, fallback):
    try:
        return datetime.strptime(ts[:10], '%Y-%m-%d').date()
    except (ValueError, IndexError, TypeError):
        return fallback


def _group_trips_by_date(trips, fallback_date):
    by_date = {}
    for trip in trips:
        if not isinstance(trip, dict):
            continue
        d = _parse_date(trip.get('end_timestamp', ''), fallback_date)
        by_date.setdefault(d, []).append(trip)
    return by_date


def _group_events_by_date(events, fallback_date):
    by_date = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        d = _parse_date(ev.get('event_timestamp', ev.get('timestamp', '')), fallback_date)
        vid = ev.get('registration', ev.get('vehiclePlate', '')).upper()
        event_type = ev.get('event_description', ev.get('eventType', ''))
        bucket = by_date.setdefault(d, {})
        counts = bucket.setdefault(vid, {'brake': 0, 'accel': 0, 'turn': 0})
        if 'BRAKE' in event_type.upper():
            counts['brake'] += 1
        elif 'ACCEL' in event_type.upper():
            counts['accel'] += 1
        elif 'TURN' in event_type.upper() or 'CORNERING' in event_type.upper():
            counts['turn'] += 1
    return by_date


def _group_fuel_by_date(fuel_entries, fallback_date):
    by_date = {}
    for fe in fuel_entries:
        if not isinstance(fe, dict):
            continue
        d = _parse_date(fe.get('fill_timestamp', fe.get('timestamp', fe.get('date', ''))), fallback_date)
        vid = fe.get('registration', fe.get('vehiclePlate', '')).upper()
        liters = fe.get('fill_amount_litres', fe.get('liters', fe.get('quantity', fe.get('amount', 0))))
        try:
            by_date.setdefault(d, {})[vid] = float(liters)
        except (ValueError, TypeError):
            pass
    return by_date


def _matching_trips(trips, plate, unit):
    """Return all trips matching the given truck plate/unit."""
    exact = []
    for t in trips:
        if isinstance(t, dict):
            t_plate = t.get('registration', t.get('vehiclePlate', '')).upper()
            t_unit = t.get('vehicleName', t.get('name', '')).upper()
            if plate == t_plate or unit == t_unit or plate == t_unit:
                exact.append(t)
    if exact:
        return exact
    # Fall back to substring match
    loose = []
    for t in trips:
        if isinstance(t, dict):
            t_plate = t.get('registration', t.get('vehiclePlate', '')).upper()
            t_unit = t.get('vehicleName', t.get('name', '')).upper()
            if (plate and plate in t_plate) or (unit and unit in t_unit) or (plate and plate in t_unit):
                loose.append(t)
    return loose
