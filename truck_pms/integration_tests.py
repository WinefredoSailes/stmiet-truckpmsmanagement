"""
Integration tests for the critical data chain:
  Cartrack API Import -> DailyLog.save() -> Truck.current_mileage_km/current_engine_hours -> PMSchedule.status()

This ensures that pulling Cartrack data correctly:
1. Creates DailyLog entries with correct unit conversions
2. Updates Truck mileage and engine hours via DailyLog.save()
3. Affects PM schedule status (due/overdue calculations)
"""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from trucks.models import Truck
from fleetops.models import DailyLog
from pms.models import TaskCategory, TaskTemplate, PMSchedule
from fleetops.cartrack_import import import_cartrack_data

# Disable Cartrack API calls during tests
TEST_TOKEN = 'test_token_123'
TEST_USERNAME = 'SEVE00001'


def create_truck(**kw):
    defaults = dict(
        unit_number='T-INT', plate_number='INT-001',
        make='Isuzu', model='FVR', year=2020,
        status='ACTIVE', current_mileage_km=5000,
        current_engine_hours=250,
    )
    defaults.update(kw)
    return Truck.objects.create(**defaults)


def create_category():
    return TaskCategory.objects.create(name='Engine', description='Engine tasks')


def create_template(category, **kw):
    defaults = dict(
        category=category, name='Change Oil',
        interval_type='MILEAGE', interval_value=5000,
        estimated_labor_hours=1.0,
    )
    defaults.update(kw)
    return TaskTemplate.objects.create(**defaults)


class CartrackToPmIntegrationTests(TestCase):
    """Test the full data pipeline from Cartrack import to PM schedule updates."""

    def setUp(self):
        self.truck = create_truck()
        self.cat = create_category()
        # Create a PM schedule with 5000km interval, last done at 0km
        self.tmpl = create_template(self.cat, interval_type='MILEAGE', interval_value=5000)
        self.schedule = PMSchedule.objects.create(
            truck=self.truck,
            task_template=self.tmpl,
            is_active=True,
            last_mileage_km=0,
        )
        self.today = timezone.now().date()

    def _make_trip_data(self, plate, dist_m, op_s, idle_s, odo_m, clock_s, max_spd=60):
        """Helper to create a single trip dict matching Cartrack API format."""
        return {
            'registration': plate,
            'trip_distance': float(dist_m),
            'trip_duration_seconds': float(op_s),
            'idle_time_seconds': float(idle_s),
            'end_odometer': float(odo_m),
            'clock_end': float(clock_s),
            'max_speed': float(max_spd),
            'harsh_braking_events': 1,
            'harsh_acceleration_events': 0,
            'harsh_cornering_events': 0,
            'end_timestamp': f'{self.today.isoformat()} 12:00:00',
        }

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_updates_truck_mileage(self, mock_client_cls):
        """Pulling 200km of trip data should update truck mileage via DailyLog.save()."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = TEST_TOKEN
        mock_client.fetch_trips.return_value = {
            'data': [self._make_trip_data(
                'INT-001',
                dist_m=200000.0,   # 200 km
                op_s=28800.0,       # 8 hours
                idle_s=1800.0,      # 0.5 hours
                odo_m=5200000.0,    # 5200 km
                clock_s=360000.0,   # 100 hours
            )],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel.return_value = {
            'data': [{'registration': 'INT-001', 'fuel_consumed_litres': 80.0}],
            'error': None, 'endpoint': 'reports/fuel-efficiency',
        }

        result = import_cartrack_data(
            import_date=self.today,
            api_token=TEST_TOKEN, api_username=TEST_USERNAME,
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['processed'], 1)

        # Verify DailyLog was created with correct dist/eng hrs precision
        log = DailyLog.objects.get(truck=self.truck, date=self.today)
        self.assertAlmostEqual(float(log.distance_traveled_km), 200.0, places=2)
        self.assertAlmostEqual(float(log.engine_hours), 100.0, places=2)
        self.assertEqual(log.mileage_km, 5200)
        self.assertEqual(log.data_source, DailyLog.DataSource.CARTRACK)

        # Verify Truck mileage was updated by DailyLog.save()
        self.truck.refresh_from_db()
        self.assertEqual(self.truck.current_mileage_km, 5200)
        self.assertEqual(float(self.truck.current_engine_hours), 100.0)

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_triggers_pm_due_status(self, mock_client_cls):
        """
        Import enough km to push the truck past the PM interval.
        The schedule should change from 'no_data' to 'due' or 'overdue'.
        """
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = TEST_TOKEN
        # Trip distance = 6000km, which exceeds the 5000km PM interval
        mock_client.fetch_trips.return_value = {
            'data': [self._make_trip_data(
                'INT-001',
                dist_m=6000000.0,  # 6000 km
                op_s=36000.0,
                idle_s=1800.0,
                odo_m=11000000.0,   # 11000 km (was at 5000, now 11000 = 6000 traveled)
                clock_s=720000.0,
            )],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel.return_value = {
            'data': [{'registration': 'INT-001', 'fuel_consumed_litres': 500.0}],
            'error': None, 'endpoint': 'reports/fuel-efficiency',
        }

        # Before import: truck at 5000km, schedule last at 0km, interval 5000
        self.truck.current_mileage_km = 5000
        self.truck.save()

        result = import_cartrack_data(
            import_date=self.today,
            api_token=TEST_TOKEN, api_username=TEST_USERNAME,
        )
        self.assertTrue(result['success'])

        # After import: truck at 5000 + 6000 = 11000km
        # Schedule last at 0km, interval 5000, so next_due = 5000
        # Current mileage 11000 > 5000, so status should be 'overdue'
        self.truck.refresh_from_db()
        self.assertEqual(self.truck.current_mileage_km, 11000)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status(), 'overdue')

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_fuel_fallback_distribution(self, mock_client_cls):
        """Fuel fetched once for date range gets distributed evenly across days."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = TEST_TOKEN
        mock_client.fetch_trips.return_value = {
            'data': [self._make_trip_data(
                'INT-001', dist_m=100000.0, op_s=14400.0,
                idle_s=600.0, odo_m=5100000.0, clock_s=180000.0,
            )],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        # Fuel returned as single value for a 2-day range
        mock_client.fetch_fuel.return_value = {
            'data': [{'registration': 'INT-001', 'fuel_consumed_litres': 100.0}],
            'error': None, 'endpoint': 'reports/fuel-efficiency',
        }

        start = self.today
        end = self.today + timedelta(days=1)

        result = import_cartrack_data(
            import_date=start, import_date_end=end,
            api_token=TEST_TOKEN, api_username=TEST_USERNAME,
        )
        self.assertTrue(result['success'])
        logs = DailyLog.objects.filter(truck=self.truck, date__gte=start, date__lte=end)
        # Each day should get 50L (100L / 2 days)
        for log in logs:
            if log.fuel_liters is not None:
                self.assertAlmostEqual(float(log.fuel_liters), 50.0, places=1)

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_multiple_trucks(self, mock_client_cls):
        """Import processes all active trucks."""
        truck2 = create_truck(
            unit_number='T-INT2', plate_number='INT-002',
            current_mileage_km=3000,
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = TEST_TOKEN
        mock_client.fetch_trips.return_value = {
            'data': [
                self._make_trip_data(
                    'INT-001', dist_m=50000.0, op_s=7200.0,
                    idle_s=300.0, odo_m=5050000.0, clock_s=90000.0,
                ),
                self._make_trip_data(
                    'INT-002', dist_m=75000.0, op_s=10800.0,
                    idle_s=600.0, odo_m=3075000.0, clock_s=126000.0,
                ),
            ],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel.return_value = {'data': [], 'error': None, 'endpoint': 'none'}

        result = import_cartrack_data(
            import_date=self.today,
            api_token=TEST_TOKEN, api_username=TEST_USERNAME,
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['processed'], 2)
        self.assertEqual(DailyLog.objects.filter(date=self.today).count(), 2)

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_data_types_filtering(self, mock_client_cls):
        """Only requested data types are fetched."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = TEST_TOKEN

        result = import_cartrack_data(
            import_date=self.today, data_types=['trips'],
            api_token=TEST_TOKEN, api_username=TEST_USERNAME,
        )
        mock_client.fetch_trips.assert_called_once()
        mock_client.fetch_events.assert_not_called()
        mock_client.fetch_fuel.assert_not_called()
