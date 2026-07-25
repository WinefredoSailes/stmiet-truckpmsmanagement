import os
import hashlib
import math
import logging
from datetime import date, timedelta, datetime
from django.db import models as db_models
from django.utils import timezone
from fleetops.models import DailyLog, DriverAssignment
from trucks.models import Truck

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


DEFAULT_API_URL = os.environ.get('TRACKSOLID_API_URL',
                                 'https://hk-open.tracksolidpro.com/route/rest')


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_ts(ts):
    try:
        return datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
    except (ValueError, IndexError, TypeError):
        return None


class TracksolidClient:
    def __init__(self, api_url=None, app_key='', app_secret='', user_id='', user_pwd_md5=''):
        self.api_url = (api_url or DEFAULT_API_URL).rstrip('/')
        self.app_key = app_key or os.environ.get('TRACKSOLID_APP_KEY', '')
        self.app_secret = app_secret or os.environ.get('TRACKSOLID_APP_SECRET', '')
        self.user_id = user_id or os.environ.get('TRACKSOLID_USER_ID', '')
        self.user_pwd_md5 = user_pwd_md5 or os.environ.get('TRACKSOLID_USER_PWD_MD5', '')
        self._token = None
        self._token_expiry = None

    def _now(self):
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    def _sign(self, params):
        sorted_keys = sorted(params.keys())
        raw = self.app_secret
        for k in sorted_keys:
            raw += k + str(params[k])
        raw += self.app_secret
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    def _call(self, method, private_params=None, use_token=True):
        url = self.api_url
        params = {
            'app_key': self.app_key,
            'format': 'json',
            'method': method,
            'sign_method': 'md5',
            'timestamp': self._now(),
            'v': '1.0',
        }
        if use_token:
            if not self._token:
                self._get_token()
            params['access_token'] = self._token
        if private_params:
            params.update(private_params)
        params['sign'] = self._sign(params)
        body = ''
        try:
            resp = requests.post(url, data=params, timeout=(5, 15))
            body = resp.text[:1000]
            if not resp.text.strip():
                return {'data': [], 'error': f'{method}: empty response (status {resp.status_code})'}
            data = resp.json()
            if data.get('exception') == 'java.lang.NullPointerException':
                err = (f'{method}: TrackSolid server returned NullPointerException. '
                       f'The /v1/oauth/getAccessToken endpoint has a server-side bug. '
                       f'Please contact TrackSolid support. | body: {body}')
                return {'data': [], 'error': err}
            if data.get('code') != 0:
                err = f"{method}: {data.get('message', '')} (code={data.get('code')})"
                err += f" | body: {body}"
                return {'data': [], 'error': err}
            return {'data': data.get('result', []), 'error': None}
        except Exception as e:
            return {'data': [], 'error': f'{type(e).__name__}: {e} | body: {body}'}

    def _get_token(self):
        private = {
            'user_id': self.user_id,
            'user_pwd_md5': self.user_pwd_md5,
            'expires_in': '3600',
        }
        result = self._call('jimi.oauth.token.get', private_params=private, use_token=False)
        if result['error']:
            raise RuntimeError(f"Token error: {result['error']}")
        data = result['data']
        if isinstance(data, dict):
            self._token = data.get('accessToken', data.get('access_token', ''))
        elif isinstance(data, list) and data:
            self._token = data[0].get('accessToken', '')
        if not self._token:
            raise RuntimeError('Failed to get TrackSolid access token')

    def list_devices(self):
        result = self._call('jimi.user.device.list', {'target': self.user_id})
        if result['error']:
            return result
        devices = result['data']
        if isinstance(devices, dict):
            devices = [devices]
        return {'data': devices, 'error': None}

    def device_detail(self, imei):
        return self._call('jimi.track.device.detail', {'imei': imei})

    def track_history(self, imei, begin_time, end_time):
        return self._call('jimi.device.track.list', {
            'imei': imei,
            'begin_time': begin_time,
            'end_time': end_time,
        })


def _process_track(points):
    if not points or not isinstance(points, list):
        return {}
    total_dist = 0.0
    speeds = []
    prev = None
    op_seconds = 0
    idle_seconds = 0
    acc_on_intervals = []
    acc_on_start = None

    for p in points:
        ts = _parse_ts(p.get('gpsTime', ''))
        if not ts:
            continue
        try:
            lat = float(p.get('lat', 0))
            lng = float(p.get('lng', 0))
            speed = float(p.get('gpsSpeed', 0))
        except (ValueError, TypeError):
            continue
        ignition = (p.get('ignition', '') or '').upper()
        acc_on = ignition in ('ON', '1', 'TRUE')

        speeds.append(speed)
        if prev is not None:
            total_dist += _haversine_km(prev['lat'], prev['lng'], lat, lng)
        prev = {'lat': lat, 'lng': lng, 'ts': ts, 'speed': speed, 'acc_on': acc_on}

        if acc_on:
            if acc_on_start is None:
                acc_on_start = ts
        else:
            if acc_on_start is not None:
                acc_on_intervals.append((acc_on_start, ts))
                acc_on_start = None

    if acc_on_start is not None:
        acc_on_intervals.append((acc_on_start, ts if ts else acc_on_start))

    for start, end in acc_on_intervals:
        delta = (end - start).total_seconds()
        op_seconds += delta

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        try:
            s1 = float(p1.get('gpsSpeed', 0))
            s2 = float(p2.get('gpsSpeed', 0))
        except (ValueError, TypeError):
            continue
        ign1 = (p1.get('ignition', '') or '').upper() in ('ON', '1', 'TRUE')
        ign2 = (p2.get('ignition', '') or '').upper() in ('ON', '1', 'TRUE')
        if ign1 and ign2:
            t1 = _parse_ts(p1.get('gpsTime', ''))
            t2 = _parse_ts(p2.get('gpsTime', ''))
            if t1 and t2:
                gap = (t2 - t1).total_seconds()
                if s1 < 5 and s2 < 5:
                    idle_seconds += gap

    speeds = [s for s in speeds if s > 0]
    max_speed = max(speeds) if speeds else None
    avg_speed = round(total_dist / (op_seconds / 3600), 1) if op_seconds > 0 else None
    return {
        'distance': round(total_dist, 1),
        'max_speed': round(max_speed, 1) if max_speed else None,
        'avg_speed': avg_speed,
        'op_hours': round(op_seconds / 3600, 2),
        'idle_hours': round(idle_seconds / 3600, 2),
    }


def import_tracksolid_data(import_date=None, import_date_end=None, days_back=1,
                           dry_run=False):
    if not REQUESTS_AVAILABLE:
        return {'success': False, 'error': 'requests library required'}

    client = TracksolidClient()
    if not client.app_key or not client.app_secret:
        return {'success': False,
                'error': 'TRACKSOLID_APP_KEY and TRACKSOLID_APP_SECRET required'}

    import_date = import_date or (date.today() - timedelta(days=days_back))
    import_date_end = import_date_end or import_date
    date_fmt = '%Y-%m-%d'

    result = {
        'success': True,
        'provider': 'tracksolid',
        'import_date': import_date,
        'import_date_end': import_date_end,
        'processed': 0,
        'errors': [],
        'dry_run': dry_run,
    }

    try:
        devices_r = client.list_devices()
    except RuntimeError as e:
        return {'success': False, 'error': str(e)}
    if devices_r['error']:
        result['errors'].append(f"Device list: {devices_r['error']}")
        return result

    devices = devices_r['data']
    if isinstance(devices, dict):
        devices = [devices]
    if not devices:
        result['errors'].append('No devices found on TrackSolid account')
        return result

    # Build plate → imei mapping
    plate_to_imei = {}
    for d in devices:
        plate = (d.get('vehicleNumber', '') or '').upper().strip()
        imei = (d.get('imei', '') or '').strip()
        if plate and imei:
            plate_to_imei[plate] = imei

    trucks = list(Truck.objects.filter(status='ACTIVE'))
    result['trucks_found'] = len(trucks)
    result['devices_found'] = len(plate_to_imei)

    current = import_date
    while current <= import_date_end:
        date_str = current.strftime(date_fmt)
        for truck in trucks:
            plate = truck.plate_number.upper().strip()
            imei = plate_to_imei.get(plate)
            if not imei:
                continue

            tr = client.track_history(imei, f'{date_str} 00:00:00', f'{date_str} 23:59:59')
            if tr['error']:
                result['errors'].append(f'{plate}: {tr["error"]}')
                continue

            points = tr['data']
            if isinstance(points, dict):
                points = [points]
            if not points:
                continue

            track = _process_track(points)
            if not track:
                continue

            # Get latest mileage from device detail
            detail = client.device_detail(imei)
            mileage = None
            if not detail['error']:
                dd = detail['data']
                if isinstance(dd, dict):
                    try:
                        mileage = int(float(dd.get('currentMileage', 0) or 0))
                    except (ValueError, TypeError):
                        pass

            defaults = {
                'distance_traveled_km': track['distance'],
                'max_speed_kmh': track['max_speed'],
                'avg_speed_kmh': track['avg_speed'],
                'operating_hours': track['op_hours'],
                'idle_hours': track['idle_hours'],
                'mileage_km': mileage if mileage else 0,
                'data_source': DailyLog.DataSource.CARTRACK,
            }

            # Assign driver
            driver = DriverAssignment.objects.filter(
                truck=truck, assigned_from__lte=current
            ).filter(
                db_models.Q(assigned_until__isnull=True) | db_models.Q(assigned_until__gte=current)
            ).select_related('driver').first()
            if driver:
                defaults['driver'] = driver.driver

            if dry_run:
                result['processed'] += 1
                continue

            DailyLog.objects.update_or_create(truck=truck, date=current, defaults=defaults)
            result['processed'] += 1

        current += timedelta(days=1)

    return result
