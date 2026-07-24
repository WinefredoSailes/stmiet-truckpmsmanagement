import os
from datetime import date, timedelta
from django.db import models
from django.utils import timezone
from fleetops.models import DailyLog, DriverAssignment
from trucks.models import Truck

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

def import_cartrack_data(import_date=None, days_back=1, api_token='', api_url='https://api.cartrack.com/v1', dry_run=False, data_types=None):
    if not REQUESTS_AVAILABLE:
        return {'success': False, 'error': 'requests library required. Run: pip install requests'}

    token = api_token or os.environ.get('CARTRACK_API_TOKEN', '')
    if not token:
        return {'success': False, 'error': 'No CARTRACK_API_TOKEN provided. Set env var or pass --api-token.'}

    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    import_date = import_date or (date.today() - timedelta(days=days_back))

    trucks = Truck.objects.filter(status='ACTIVE')

    result = {
        'success': True,
        'import_date': import_date,
        'trucks_found': trucks.count(),
        'processed': 0,
        'errors': [],
        'dry_run': dry_run,
    }

    data_types = data_types or ['trips', 'events', 'fuel']
    trips = []
    events = []
    fuel_entries = []

    try:
        if 'trips' in data_types:
            trips = _fetch_trips(headers, api_url, import_date)
        if 'events' in data_types:
            events = _fetch_events(headers, api_url, import_date)
        if 'fuel' in data_types:
            fuel_entries = _fetch_fuel(headers, api_url, import_date)
    except Exception:
        pass

    if not trips and not events:
        result['errors'].append('No trip or event data returned from Cartrack API.')

    events_by_vehicle = _organize_events(events)
    fuel_by_vehicle = _organize_fuel(fuel_entries)

    for truck in trucks:
        plate = truck.plate_number.upper()
        unit = truck.unit_number.upper()

        trip_match = _find_matching_trip(trips, plate, unit)
        if not trip_match:
            continue

        dist = float(trip_match.get('distance', trip_match.get('distanceKm', 0)) or 0)
        max_spd = trip_match.get('maxSpeed', trip_match.get('maxSpeedKmh', None))
        avg_spd = trip_match.get('averageSpeed', trip_match.get('avgSpeedKmh', None))
        idle = float(trip_match.get('idleTime', trip_match.get('idleHours', 0)) or 0)
        op_hrs = float(trip_match.get('engineHours', trip_match.get('runningHours', trip_match.get('movingHours', 0))) or 0)
        mileage = int(float(trip_match.get('odometerEnd', trip_match.get('endOdometer', 0)) or 0))
        eng_hrs = float(trip_match.get('engineHoursTotal', trip_match.get('totalEngineHours', 0)) or 0)

        ev = events_by_vehicle.get(plate, events_by_vehicle.get(unit, {}))
        fuel_l = fuel_by_vehicle.get(plate, fuel_by_vehicle.get(unit, None))

        defaults = {
            'mileage_km': mileage,
            'engine_hours': eng_hrs if eng_hrs else op_hrs,
            'fuel_liters': fuel_l,
            'idle_hours': idle,
            'operating_hours': op_hrs,
            'distance_traveled_km': dist,
            'max_speed_kmh': float(max_spd) if max_spd is not None else None,
            'avg_speed_kmh': float(avg_spd) if avg_spd is not None else None,
            'harsh_braking_count': ev.get('brake', 0),
            'harsh_acceleration_count': ev.get('accel', 0),
            'harsh_turning_count': ev.get('turn', 0),
            'data_source': DailyLog.DataSource.CARTRACK,
        }

        active = DriverAssignment.objects.filter(
            truck=truck,
            assigned_from__lte=import_date,
        ).filter(
            models.Q(assigned_until__isnull=True) |
            models.Q(assigned_until__gte=import_date)
        ).select_related('driver').first()
        if active:
            defaults['driver'] = active.driver

        if dry_run:
            result['processed'] += 1
            continue

        DailyLog.objects.update_or_create(
            truck=truck,
            date=import_date,
            defaults=defaults,
        )
        result['processed'] += 1

    return result


def _fetch_trips(headers, api_url, import_date):
    try:
        params = {
            'from': import_date.strftime('%Y-%m-%dT00:00:00Z'),
            'to': import_date.strftime('%Y-%m-%dT23:59:59Z'),
        }
        resp = requests.get(f'{api_url}/trips', headers=headers, params=params, timeout=(5, 10))
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', data if isinstance(data, list) else [])
    except Exception:
        return []


def _fetch_events(headers, api_url, import_date):
    try:
        params = {
            'from': import_date.strftime('%Y-%m-%dT00:00:00Z'),
            'to': import_date.strftime('%Y-%m-%dT23:59:59Z'),
            'types': 'HARSH_BRAKING,HARSH_ACCELERATION,HARSH_TURNING',
        }
        resp = requests.get(f'{api_url}/vehicle-events', headers=headers, params=params, timeout=(5, 10))
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', data if isinstance(data, list) else [])
    except Exception:
        return []


def _fetch_fuel(headers, api_url, import_date):
    try:
        params = {
            'from': import_date.strftime('%Y-%m-%dT00:00:00Z'),
            'to': import_date.strftime('%Y-%m-%dT23:59:59Z'),
        }
        resp = requests.get(f'{api_url}/fuel', headers=headers, params=params, timeout=(5, 10))
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', data if isinstance(data, list) else [])
    except Exception:
        return []


def _organize_events(events):
    by_vehicle = {}
    for ev in events:
        if isinstance(ev, dict):
            vid = ev.get('vehicleId', ev.get('vehiclePlate', ''))
            event_type = ev.get('type', ev.get('eventType', ''))
            if vid not in by_vehicle:
                by_vehicle[vid] = {'brake': 0, 'accel': 0, 'turn': 0}
            if 'BRAKE' in event_type.upper():
                by_vehicle[vid]['brake'] += 1
            elif 'ACCEL' in event_type.upper():
                by_vehicle[vid]['accel'] += 1
            elif 'TURN' in event_type.upper():
                by_vehicle[vid]['turn'] += 1
    return by_vehicle


def _organize_fuel(fuel_entries):
    by_vehicle = {}
    for fe in fuel_entries:
        if isinstance(fe, dict):
            vid = fe.get('vehicleId', fe.get('vehiclePlate', ''))
            liters = fe.get('liters', fe.get('quantity', fe.get('amount', 0)))
            try:
                by_vehicle[vid] = float(liters)
            except (ValueError, TypeError):
                pass
    return by_vehicle


def _find_matching_trip(trips, plate, unit):
    for t in trips:
        if isinstance(t, dict):
            t_plate = t.get('vehiclePlate', t.get('registration', '')).upper()
            t_unit = t.get('vehicleName', t.get('name', '')).upper()
            if plate in t_plate or unit in t_unit or plate in t_unit:
                return t
    return None
