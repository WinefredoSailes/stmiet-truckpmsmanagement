from django.core.management.base import BaseCommand
from fleetops.cartrack_import import import_cartrack_data, REQUESTS_AVAILABLE, DEFAULT_API_URL
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Import daily data from Cartrack API for all active trucks'

    def add_arguments(self, parser):
        parser.add_argument('--api-token', default='', help='Cartrack API token')
        parser.add_argument('--api-url', default=DEFAULT_API_URL, help='Cartrack API base URL')
        parser.add_argument('--days-back', type=int, default=1, help='Days back to import (default: 1 = yesterday)')
        parser.add_argument('--dry-run', action='store_true', help='Print what would be done without saving')

    def handle(self, *args, **options):
        if not REQUESTS_AVAILABLE:
            self.stdout.write(self.style.ERROR(
                'The "requests" library is required. Install with: pip install requests'
            ))
            return

        import_date = date.today() - timedelta(days=options['days_back'])
        self.stdout.write(f'Importing data for {import_date}...')

        result = import_cartrack_data(
            import_date=import_date,
            api_token=options['api_token'],
            api_url=options['api_url'],
            dry_run=options['dry_run'],
        )

        if not result['success']:
            self.stdout.write(self.style.ERROR(result['error']))
            return

        self.stdout.write(f"{result['trucks_found']} active truck(s) found.")
        if result['errors']:
            for err in result['errors']:
                self.stdout.write(self.style.WARNING(err))

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f"Dry run: {result['processed']} truck(s) would be processed."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Import complete: {result['processed']} log(s) created/updated for {import_date}."
            ))
