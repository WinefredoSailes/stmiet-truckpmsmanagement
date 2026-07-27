import os
import base64
import logging
from datetime import date, timedelta, datetime

logger = logging.getLogger(__name__)
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


class CartrackAPIClient:
    def __init__(self, api_url=None, username='', token=''):
        self.api_url = (api_url or DEFAULT_API_URL).rstrip('/')
        self.username = username or os.environ.get('CARTRACK_API_USERNAME', 'SEVE00001')
        self.token = token or os.environ.get('CARTRACK_API_TOKEN', '')
        encoded = base64.b64encode(f'{self.username}:{self.token}'.encode()).decode()
        self.headers = {'Authorization': f'Basic {encoded}', 'Accept': 'application/json'}

    def _fetch(self, endpoint, params):
        url = f'{self.api_url}/{endpoint.lstrip("/")}'
        resp = requests.get(url, headers=self.headers, params=params, timeout=(3, 30))
        resp.raise_for_status()
        data = resp.json()
        return data.get('data', data if isinstance(data, list) else [])

    def _safe_fetch(self, endpoint, params):
        try:
            return {'data': self._fetch(endpoint, params), 'error': None}
        except Exception as e:
            status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            text = (getattr(e.response, 'text', '') or '')[:300] if hasattr(e, 'response') else ''
            return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})', 'response_text': text}

    def fetch_trips(self, start_date, end_date=None):
        end = end_date or start_date
        params = {'limit': '1000',
                  'start_timestamp': f'{start_date} 00:00:00',
                  'end_timestamp': f'{end} 23:59:59'}
        return self._safe_fetch('trips', params)

    def fetch_events(self, start_date, end_date=None):
        end = end_date or start_date
        params = {'limit': '1000',
                  'start_timestamp': f'{start_date} 00:00:00',
                  'end_timestamp': f'{end} 23:59:59'}
        return self._safe_fetch('vehicles/events', params)

    def fetch_fuel(self, start_date, end_date=None):
        """Try fuel efficiency report endpoint (preferred) then fall back to /fuel/fills."""
        end = end_date or start_date
        params = {'start_date': start_date, 'end_date': end, 'limit': '1000'}
        for ep in ('reports/fuel-efficiency', 'reports/fuelefficiency'):
            try:
                resp = requests.get(f'{self.api_url}/{ep}', headers=self.headers, params=params, timeout=(3, 8))
                if resp.status_code == 422:
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data.get('data', data if isinstance(data, list) else [])
                if items:
                    return {'data': items, 'error': None, 'endpoint': ep}
            except Exception:
                continue
        # Fallback: /fuel/fills
        try:
            p = {'start_timestamp': f'{start_date} 00:00:00', 'end_timestamp': f'{end} 23:59:59', 'limit': '1000'}
            resp = requests.get(f'{self.api_url}/fuel/fills', headers=self.headers, params=p, timeout=(3, 8))
            if resp.status_code != 422:
                resp.raise_for_status()
                data = resp.json()
                items = data.get('data', data if isinstance(data, list) else [])
                if items:
                    return {'data': items, 'error': None, 'endpoint': 'fuel/fills'}
        except Exception:
            pass
        return {'data': [], 'error': 'No data', 'endpoint': 'none'}


    def get_positions(self):
        """Fetch current positions. Tries dedicated endpoint, falls back to latest trip end position."""
        # Try dedicated position endpoints first
        for ep in ['position', 'positions', 'vehicles/position']:
            try:
                resp = requests.get(f'{self.api_url}/{ep}', headers=self.headers, timeout=(3, 10))
                logger.info('get_positions: %s status=%d body=%s', ep, resp.status_code, resp.text[:300])
                if resp.status_code == 404:
                    continue
                if resp.status_code in (422, 403):
                    continue
                resp.raise_for_status()
                data = resp.json()
                items = data if isinstance(data, list) else data.get('data', [])
                if items:
                    return {'data': items, 'error': None, 'endpoint': ep}
            except Exception as e:
                logger.warning('get_positions: %s exception %s', ep, e)
                continue
        # Fallback: use latest trip end location as current position
        logger.info('get_positions: falling back to latest trip positions')
        raw = ''
        resp = None
        try:
            today = date.today()
            params = {'limit': '200', 'start_timestamp': f'{today - timedelta(days=14)} 00:00:00',
                      'end_timestamp': f'{today} 23:59:59'}
            resp = requests.get(f'{self.api_url}/trips', headers=self.headers, params=params, timeout=(3, 15))
            resp.raise_for_status()
            raw = resp.text[:2000]
            logger.info('get_positions: trips response status=%d body=%s', resp.status_code, raw[:500])
            json_data = resp.json()
            trips = json_data.get('data', json_data if isinstance(json_data, list) else [])
            if not trips:
                return {'data': [], 'error': f'No trips found', 'endpoint': 'trips_fallback', 'sample': raw[:2000]}
            if len(trips) > 0:
                logger.info('get_positions: first trip keys=%s sample=%s', list(trips[0].keys()), str(trips[0])[:800])
            # Group by vehicle, take latest trip's end location
            by_vehicle = {}
            for t in trips:
                vid = _vehicle_id(t)
                ts = t.get('end_timestamp', '')
                if vid and ts:
                    if vid not in by_vehicle or ts > by_vehicle[vid]['end_timestamp']:
                        by_vehicle[vid] = t
            positions = []
            for vid, trip in by_vehicle.items():
                lat = trip.get('endLatitude') or trip.get('end_latitude') or trip.get('latitude')
                lng = trip.get('endLongitude') or trip.get('end_longitude') or trip.get('longitude')
                if lat is None or lng is None:
                    continue
                try:
                    lat, lng = float(lat), float(lng)
                except (ValueError, TypeError):
                    continue
                if lat == 0 and lng == 0:
                    continue
                positions.append({
                    'registration': vid,
                    'latitude': lat,
                    'longitude': lng,
                    'speed': trip.get('avgSpeed', trip.get('max_speed', 0)),
                    'heading': trip.get('heading', trip.get('direction', 0)),
                    'eventTime': trip.get('end_timestamp', ''),
                })
            if not positions:
                return {'data': [], 'error': f'No lat/lng in trips data', 'endpoint': 'trips_fallback', 'sample': raw[:2000]}
            logger.info('get_positions: trip fallback got %d positions', len(positions))
            return {'data': positions, 'error': None, 'endpoint': 'trips_fallback', 'sample': raw[:2000]}
        except Exception as e:
            logger.error('get_positions: trip fallback failed %s', e)
            sample = raw[:500] if raw else str(e)[:300]
            return {'data': [], 'error': f'Trip fallback failed: {e}', 'endpoint': 'trips_fallback', 'sample': sample}


def _parse_date(ts, fallback):
    try:
        return datetime.strptime(ts[:10], '%Y-%m-%d').date()
    except (ValueError, IndexError, TypeError):
        return fallback


def _vehicle_id(entry):
    return entry.get('registration', entry.get('vehiclePlate', '')).upper()


def _vehicle_id2(entry):
    return str(entry.get('vehicle_id', '')).upper()


def _group_by_date(items, date_field, fallback_date):
    grouped = {}
    for item in items:
        d = _parse_date(item.get(date_field, item.get('timestamp', '')), fallback_date)
        grouped.setdefault(d, []).append(item)
    return grouped


def _match_vehicle(items, plate, unit, key_fn=_vehicle_id):
    """Return all items matching either plate or unit (exact then substring)."""
    if not items:
        return []
    key = key_fn
    exact = [i for i in items if key(i) == plate or key(i) == unit or plate == key(i)]
    if exact:
        return exact
    return [i for i in items if (plate and plate in key(i)) or (unit and unit in key(i)) or (plate and plate in key(i))]


def _aggregate_trips(trips):
    if not trips:
        return {}
    total_dist = sum(float(t.get('trip_distance', 0) or 0) for t in trips) / 1000
    latest = max(trips, key=lambda t: t.get('end_timestamp', ''))
    return {
        'distance': total_dist,
        'max_speed': max((float(t.get('max_speed', 0) or 0) for t in trips), default=None),
        'idle': sum(float(t.get('idle_time_seconds', 0) or 0) for t in trips) / 3600,
        'op': sum(float(t.get('trip_duration_seconds', 0) or 0) for t in trips) / 3600,
        'brake': sum(int(t.get('harsh_braking_events', 0) or 0) for t in trips),
        'accel': sum(int(t.get('harsh_acceleration_events', 0) or 0) for t in trips),
        'turn': sum(int(t.get('harsh_cornering_events', 0) or 0) for t in trips),
        'idle_count': sum(int(t.get('events_idle', 0) or 0) for t in trips),
        'mileage': int(float(latest.get('end_odometer', 0) or 0) / 1000),
        'eng_hrs': float(latest.get('clock_end', 0) or 0) / 3600,
    }


def import_cartrack_data(import_date=None, import_date_end=None, days_back=1, api_token='', api_username='', api_url=None, dry_run=False, data_types=None):
    if not REQUESTS_AVAILABLE:
        return {'success': False, 'error': 'requests library required. Run: pip install requests'}

    client = CartrackAPIClient(api_url=api_url, username=api_username, token=api_token)
    if not client.token:
        return {'success': False, 'error': 'No CARTRACK_API_TOKEN provided. Set env var or pass --api-token.'}

    import_date = import_date or (date.today() - timedelta(days=days_back))
    import_date_end = import_date_end or import_date
    date_fmt = '%Y-%m-%d'

    trucks = list(Truck.objects.filter(status='ACTIVE'))
    result = {
        'success': True,
        'import_date': import_date,
        'import_date_end': import_date_end,
        'trucks_found': len(trucks),
        'processed': 0,
        'errors': [],
        'dry_run': dry_run,
    }

    data_types = data_types or ['trips', 'events', 'fuel']
    trips = events = []

    if 'trips' in data_types:
        r = client.fetch_trips(import_date.strftime(date_fmt), import_date_end.strftime(date_fmt))
        if r['error']:
            result['errors'].append(f'Trips: {r["error"]}')
        trips = r['data']
    if 'events' in data_types:
        r = client.fetch_events(import_date.strftime(date_fmt), import_date_end.strftime(date_fmt))
        if r['error']:
            result['errors'].append(f'Events: {r["error"]}')
        events = r['data']

    if not trips and not events and 'trips' in data_types:
        result['errors'].append('No trip or event data returned from Cartrack API.')

    # Group events by date
    events_by_date = _group_by_date(events, 'event_timestamp', import_date)

    # Index events by vehicle under each date
    ev_index = {}
    for d, items in events_by_date.items():
        idx = {}
        for ev in items:
            vid = _vehicle_id(ev)
            t = ev.get('event_description', ev.get('eventType', ''))
            c = idx.setdefault(vid, {'brake': 0, 'accel': 0, 'turn': 0})
            if 'BRAKE' in t.upper(): c['brake'] += 1
            elif 'ACCEL' in t.upper(): c['accel'] += 1
            elif 'TURN' in t.upper() or 'CORNERING' in t.upper(): c['turn'] += 1
        ev_index[d] = idx

    # Fetch fuel once upfront (report gives range aggregates)
    fuel_by_vehicle = {}
    fuel_endpoint = None
    if 'fuel' in data_types:
        r = client.fetch_fuel(import_date.strftime(date_fmt), import_date_end.strftime(date_fmt))
        if r['endpoint'] and r['endpoint'] != 'none':
            fuel_endpoint = r['endpoint']
        for fe in r['data']:
            ltrs = None
            for key in ('fuel_consumed_litres', 'fuelConsumedLitres', 'fuel_consumed_l',
                        'fuel_consumed', 'total_fuel_consumed', 'fill_amount_litres',
                        'liters', 'quantity', 'amount', 'volume'):
                val = fe.get(key)
                if val is not None:
                    try:
                        ltrs = float(val)
                        break
                    except (ValueError, TypeError):
                        continue
            if ltrs is not None:
                vid = _vehicle_id(fe)
                vid2 = _vehicle_id2(fe)
                fuel_by_vehicle[vid] = ltrs
                if vid2:
                    fuel_by_vehicle[vid2] = ltrs

    days_in_range = (import_date_end - import_date).days + 1 if import_date_end else 1
    result['fuel_count'] = len(fuel_by_vehicle)

    # Process each date
    current = import_date
    while current <= import_date_end:
        day_ev = ev_index.get(current, {})

        for truck in trucks:
            plate = truck.plate_number.upper()
            unit = truck.unit_number.upper()

            trip_data = _aggregate_trips(_match_vehicle(trips, plate, unit))

            # Match events
            ev_counts = next(
                (v for k, v in day_ev.items() if k == plate or k == unit or (plate and plate in k) or (unit and unit in k)),
                {'brake': 0, 'accel': 0, 'turn': 0}
            )

            # Match fuel (distribute range total evenly across days)
            fuel_l = None
            if fuel_by_vehicle:
                for k, v in fuel_by_vehicle.items():
                    if k == plate or k == unit or (plate and plate in k) or (unit and unit in k):
                        fuel_l = round(v / days_in_range, 2)
                        break

            if not trip_data and fuel_l is None:
                continue

            if trip_data:
                defaults = {
                    'mileage_km': trip_data['mileage'],
                    'engine_hours': round(trip_data['eng_hrs'], 1),
                    'fuel_liters': round(fuel_l, 2) if fuel_l else None,
                    'idle_hours': round(trip_data['idle'], 2),
                    'idle_count': trip_data['idle_count'],
                    'operating_hours': round(trip_data['op'], 2),
                    'distance_traveled_km': round(trip_data['distance'], 1),
                    'max_speed_kmh': round(trip_data['max_speed'], 1) if trip_data['max_speed'] else None,
                    'avg_speed_kmh': round(trip_data['distance'] / trip_data['op'], 1) if trip_data['op'] > 0 else None,
                    'harsh_braking_count': trip_data['brake'] + ev_counts['brake'],
                    'harsh_acceleration_count': trip_data['accel'] + ev_counts['accel'],
                    'harsh_turning_count': trip_data['turn'] + ev_counts['turn'],
                    'data_source': DailyLog.DataSource.CARTRACK,
                }
            else:
                defaults = {
                    'fuel_liters': round(fuel_l, 2) if fuel_l else None,
                    'data_source': DailyLog.DataSource.CARTRACK,
                }

            driver = DriverAssignment.objects.filter(
                truck=truck, assigned_from__lte=current
            ).filter(
                models.Q(assigned_until__isnull=True) | models.Q(assigned_until__gte=current)
            ).select_related('driver').first()
            if driver:
                defaults['driver'] = driver.driver

            if dry_run:
                result['processed'] += 1
                continue

            DailyLog.objects.update_or_create(truck=truck, date=current, defaults=defaults)
            result['processed'] += 1

        current += timedelta(days=1)

    if fuel_endpoint:
        result['fuel_endpoint'] = fuel_endpoint
    return result
