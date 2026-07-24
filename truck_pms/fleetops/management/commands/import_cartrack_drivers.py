from django.core.management.base import BaseCommand, CommandError
from fleetops.models import Driver, DriverAssignment
from trucks.models import Truck
from django.db.models import Q
import os
import base64
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class Command(BaseCommand):
    help = 'One-time import of drivers from Cartrack API'

    def add_arguments(self, parser):
        parser.add_argument('--api-token', default='', help='Cartrack API token/password')
        parser.add_argument('--api-username', default='', help='Cartrack API username (default: SEVE00001)')
        parser.add_argument('--api-url', default='https://fleetapi-ph.cartrack.com/rest', help='Cartrack API base URL')

    def handle(self, *args, **options):
        if not REQUESTS_AVAILABLE:
            self.stdout.write(self.style.ERROR(
                'The "requests" library is required. Install with: pip install requests'
            ))
            return

        token = options['api_token'] or os.environ.get('CARTRACK_API_TOKEN', '')
        base_url = options['api_url']

        if not token:
            self.stdout.write(self.style.WARNING(
                'No CARTRACK_API_TOKEN provided. Set env var or pass --api-token.'
            ))
            return

        username = os.environ.get('CARTRACK_API_USERNAME', 'SEVE00001')
        encoded = base64.b64encode(f'{username}:{token}'.encode()).decode()
        headers = {'Authorization': f'Basic {encoded}', 'Accept': 'application/json'}

        # Fetch drivers from Cartrack
        self.stdout.write('Fetching drivers from Cartrack...')
        try:
            resp = requests.get(f'{base_url}/drivers', headers=headers, timeout=(3, 5))
            resp.raise_for_status()
            cartrack_drivers = resp.json().get('data', resp.json() if isinstance(resp.json(), list) else [])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch drivers: {e}'))
            return

        self.stdout.write(f'Found {len(cartrack_drivers)} driver(s) in Cartrack.')

        created = 0
        updated = 0
        for cd in cartrack_drivers:
            if isinstance(cd, dict):
                name = cd.get('name', cd.get('driverName', ''))
                license_num = cd.get('licenseNumber', cd.get('license', ''))
                mobile = cd.get('phone', cd.get('mobile', ''))
                license_expiry_str = cd.get('licenseExpiry', cd.get('licenseExpiryDate', ''))
            else:
                continue

            if not name or not license_num:
                continue

            license_expiry = None
            if license_expiry_str:
                try:
                    license_expiry = datetime.strptime(license_expiry_str[:10], '%Y-%m-%d').date()
                except ValueError:
                    try:
                        license_expiry = datetime.strptime(license_expiry_str[:10], '%d/%m/%Y').date()
                    except ValueError:
                        pass

            if not license_expiry:
                license_expiry = datetime.now().date()

            driver, was_created = Driver.objects.update_or_create(
                license_number=license_num,
                defaults={
                    'name': name,
                    'mobile': mobile,
                    'license_expiry': license_expiry,
                    'notes': 'Imported from Cartrack',
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Import complete: {created} created, {updated} updated.'
        ))

        # Try to fetch vehicle-driver linkages
        self.stdout.write('Fetching vehicle-driver linkages...')
        try:
            resp = requests.get(f'{base_url}/vehicle-driver-linkage', headers=headers, timeout=(3, 5))
            resp.raise_for_status()
            linkages = resp.json().get('data', resp.json() if isinstance(resp.json(), list) else [])
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not fetch linkages (non-critical): {e}'))
            linkages = []

        assignments = 0
        for link in linkages:
            if isinstance(link, dict):
                driver_ref = link.get('driverId', link.get('driverLicense', ''))
                vehicle_ref = link.get('vehicleId', link.get('vehiclePlate', link.get('vehicleReg', '')))
            else:
                continue

            driver = None
            if driver_ref:
                driver = Driver.objects.filter(
                    Q(license_number=driver_ref) | Q(pk=driver_ref)
                ).first()

            truck = None
            if vehicle_ref:
                truck = Truck.objects.filter(
                    Q(plate_number__iexact=vehicle_ref) |
                    Q(unit_number__iexact=vehicle_ref)
                ).first()

            if driver and truck:
                DriverAssignment.objects.get_or_create(
                    driver=driver,
                    truck=truck,
                    assigned_from=datetime.now().date(),
                    defaults={'assigned_until': None}
                )
                assignments += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {assignments} driver-truck linkage(s).'
        ))
