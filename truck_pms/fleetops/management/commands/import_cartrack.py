from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone
from fleetops.models import DailyLog, DriverAssignment
from trucks.models import Truck
from datetime import date, timedelta
import os

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class Command(BaseCommand):
    help = 'Import daily data from Cartrack API for all active trucks'

    def add_arguments(self, parser):
        parser.add_argument('--api-token', default='', help='Cartrack API token')
        parser.add_argument('--api-url', default='https://api.cartrack.com/v1', help='Cartrack API base URL')
        parser.add_argument('--days-back', type=int, default=1, help='Days back to import (default: 1 = yesterday)')
        parser.add_argument('--dry-run', action='store_true', help='Print what would be done without saving')

    def handle(self, *args, **options):
        if not REQUESTS_AVAILABLE:
            self.stdout.write(self.style.ERROR(
                'The "requests" library is required. Install with: pip install requests'
            ))
            return

        token = options['api_token'] or os.environ.get('CARTRACK_API_TOKEN', '')
        base_url = options['api_url']
        days_back = options['days_back']
        dry_run = options['dry_run']

        if not token:
            self.stdout.write(self.style.WARNING(
                'No CARTRACK_API_TOKEN provided. Set env var or pass --api-token.'
            ))
            return

        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        import_date = date.today() - timedelta(days=days_back)

        self.stdout.write(f'Importing data for {import_date}...')

        trucks = Truck.objects.filter(status='ACTIVE')
        self.stdout.write(f'{trucks.count()} active truck(s) found.')

        # Fetch trips for the date range
        self.stdout.write('Fetching trip data from Cartrack...')
        try:
            params = {
                'from': import_date.strftime('%Y-%m-%dT00:00:00Z'),
                'to': import_date.strftime('%Y-%m-%dT23:59:59Z'),
            }
            resp = requests.get(
                f'{base_url}/trips',
                headers=headers,
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            trips_data = resp.json()
            trips = trips_data.get('data', trips_data if isinstance(trips_data, list) else [])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch trips: {e}'))
            trips = []

        # Fetch vehicle events
        self.stdout.write('Fetching vehicle events...')
        try:
            params = {
                'from': import_date.strftime('%Y-%m-%dT00:00:00Z'),
                'to': import_date.strftime('%Y-%m-%dT23:59:59Z'),
                'types': 'HARSH_BRAKING,HARSH_ACCELERATION,HARSH_TURNING',
            }
            resp = requests.get(
                f'{base_url}/vehicle-events',
                headers=headers,
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            events_data = resp.json()
            events = events_data.get('data', events_data if isinstance(events_data, list) else [])
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not fetch events (non-critical): {e}'))
            events = []

        # Fetch fuel data
        self.stdout.write('Fetching fuel data...')
        try:
            params = {
                'from': import_date.strftime('%Y-%m-%dT00:00:00Z'),
                'to': import_date.strftime('%Y-%m-%dT23:59:59Z'),
            }
            resp = requests.get(
                f'{base_url}/fuel',
                headers=headers,
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            fuel_data = resp.json()
            fuel_entries = fuel_data.get('data', fuel_data if isinstance(fuel_data, list) else [])
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not fetch fuel data (non-critical): {e}'))
            fuel_entries = []

        # Organize events by vehicle
        events_by_vehicle = {}
        for ev in events:
            if isinstance(ev, dict):
                vid = ev.get('vehicleId', ev.get('vehiclePlate', ''))
                event_type = ev.get('type', ev.get('eventType', ''))
                if vid not in events_by_vehicle:
                    events_by_vehicle[vid] = {'brake': 0, 'accel': 0, 'turn': 0}
                if 'BRAKE' in event_type.upper():
                    events_by_vehicle[vid]['brake'] += 1
                elif 'ACCEL' in event_type.upper():
                    events_by_vehicle[vid]['accel'] += 1
                elif 'TURN' in event_type.upper():
                    events_by_vehicle[vid]['turn'] += 1

        # Organize fuel by vehicle
        fuel_by_vehicle = {}
        for fe in fuel_entries:
            if isinstance(fe, dict):
                vid = fe.get('vehicleId', fe.get('vehiclePlate', ''))
                liters = fe.get('liters', fe.get('quantity', fe.get('amount', 0)))
                try:
                    fuel_by_vehicle[vid] = float(liters)
                except (ValueError, TypeError):
                    pass

        processed = 0
        for truck in trucks:
            plate = truck.plate_number.upper()
            unit = truck.unit_number.upper()

            # Find matching trip data
            trip_match = None
            for t in trips:
                if isinstance(t, dict):
                    t_plate = t.get('vehiclePlate', t.get('registration', '')).upper()
                    t_unit = t.get('vehicleName', t.get('name', '')).upper()
                    if plate in t_plate or unit in t_unit or plate in t_unit:
                        trip_match = t
                        break

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

            # Look up active driver
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
                self.stdout.write(f'  Would update {truck.unit_number}: {dist}km, {fuel_l}L')
                continue

            log, created = DailyLog.objects.update_or_create(
                truck=truck,
                date=import_date,
                defaults=defaults,
            )
            processed += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Dry run: {processed} truck(s) would be processed.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Import complete: {processed} log(s) created/updated for {import_date}.'
            ))
