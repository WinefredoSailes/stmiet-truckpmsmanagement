from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from fleetops.models import Driver, DriverAssignment
from trucks.models import Truck

# Truck -> driver name mapping from the Cartrack Risk Report
MAPPING = {
    'JAR1707': 'Duane Roy',
    'KAP8160': 'Reynelie Flores',
    'MAM2396': 'Adonis Venailos',
    'MAW7645': 'Ivan Jay',
    'CBR3869': 'Reynan Pagasian',
}


class Command(BaseCommand):
    help = 'Seed DriverAssignment records from the known truck->driver mapping'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default='',
                            help='Assignment date YYYY-MM-DD (default: today)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Print what would be done without saving')

    def handle(self, *args, **options):
        assign_date = timezone.localdate()
        if options['date']:
            try:
                assign_date = timezone.datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid --date format. Use YYYY-MM-DD.'))
                return

        created = 0
        errors = []
        for plate, name in MAPPING.items():
            truck = Truck.objects.filter(
                Q(plate_number__iexact=plate) | Q(unit_number__iexact=plate)
            ).first()
            if not truck:
                errors.append(f'{plate}: no truck found')
                continue

            driver = None
            name_lower = name.lower().strip()
            candidates = Driver.objects.all()
            # exact name match first, then first-name+last-name containment
            for d in candidates:
                if d.name.strip().lower() == name_lower:
                    driver = d
                    break
            if not driver:
                for d in candidates:
                    d_lower = d.name.strip().lower()
                    if all(part in d_lower for part in name_lower.split()):
                        driver = d
                        break
            if not driver:
                errors.append(f'{plate}: driver "{name}" not found')
                continue

            if options['dry_run']:
                self.stdout.write(f'WOULD assign {driver.name} -> {truck.unit_number} from {assign_date}')
                continue

            _, was_created = DriverAssignment.objects.get_or_create(
                driver=driver,
                truck=truck,
                assigned_from=assign_date,
                defaults={'assigned_until': None},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f'Assigned {driver.name} -> {truck.unit_number} from {assign_date}'
                ))
            else:
                self.stdout.write(
                    f'{driver.name} -> {truck.unit_number} already assigned on {assign_date}'
                )

        for err in errors:
            self.stdout.write(self.style.WARNING(err))
        if not options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'Done: {created} assignment(s) created.'))
