import os
import base64
import logging
import time
from datetime import timedelta, datetime

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
        self._last_request = 0.0

    def _pace(self):
        """Keep requests within the API's 10/minute rate limit."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < 6.5:
            time.sleep(6.5 - elapsed)
        self._last_request = time.monotonic()

    def _fetch(self, endpoint, params):
        self._pace()
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
        r = self._safe_fetch('trips', params)
        if r['data']:
            logger.info('fetch_trips: %s – %s returned %d items', start_date, end, len(r['data']))
            logger.info('fetch_trips: first item keys=%s', list(r['data'][0].keys()))
            for field in ('trip_distance', 'end_odometer', 'clock_end', 'idle_time_seconds',
                          'trip_duration_seconds', 'max_speed', 'avgSpeed',
                          'harsh_braking_events', 'harsh_acceleration_events', 'harsh_cornering_events'):
                val = r['data'][0].get(field, '⚠️ MISSING')
                logger.info('fetch_trips: field "%-30s" = %s', field, val)
        else:
            logger.warning('fetch_trips: %s – %s returned 0 items (error=%s)', start_date, end, r.get('error'))
            if r.get('response_text'):
                logger.warning('fetch_trips: API response=%s', r['response_text'][:500])
        return r

    def fetch_events(self, start_date, end_date=None):
        end = end_date or start_date
        params = {'limit': '1000',
                  'start_timestamp': f'{start_date} 00:00:00',
                  'end_timestamp': f'{end} 23:59:59'}
        r = self._safe_fetch('vehicles/events', params)
        if r['data']:
            logger.info('fetch_events: %s – %s returned %d items', start_date, end, len(r['data']))
        else:
            logger.warning('fetch_events: %s – %s returned 0 items (error=%s)', start_date, end, r.get('error'))
        return r

    def fetch_fuel_consumed(self, registrations, start_date, end_date=None):
        """POST /fuel/consumed — FMS fuel-consumed sensor (sensor type 20).

        Requires the CAN-bus fuel-consumed sensor. Max 24h per request,
        max 100 registrations, rate limited to 10/min.
        """
        end = end_date or start_date
        payload = {
            'registrations': registrations,
            'start_timestamp': f'{start_date} 00:00:00',
            'end_timestamp': f'{end} 23:59:59',
            'limit': '100',
        }
        url = f'{self.api_url}/fuel/consumed'
        try:
            self._pace()
            resp = requests.post(
                url, headers=self.headers, json=payload, timeout=(3, 30)
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get('data', [])
            logger.info('fetch_fuel_consumed: %s – %s returned %d items',
                        start_date, end, len(items))
            return {'data': items, 'error': None}
        except Exception as e:
            status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})'}

    def fetch_fuel_level(self, registrations, start_date, end_date=None):
        """POST /fuel/level — tank level estimate (calibrated fuel sensor).

        Returns start/end tank level and estimated_fuel_used per vehicle.
        Max 24h per request, rate limited to 10/min.
        """
        end = end_date or start_date
        payload = {
            'registrations': registrations,
            'start_timestamp': f'{start_date} 00:00:00',
            'end_timestamp': f'{end} 23:59:59',
            'limit': '100',
        }
        url = f'{self.api_url}/fuel/level'
        try:
            self._pace()
            resp = requests.post(
                url, headers=self.headers, json=payload, timeout=(3, 30)
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get('data', [])
            logger.info('fetch_fuel_level: %s – %s returned %d items',
                        start_date, end, len(items))
            return {'data': items, 'error': None}
        except Exception as e:
            status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})'}

    def fetch_fuel_fills(self, registration, start_date, end_date=None):
        """GET /fuel/fills/{registration} — dated fill events (31-day max)."""
        end = end_date or start_date
        url = f'{self.api_url}/fuel/fills/{registration}'
        try:
            self._pace()
            resp = requests.get(url, headers=self.headers, timeout=(3, 30), params={
                'start_timestamp': f'{start_date} 00:00:00',
                'end_timestamp': f'{end} 23:59:59',
                'limit': '100',
            })
            resp.raise_for_status()
            data = resp.json()
            items = data.get('data', [])
            return {'data': items, 'error': None}
        except Exception as e:
            status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})'}

    def fetch_fuel_fills_all(self, start_date, end_date=None):
        """GET /fuel/fills — fill events for all fleet vehicles (24h max)."""
        end = end_date or start_date
        url = f'{self.api_url}/fuel/fills'
        try:
            self._pace()
            resp = requests.get(url, headers=self.headers, timeout=(3, 30), params={
                'start_timestamp': f'{start_date} 00:00:00',
                'end_timestamp': f'{end} 23:59:59',
                'limit': '100',
            })
            resp.raise_for_status()
            data = resp.json()
            items = data.get('data', [])
            return {'data': items, 'error': None}
        except Exception as e:
            status = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            return {'data': [], 'error': f'{type(e).__name__}: {e} (HTTP {status})'}





def _parse_date(ts, fallback):
    try:
        return datetime.strptime(ts[:10], '%Y-%m-%d').date()
    except (ValueError, IndexError, TypeError):
        return fallback


def _vehicle_id(entry):
    reg = entry.get('registration')
    plate = entry.get('vehiclePlate')
    return str(reg if reg is not None else (plate or '')).upper()


def _vehicle_id2(entry):
    return str(entry.get('vehicle_id', '') or '').upper()


def _as_list(data):
    """Normalize API `data` to a list.

    POST /fuel/* responses may return either a bare list or a dict keyed by
    registration; normalize whichever shape we get.
    """
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if 'registration' in data:
            return [data]
        return [v for v in data.values() if isinstance(v, dict)]
    return []


def _normal_list(data):
    """Alias of _as_list for readability at call sites."""
    return _as_list(data)


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
    latest = max((t for t in trips if t.get('end_timestamp') is not None),
                 key=lambda t: t.get('end_timestamp', ''), default={})
    total_dur = sum(float(t.get('trip_duration_seconds', 0) or 0) for t in trips)
    total_idle = sum(float(t.get('idle_time_seconds', 0) or 0) for t in trips)
    return {
        'distance': total_dist,
        'max_speed': max((float(t.get('max_speed', 0) or 0) for t in trips), default=None),
        'idle': total_idle / 3600,
        'op': max(total_dur - total_idle, 0) / 3600,
        'brake': sum(int(float(t.get('harsh_braking_events', 0) or 0)) for t in trips),
        'accel': sum(int(float(t.get('harsh_acceleration_events', 0) or 0)) for t in trips),
        'turn': sum(int(float(t.get('harsh_cornering_events', 0) or 0)) for t in trips),
        'speed': sum(
            int(float(t.get('thresholds_speeding_events', 0) or 0))
            + int(float(t.get('road_speeding_events', 0) or 0))
            for t in trips
        ),
        'idle_count': sum(int(float(t.get('events_idle', 0) or 0)) for t in trips),
        'mileage': int(float(latest.get('end_odometer', 0) or 0) / 1000),
        'eng_hrs': float(latest.get('clock_end', 0) or 0) / 3600,
    }


def import_cartrack_data(import_date=None, import_date_end=None, days_back=1, api_token='', api_username='', api_url=None, dry_run=False, data_types=None):
    if not REQUESTS_AVAILABLE:
        return {'success': False, 'error': 'requests library required. Run: pip install requests'}

    client = CartrackAPIClient(api_url=api_url, username=api_username, token=api_token)
    if not client.token:
        return {'success': False, 'error': 'No CARTRACK_API_TOKEN provided. Set env var or pass --api-token.'}

    import_date = import_date or (timezone.localdate() - timedelta(days=days_back))
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
        # /vehicles/events caps at 24h per request -> fetch per day
        events_all = []
        raw_errors = set()
        day = import_date
        while day <= import_date_end:
            r = client.fetch_events(day.strftime(date_fmt), day.strftime(date_fmt))
            if r['error']:
                raw_errors.add(r['error'])
            events_all.extend(r['data'])
            day += timedelta(days=1)
        if raw_errors:
            result['errors'].append('Events: ' + '; '.join(sorted(raw_errors)))
        events = events_all

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

    # ------------------------------------------------------------------
    # Fuel: per-day, per-vehicle resolution.
    # Priority per (vehicle, day):
    #   1. POST /fuel/consumed  -> fuel_consumed (CAN-bus, type 20)  [this fleet: none]
    #   2. POST /fuel/level     -> estimated_fuel_used (calibrated sensor)
    #   3. GET  /fuel/fills     -> sum of fill_amount_litres that day
    # Fuel is fetched per-day because the POST endpoints cap at 24h windows;
    # calls are spaced ~7s to respect the 10/minute rate limit.
    # ------------------------------------------------------------------
    fuel_by_date = {}      # date -> {upper_regsub: liters}
    fuel_warnings = set()
    fuel_endpoint = None
    if 'fuel' in data_types:
        registrations = [
            t.plate_number.strip().upper() for t in trucks
            if t.plate_number and t.plate_number.strip()
        ]
        registrations = list(dict.fromkeys(registrations))
        day = import_date
        while day <= import_date_end:
            day_str = day.strftime(date_fmt)
            day_fuel = {}

            r_con = client.fetch_fuel_consumed(registrations, day_str)
            for item in _as_list(r_con['data']):
                vid = str(item.get('registration', '')).upper()
                val = item.get('fuel_consumed') or item.get('fuel') or item.get('fuel_consumed_litres')
                if vid and val is not None:
                    try:
                        day_fuel[vid] = float(val)
                    except (ValueError, TypeError):
                        pass
            if r_con['error']:
                fuel_warnings.add(f'{day_str}: /fuel/consumed {r_con["error"]}')

            if day_fuel:
                fuel_endpoint = fuel_endpoint or 'fuel/consumed'
            else:
                r_lvl = client.fetch_fuel_level(registrations, day_str)
                for item in _normal_list(r_lvl['data']):
                    vid = str(item.get('registration', '')).upper()
                    val = item.get('estimated_fuel_used')
                    cal = item.get('calibrated', True) in (True, 'true', 1)
                    if vid and cal and val is not None:
                        try:
                            day_fuel[vid] = float(val)
                        except (ValueError, TypeError):
                            pass
                if r_lvl['error']:
                    fuel_warnings.add(f'{day_str}: /fuel/level {r_lvl["error"]}')
                if day_fuel:
                    fuel_endpoint = fuel_endpoint or 'fuel/level'

            if day_fuel:
                fuel_by_date[day] = day_fuel
            else:
                # last resort: fills for the day (fuel added, approximation)
                r_fills = client.fetch_fuel_fills_all(day_str)
                for fi in _normal_list(r_fills['data']):
                    vid = str(fi.get('registration', '')).upper()
                    amt = fi.get('fill_amount_litres') or fi.get('fill_amount_l')
                    if vid and amt is not None:
                        try:
                            day_fuel[vid] = day_fuel.get(vid, 0.0) + float(amt)
                        except (ValueError, TypeError):
                            pass
                if day_fuel:
                    fuel_by_date[day] = day_fuel
                    fuel_endpoint = fuel_endpoint or 'fuel/fills'
                if r_fills['error']:
                    fuel_warnings.add(f'{day_str}: /fuel/fills {r_fills["error"]}')

            day += timedelta(days=1)

    result['fuel_count'] = sum(len(v) for v in fuel_by_date.values())

    # Trucks with no per-vehicle fuel record anywhere in the range
    for truck in trucks:
        plate = truck.plate_number.upper() if truck.plate_number else ''
        unit = truck.unit_number.upper()
        covered = any(
            any(k == plate or k == unit or (plate and plate in k) or (unit and unit in k)
                for k in day_map)
            for day_map in fuel_by_date.values()
        )
        if not covered:
            fuel_warnings.add(f'Truck {unit} ({plate}): no Cartrack fuel sensor data for this range (blank, not fabricated).')

    result['fuel_warnings'] = sorted(fuel_warnings)
    result['fuel_endpoint'] = fuel_endpoint

    # Process each date
    current = import_date
    while current <= import_date_end:
        day_ev = ev_index.get(current, {})

        for truck in trucks:
            plate = truck.plate_number.strip().upper() if truck.plate_number else ''
            unit = truck.unit_number.strip().upper() if truck.unit_number else ''

            matched_trips = _match_vehicle(trips, plate, unit)

            if matched_trips:
                raw_dist = sum(float(t.get('trip_distance', 0) or 0) for t in matched_trips)
                raw_op = sum(float(t.get('trip_duration_seconds', 0) or 0) for t in matched_trips)
                raw_idle = sum(float(t.get('idle_time_seconds', 0) or 0) for t in matched_trips)
                raw_odo = max((float(t.get('end_odometer', 0) or 0) for t in matched_trips), default=0)
                raw_clock = max((float(t.get('clock_end', 0) or 0) for t in matched_trips), default=0)
                logger.info(
                    'import: %s (%s) date=%s trips=%d raw_dist_m=%.1f→km=%.2f '
                    'raw_op_s=%.0f→hr=%.2f raw_idle_s=%.0f→hr=%.2f '
                    'raw_odo_m=%.0f→km=%d raw_clock_s=%.0f→hr=%.2f',
                    truck.unit_number, plate, current, len(matched_trips),
                    raw_dist, raw_dist / 1000,
                    raw_op, raw_op / 3600,
                    raw_idle, raw_idle / 3600,
                    raw_odo, raw_odo / 1000,
                    raw_clock, raw_clock / 3600,
                )
            else:
                logger.info('import: %s (%s) date=%s no trips matched', truck.unit_number, plate, current)

            trip_data = _aggregate_trips(matched_trips)

            # Match events
            ev_counts = next(
                (v for k, v in day_ev.items() if k == plate or k == unit or (plate and plate in k) or (unit and unit in k)),
                {'brake': 0, 'accel': 0, 'turn': 0}
            )

            # Match fuel (per-day value from resolved fuel_by_date)
            fuel_l = None
            day_fuel = fuel_by_date.get(current, {})
            for k, v in day_fuel.items():
                if k == plate or k == unit or (plate and plate in k) or (unit and unit in k):
                    fuel_l = round(v, 2)
                    break

            if not trip_data and fuel_l is None:
                continue

            if trip_data:
                defaults = {
                    'mileage_km': trip_data['mileage'],
                    'engine_hours': round(trip_data['eng_hrs'], 2),
                    'fuel_liters': fuel_l,
                    'idle_hours': round(trip_data['idle'], 2),
                    'idle_count': trip_data['idle_count'],
                    'operating_hours': round(trip_data['op'], 2),
                    'distance_traveled_km': round(trip_data['distance'], 2),
                    'max_speed_kmh': round(trip_data['max_speed'], 1) if trip_data['max_speed'] else None,
                    'avg_speed_kmh': round(trip_data['distance'] / trip_data['op'], 1) if trip_data['op'] > 0 else None,
                    'harsh_braking_count': trip_data['brake'] + ev_counts['brake'],
                    'harsh_acceleration_count': trip_data['accel'] + ev_counts['accel'],
                    'harsh_turning_count': trip_data['turn'] + ev_counts['turn'],
                    'speeding_count': trip_data['speed'],
                    'data_source': DailyLog.DataSource.CARTRACK,
                }
            else:
                defaults = {
                    'fuel_liters': fuel_l,
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

            dl, created = DailyLog.objects.update_or_create(truck=truck, date=current, defaults=defaults)
            logger.info('import: saved %s %s id=%d data_source=%s dist=%.2f eng_hrs=%.2f fuel=%s '
                        'idle=%.2f op=%.2f mileage=%d',
                        truck.unit_number, current, dl.pk, defaults.get('data_source', '?'),
                        defaults.get('distance_traveled_km', 0), defaults.get('engine_hours', 0),
                        defaults.get('fuel_liters', '—'), defaults.get('idle_hours', 0),
                        defaults.get('operating_hours', 0), defaults.get('mileage_km', 0))
            result['processed'] += 1

        current += timedelta(days=1)

    logger.info('import: done date=%s – %s processed=%d errors=%d',
                import_date, import_date_end, result['processed'], len(result['errors']))
    return result
