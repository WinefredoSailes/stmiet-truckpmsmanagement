import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from trucks.models import Truck
from .models import Driver, DriverAssignment, DailyLog
from . import tracksolid_import
from .tracksolid_import import (
    _haversine_km, _parse_ts, _process_track,
    TracksolidClient, import_tracksolid_data,
)


class DriverModelTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(
            name='Test Driver',
            license_number='DL-001',
            license_expiry=timezone.now().date() + timezone.timedelta(days=60),
        )

    def test_driver_creation(self):
        self.assertEqual(str(self.driver), 'Test Driver (DL-001)')

    def test_license_status_ok(self):
        self.assertEqual(self.driver.license_status(), 'ok')

    def test_license_status_due_soon(self):
        self.driver.license_expiry = timezone.now().date() + timezone.timedelta(days=15)
        self.assertEqual(self.driver.license_status(), 'due_soon')

    def test_license_status_overdue(self):
        self.driver.license_expiry = timezone.now().date() - timezone.timedelta(days=1)
        self.assertEqual(self.driver.license_status(), 'overdue')

    def test_license_status_unknown(self):
        self.driver.license_expiry = None
        self.assertEqual(self.driver.license_status(), 'unknown')


class TruckComplianceTests(TestCase):
    def setUp(self):
        self.truck = Truck.objects.create(
            unit_number='TEST-001',
            plate_number='TEST001',
            make='Isuzu',
            model='Forward',
            year=2020,
            or_expiry=timezone.now().date() + timezone.timedelta(days=90),
            cr_expiry=timezone.now().date() + timezone.timedelta(days=45),
            fire_conveyance_expiry=timezone.now().date() + timezone.timedelta(days=10),
            dost_calibration_expiry=timezone.now().date() - timezone.timedelta(days=5),
        )

    def test_compliance_items_count(self):
        items = self.truck.compliance_items()
        self.assertEqual(len(items), 4)

    def test_compliance_ok(self):
        items = self.truck.compliance_items()
        self.assertEqual(items[0]['status'], 'ok')

    def test_compliance_due_soon(self):
        items = self.truck.compliance_items()
        self.assertEqual(items[2]['status'], 'due_soon')

    def test_compliance_overdue(self):
        items = self.truck.compliance_items()
        self.assertEqual(items[3]['status'], 'overdue')

    def test_compliance_unknown(self):
        self.truck.cr_expiry = None
        items = self.truck.compliance_items()
        self.assertEqual(items[1]['status'], 'unknown')


class DailyLogModelTests(TestCase):
    def setUp(self):
        self.truck = Truck.objects.create(
            unit_number='TEST-002',
            plate_number='TEST002',
            make='Isuzu', model='NLR', year=2022,
        )
        self.log = DailyLog.objects.create(
            truck=self.truck,
            date=timezone.now().date(),
            mileage_km=5000,
            engine_hours=100,
            fuel_liters=50,
            distance_traveled_km=400,
            idle_hours=2,
            operating_hours=8,
            harsh_braking_count=3,
            harsh_acceleration_count=1,
            harsh_turning_count=2,
        )

    def test_fuel_efficiency(self):
        self.assertEqual(self.log.fuel_efficiency(), 8.0)

    def test_utilization_rate(self):
        self.assertEqual(self.log.utilization_rate(), 80.0)

    def test_total_harsh_events(self):
        self.assertEqual(self.log.total_harsh_events(), 6)

    def test_save_updates_truck(self):
        self.truck.refresh_from_db()
        self.assertEqual(self.truck.current_mileage_km, 5000)
        self.assertEqual(float(self.truck.current_engine_hours), 100)


class ViewAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', password='test123', role=User.Role.ADMIN
        )
        self.staff = User.objects.create_user(
            username='staff', password='test123', role=User.Role.STAFF
        )
        self.mechanic = User.objects.create_user(
            username='mech', password='test123', role=User.Role.MECHANIC
        )

    def test_daily_log_admin(self):
        self.client.login(username='admin', password='test123')
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_staff(self):
        self.client.login(username='staff', password='test123')
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_mechanic_denied(self):
        self.client.login(username='mech', password='test123')
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 302)

    def test_drivers_admin(self):
        self.client.login(username='admin', password='test123')
        resp = self.client.get(reverse('fleetops:driver_list'))
        self.assertEqual(resp.status_code, 200)

    def test_drivers_staff_denied(self):
        self.client.login(username='staff', password='test123')
        resp = self.client.get(reverse('fleetops:driver_list'))
        self.assertEqual(resp.status_code, 302)

    def test_compliance_staff(self):
        self.client.login(username='staff', password='test123')
        resp = self.client.get(reverse('fleetops:compliance_dashboard'))
        self.assertEqual(resp.status_code, 200)


class TracksolidUtilsTests(TestCase):
    def test_haversine_km_zero_distance(self):
        self.assertEqual(_haversine_km(0, 0, 0, 0), 0.0)

    def test_haversine_km_known_distance(self):
        d = _haversine_km(14.5995, 120.9842, 14.5500, 121.0000)
        self.assertAlmostEqual(d, 5.9, delta=1.0)

    def test_haversine_km_manila_to_quezon(self):
        d = _haversine_km(14.5995, 120.9842, 14.6760, 121.0437)
        self.assertAlmostEqual(d, 10.0, delta=2.0)

    def test_parse_ts_valid(self):
        dt = _parse_ts('2025-07-25 14:30:00')
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.month, 7)
        self.assertEqual(dt.day, 25)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)

    def test_parse_ts_invalid(self):
        self.assertIsNone(_parse_ts('not-a-date'))
        self.assertIsNone(_parse_ts(''))
        self.assertIsNone(_parse_ts(None))

    def test_parse_ts_edge_cases(self):
        self.assertIsNone(_parse_ts('2025-07-25T14:30:00'))

    def test_process_track_empty(self):
        self.assertEqual(_process_track([]), {})
        self.assertEqual(_process_track(None), {})

    def test_process_track_single_point(self):
        pts = [{'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5', 'lng': '121.0', 'gpsSpeed': '0', 'ignition': 'ON'}]
        r = _process_track(pts)
        self.assertIsNotNone(r)
        self.assertEqual(r['distance'], 0.0)
        self.assertEqual(r['max_speed'], None)
        self.assertEqual(r['avg_speed'], None)

    def test_process_track_moving(self):
        pts = [
            {'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5995', 'lng': '120.9842', 'gpsSpeed': '40', 'ignition': 'ON'},
            {'gpsTime': '2025-07-25 08:30:00', 'lat': '14.5500', 'lng': '121.0000', 'gpsSpeed': '50', 'ignition': 'ON'},
        ]
        r = _process_track(pts)
        self.assertGreater(r['distance'], 0)
        self.assertEqual(r['max_speed'], 50.0)
        self.assertIsNotNone(r['avg_speed'])
        self.assertGreater(r['op_hours'], 0)
        self.assertEqual(r['idle_hours'], 0)

    def test_process_track_idle_detected(self):
        pts = [
            {'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5995', 'lng': '120.9842', 'gpsSpeed': '0', 'ignition': 'ON'},
            {'gpsTime': '2025-07-25 08:15:00', 'lat': '14.5995', 'lng': '120.9842', 'gpsSpeed': '0', 'ignition': 'ON'},
        ]
        r = _process_track(pts)
        self.assertGreater(r['idle_hours'], 0)
        self.assertGreater(r['op_hours'], 0)

    def test_process_track_ignition_off(self):
        pts = [
            {'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5995', 'lng': '120.9842', 'gpsSpeed': '0', 'ignition': 'OFF'},
            {'gpsTime': '2025-07-25 08:30:00', 'lat': '14.5500', 'lng': '121.0000', 'gpsSpeed': '0', 'ignition': 'OFF'},
        ]
        r = _process_track(pts)
        self.assertEqual(r.get('op_hours', 0), 0)
        self.assertEqual(r.get('idle_hours', 0), 0)


class TracksolidClientTests(TestCase):
    def setUp(self):
        self.client = TracksolidClient(
            api_url='https://test.api/rest',
            app_key='KEY',
            app_secret='SECRET',
            user_id='USER',
            user_pwd_md5='MD5',
        )

    def test_sign_consistency(self):
        params = {'app_key': 'KEY', 'format': 'json', 'method': 'test.method', 'v': '1.0'}
        s1 = self.client._sign(params)
        s2 = self.client._sign(params)
        self.assertEqual(s1, s2)
        self.assertEqual(len(s1), 32)
        self.assertTrue(s1.isupper())
        self.assertTrue(s1.isalnum())

    def test_sign_changes_with_params(self):
        s1 = self.client._sign({'a': '1', 'b': '2'})
        s2 = self.client._sign({'a': '1', 'b': '3'})
        self.assertNotEqual(s1, s2)

    @patch('requests.post')
    def test_get_token_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'code': 0,
            'result': {'accessToken': 'test_token_123'}
        }
        mock_post.return_value = mock_resp

        self.client._get_token()
        self.assertEqual(self.client._token, 'test_token_123')

    @patch('requests.post')
    def test_get_token_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'code': 1, 'message': 'Auth failed'}
        mock_post.return_value = mock_resp

        with self.assertRaises(RuntimeError):
            self.client._get_token()

    @patch('fleetops.tracksolid_import.TracksolidClient._call')
    def test_list_devices(self, mock_call):
        mock_call.return_value = {
            'data': [
                {'imei': '869066063765607', 'vehicleNumber': 'GNN403', 'deviceName': 'Device1'},
                {'imei': '869247060084669', 'vehicleNumber': 'NKC4763', 'deviceName': 'Device2'},
            ],
            'error': None,
        }
        r = self.client.list_devices()
        self.assertIsNone(r['error'])
        self.assertEqual(len(r['data']), 2)

    @patch('fleetops.tracksolid_import.TracksolidClient._call')
    def test_track_history(self, mock_call):
        mock_call.return_value = {
            'data': [
                {'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5', 'lng': '121.0',
                 'gpsSpeed': '0', 'ignition': 'ON'},
            ],
            'error': None,
        }
        r = self.client.track_history('869066063765607',
                                      '2025-07-25 00:00:00', '2025-07-25 23:59:59')
        self.assertIsNone(r['error'])
        self.assertEqual(len(r['data']), 1)


class ImportTracksolidDataTests(TestCase):
    def setUp(self):
        self.truck = Truck.objects.create(
            unit_number='TRK-001', plate_number='GNN403',
            make='Isuzu', model='NLR', year=2023, status='ACTIVE',
        )
        self.driver = Driver.objects.create(name='Test Driver', license_number='DL-001',
                                            license_expiry=timezone.now().date() + timezone.timedelta(days=60))
        DriverAssignment.objects.create(
            truck=self.truck, driver=self.driver,
            assigned_from=timezone.now().date() - timezone.timedelta(days=10),
        )

    @patch('fleetops.tracksolid_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.tracksolid_import.TracksolidClient')
    def test_import_empty_devices(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_devices.return_value = {'data': [], 'error': None}
        mock_client.app_key = 'KEY'
        mock_client.app_secret = 'SECRET'

        r = import_tracksolid_data(import_date=timezone.now().date())
        self.assertTrue(r['success'])
        self.assertEqual(r['processed'], 0)
        self.assertIn('No devices found', str(r['errors']))

    @patch('fleetops.tracksolid_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.tracksolid_import.TracksolidClient')
    def test_import_no_matching_plate(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_devices.return_value = {
            'data': [{'imei': '1111', 'vehicleNumber': 'UNKNOWN'}],
            'error': None,
        }
        mock_client.app_key = 'KEY'
        mock_client.app_secret = 'SECRET'

        r = import_tracksolid_data(import_date=timezone.now().date())
        self.assertTrue(r['success'])
        self.assertEqual(r['processed'], 0)

    @patch('fleetops.tracksolid_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.tracksolid_import.TracksolidClient')
    def test_import_creates_log(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_devices.return_value = {
            'data': [{'imei': '869066063765607', 'vehicleNumber': 'GNN403'}],
            'error': None,
        }
        mock_client.track_history.return_value = {
            'data': [
                {'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5995', 'lng': '120.9842',
                 'gpsSpeed': '40', 'ignition': 'ON'},
                {'gpsTime': '2025-07-25 08:30:00', 'lat': '14.5500', 'lng': '121.0000',
                 'gpsSpeed': '50', 'ignition': 'ON'},
            ],
            'error': None,
        }
        mock_client.device_detail.return_value = {
            'data': {'currentMileage': 50000},
            'error': None,
        }
        mock_client.app_key = 'KEY'
        mock_client.app_secret = 'SECRET'

        r = import_tracksolid_data(import_date=timezone.now().date())
        self.assertTrue(r['success'])
        self.assertEqual(r['processed'], 1)

        log = DailyLog.objects.get(truck=self.truck, date=timezone.now().date())
        self.assertEqual(log.driver, self.driver)
        self.assertGreater(log.distance_traveled_km, 0)
        self.assertEqual(log.max_speed_kmh, 50.0)
        self.assertIsNotNone(log.avg_speed_kmh)
        self.assertGreater(log.operating_hours, 0)

    @patch('fleetops.tracksolid_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.tracksolid_import.TracksolidClient')
    def test_import_dry_run(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_devices.return_value = {
            'data': [{'imei': '869066063765607', 'vehicleNumber': 'GNN403'}],
            'error': None,
        }
        mock_client.track_history.return_value = {
            'data': [{'gpsTime': '2025-07-25 08:00:00', 'lat': '14.5', 'lng': '121.0',
                      'gpsSpeed': '30', 'ignition': 'ON'}],
            'error': None,
        }
        mock_client.app_key = 'KEY'
        mock_client.app_secret = 'SECRET'

        r = import_tracksolid_data(import_date=timezone.now().date(), dry_run=True)
        self.assertTrue(r['success'])
        self.assertEqual(r['processed'], 1)
        self.assertTrue(r['dry_run'])
        self.assertEqual(DailyLog.objects.count(), 0)

    @patch('fleetops.tracksolid_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.tracksolid_import.TracksolidClient')
    def test_import_api_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.list_devices.side_effect = RuntimeError('Connection failed')
        mock_client.app_key = 'KEY'
        mock_client.app_secret = 'SECRET'

        r = import_tracksolid_data(import_date=timezone.now().date())
        self.assertFalse(r['success'])
        self.assertIn('Connection failed', r.get('error', ''))

    @patch('fleetops.tracksolid_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.tracksolid_import.TracksolidClient')
    def test_import_missing_credentials(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.app_key = ''
        mock_client.app_secret = ''

        r = import_tracksolid_data(import_date=timezone.now().date())
        self.assertFalse(r['success'])
