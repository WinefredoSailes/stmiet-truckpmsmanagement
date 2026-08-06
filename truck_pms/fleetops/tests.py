import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from trucks.models import Truck
from .models import Driver, DriverAssignment, DailyLog
from .cartrack_import import import_cartrack_data


def create_admin():
    return User.objects.create_user(
        username='admin', password='pass', role=User.Role.ADMIN
    )


def create_staff():
    return User.objects.create_user(
        username='staff', password='pass', role=User.Role.STAFF
    )


def create_mechanic():
    return User.objects.create_user(
        username='mech', password='pass', role=User.Role.MECHANIC
    )


def create_contractor_user():
    return User.objects.create_user(
        username='conuser', password='pass', role=User.Role.CONTRACTOR
    )


def create_truck(**kw):
    defaults = dict(
        unit_number='T-001', plate_number='ABC-123',
        make='Isuzu', model='FVR', year=2020,
        current_mileage_km=10000, current_engine_hours=500,
        status='ACTIVE',
    )
    defaults.update(kw)
    return Truck.objects.create(**defaults)


def create_driver(**kw):
    defaults = dict(
        name='Test Driver',
        license_number='DL-001',
        license_expiry=timezone.now().date() + timedelta(days=60),
    )
    defaults.update(kw)
    return Driver.objects.create(**defaults)


class DriverModelTests(TestCase):
    def setUp(self):
        self.driver = create_driver()

    def test_driver_creation(self):
        self.assertEqual(str(self.driver), 'Test Driver (DL-001)')

    def test_license_status_ok(self):
        self.assertEqual(self.driver.license_status(), 'ok')

    def test_license_status_due_soon(self):
        self.driver.license_expiry = timezone.now().date() + timedelta(days=15)
        self.assertEqual(self.driver.license_status(), 'due_soon')

    def test_license_status_overdue(self):
        self.driver.license_expiry = timezone.now().date() - timedelta(days=1)
        self.assertEqual(self.driver.license_status(), 'overdue')

    def test_license_status_unknown(self):
        self.driver.license_expiry = None
        self.assertEqual(self.driver.license_status(), 'unknown')


class TruckComplianceTests(TestCase):
    def setUp(self):
        self.truck = Truck.objects.create(
            unit_number='TEST-001', plate_number='TEST001',
            make='Isuzu', model='Forward', year=2020,
            or_expiry=timezone.now().date() + timedelta(days=90),
            cr_expiry=timezone.now().date() + timedelta(days=45),
            fire_conveyance_expiry=timezone.now().date() + timedelta(days=10),
            dost_calibration_expiry=timezone.now().date() - timedelta(days=5),
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
        self.truck = create_truck()
        self.log = DailyLog.objects.create(
            truck=self.truck,
            date=timezone.now().date(),
            mileage_km=5000, engine_hours=100,
            fuel_liters=50, distance_traveled_km=400,
            idle_hours=2, operating_hours=8,
            harsh_braking_count=3, harsh_acceleration_count=1,
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

    def test_data_source_default(self):
        self.assertEqual(self.log.data_source, DailyLog.DataSource.MANUAL)

    def test_data_source_choices(self):
        for choice in [DailyLog.DataSource.MANUAL, DailyLog.DataSource.CARTRACK, DailyLog.DataSource.BOTH]:
            self.log.data_source = choice
            self.log.save()
            self.log.refresh_from_db()
            self.assertEqual(self.log.data_source, choice)


class DailyLogViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.truck = create_truck()
        self.today = timezone.now().date()
        DailyLog.objects.create(
            truck=self.truck, date=self.today,
            mileage_km=5000, engine_hours=100,
            fuel_liters=50, distance_traveled_km=400,
            idle_hours=2, operating_hours=8,
        )

    def test_daily_log_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 302)

    def test_daily_log_specific_date(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:daily_log'), {'date': self.today.isoformat()})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ABC-123')

    def test_daily_log_range_mode(self):
        self.client.login(username='staff', password='pass')
        start = (self.today - timedelta(days=2)).isoformat()
        end = self.today.isoformat()
        resp = self.client.get(reverse('fleetops:daily_log'), {'start': start, 'end': end})
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_range_empty(self):
        self.client.login(username='staff', password='pass')
        far_past = (self.today - timedelta(days=365)).isoformat()
        resp = self.client.get(reverse('fleetops:daily_log'),
                                {'start': far_past, 'end': far_past})
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_invalid_date_falls_back(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:daily_log'), {'date': 'not-a-date'})
        self.assertEqual(resp.status_code, 200)

    def test_daily_log_unauthenticated_redirect(self):
        resp = self.client.get(reverse('fleetops:daily_log'))
        self.assertEqual(resp.status_code, 302)


class DailyLogLoadTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.truck = create_truck()
        self.driver = create_driver()
        self.today = timezone.now().date()

    def test_load_post_creates_log(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:daily_log_load'), {
            'date': self.today.isoformat(),
            f'mileage_{self.truck.pk}': '5000',
            f'hours_{self.truck.pk}': '100',
            f'driver_{self.truck.pk}': str(self.driver.pk),
            f'fuel_{self.truck.pk}': '50.0',
            f'idle_hrs_{self.truck.pk}': '2.0',
            f'op_hrs_{self.truck.pk}': '8.0',
            f'dist_{self.truck.pk}': '400.0',
            f'brake_{self.truck.pk}': '3',
            f'accel_{self.truck.pk}': '1',
            f'turn_{self.truck.pk}': '2',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(DailyLog.objects.filter(
            truck=self.truck, date=self.today
        ).exists())

    def test_load_post_updates_existing(self):
        DailyLog.objects.create(
            truck=self.truck, date=self.today,
            mileage_km=5000, engine_hours=100,
        )
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:daily_log_load'), {
            'date': self.today.isoformat(),
            f'mileage_{self.truck.pk}': '6000',
            f'hours_{self.truck.pk}': '150',
        })
        self.assertEqual(resp.status_code, 302)
        log = DailyLog.objects.get(truck=self.truck, date=self.today)
        self.assertEqual(log.mileage_km, 6000)
        self.assertEqual(float(log.engine_hours), 150)

    def test_load_get_redirects(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:daily_log_load'))
        self.assertEqual(resp.status_code, 302)

    def test_load_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.post(reverse('fleetops:daily_log_load'), {
            'date': self.today.isoformat(),
        })
        self.assertEqual(resp.status_code, 302)

    def test_load_sets_driver_from_assignment(self):
        DriverAssignment.objects.create(
            driver=self.driver, truck=self.truck,
            assigned_from=self.today - timedelta(days=10),
        )
        self.client.login(username='admin', password='pass')
        self.client.post(reverse('fleetops:daily_log_load'), {
            'date': self.today.isoformat(),
            f'mileage_{self.truck.pk}': '5000',
            f'hours_{self.truck.pk}': '100',
        })
        log = DailyLog.objects.get(truck=self.truck, date=self.today)
        self.assertEqual(log.driver, self.driver)


class DriverViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.driver = create_driver()

    def test_drivers_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:driver_list'))
        self.assertEqual(resp.status_code, 200)

    def test_drivers_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:driver_list'))
        self.assertEqual(resp.status_code, 302)

    def test_drivers_unauthenticated_redirect(self):
        resp = self.client.get(reverse('fleetops:driver_list'))
        self.assertEqual(resp.status_code, 302)

    def test_driver_create_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:driver_create'))
        self.assertEqual(resp.status_code, 200)

    def test_driver_create_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:driver_create'), {
            'name': 'New Driver',
            'license_number': 'DL-NEW',
            'license_expiry': (timezone.now().date() + timedelta(days=365)).isoformat(),
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Driver.objects.filter(name='New Driver').exists())

    def test_driver_edit_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:driver_edit', args=[self.driver.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_driver_edit_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('fleetops:driver_edit', args=[self.driver.pk]),
            {'name': 'Updated Driver', 'license_number': 'DL-001',
             'license_expiry': (timezone.now().date() + timedelta(days=90)).isoformat()},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.name, 'Updated Driver')

    def test_driver_scorecard_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:driver_scorecard', args=[self.driver.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_driver_scorecard_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:driver_scorecard', args=[self.driver.pk]))
        self.assertEqual(resp.status_code, 200)


class AssignmentViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.truck = create_truck()
        self.driver = create_driver()

    def test_assignment_list_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:assignment_list'))
        self.assertEqual(resp.status_code, 200)

    def test_assignment_list_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:assignment_list'))
        self.assertEqual(resp.status_code, 200)

    def test_assignment_create_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:assignment_create'), {
            'driver': self.driver.pk,
            'truck': self.truck.pk,
            'assigned_from': timezone.now().date().isoformat(),
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(DriverAssignment.objects.filter(
            driver=self.driver, truck=self.truck
        ).exists())

    def test_assignment_create_does_not_end_previous(self):
        self.client.login(username='admin', password='pass')
        drv2 = create_driver(name='Driver 2', license_number='DL-002')
        self.client.post(reverse('fleetops:assignment_create'), {
            'driver': self.driver.pk, 'truck': self.truck.pk,
            'assigned_from': (timezone.now().date() - timedelta(days=10)).isoformat(),
        })
        self.client.post(reverse('fleetops:assignment_create'), {
            'driver': drv2.pk, 'truck': self.truck.pk,
            'assigned_from': timezone.now().date().isoformat(),
        })
        self.assertEqual(DriverAssignment.objects.filter(truck=self.truck).count(), 2)


class FleetPerformanceTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.truck = create_truck()
        self.today = timezone.now().date()
        DailyLog.objects.create(
            truck=self.truck, date=self.today,
            mileage_km=5000, engine_hours=100,
            fuel_liters=50, distance_traveled_km=400,
            idle_hours=2, operating_hours=8,
            harsh_braking_count=3,
        )

    def test_fleet_performance_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:fleet_performance'))
        self.assertEqual(resp.status_code, 200)

    def test_fleet_performance_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:fleet_performance'))
        self.assertEqual(resp.status_code, 200)

    def test_fleet_performance_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('fleetops:fleet_performance'))
        self.assertEqual(resp.status_code, 302)

    def test_fleet_performance_with_dates(self):
        self.client.login(username='admin', password='pass')
        start = (self.today - timedelta(days=7)).isoformat()
        end = self.today.isoformat()
        resp = self.client.get(reverse('fleetops:fleet_performance'),
                                {'start': start, 'end': end})
        self.assertEqual(resp.status_code, 200)

    def test_fleet_performance_with_week(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:fleet_performance'),
                                {'week': self.today.isoformat()})
        self.assertEqual(resp.status_code, 200)

    def test_fleet_performance_no_data(self):
        self.client.login(username='admin', password='pass')
        far_past = (self.today - timedelta(days=365)).isoformat()
        resp = self.client.get(reverse('fleetops:fleet_performance'),
                                {'start': far_past, 'end': far_past})
        self.assertEqual(resp.status_code, 200)


class WeeklyReportTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.truck = create_truck()
        self.today = timezone.now().date()
        DailyLog.objects.create(
            truck=self.truck, date=self.today,
            mileage_km=5000, engine_hours=100,
            fuel_liters=50, distance_traveled_km=400,
            idle_hours=2, operating_hours=8,
        )

    def test_weekly_report_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:weekly_report'))
        self.assertEqual(resp.status_code, 200)

    def test_weekly_report_with_dates(self):
        self.client.login(username='staff', password='pass')
        start = (self.today - timedelta(days=7)).isoformat()
        end = self.today.isoformat()
        resp = self.client.get(reverse('fleetops:weekly_report'),
                                {'start': start, 'end': end})
        self.assertEqual(resp.status_code, 200)


class ComplianceDashboardTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.truck = create_truck(
            or_expiry=timezone.now().date() + timedelta(days=90),
            cr_expiry=timezone.now().date() + timedelta(days=45),
        )
        create_driver()

    def test_compliance_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('fleetops:compliance_dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_compliance_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('fleetops:compliance_dashboard'))
        self.assertEqual(resp.status_code, 302)


class PullCartrackViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.truck = create_truck()
        self.today = timezone.now().date()

    @patch('fleetops.views.import_cartrack_data')
    def test_pull_cartrack_post(self, mock_import):
        mock_import.return_value = {
            'success': True, 'processed': 2, 'trucks_found': 1,
            'import_date': self.today, 'import_date_end': self.today,
            'errors': [],
        }
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:pull_cartrack'), {
            'date': self.today.isoformat(),
            'data_types': ['trips', 'events', 'fuel'],
        })
        self.assertEqual(resp.status_code, 302)
        mock_import.assert_called_once()

    @patch('fleetops.views.import_cartrack_data')
    def test_pull_cartrack_redirects_to_date(self, mock_import):
        mock_import.return_value = {
            'success': True, 'processed': 2, 'trucks_found': 1,
            'import_date': self.today, 'import_date_end': self.today,
            'errors': [],
        }
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:pull_cartrack'), {
            'date': self.today.isoformat(),
        })
        self.assertIn(f'date={self.today.isoformat()}', resp.url)

    @patch('fleetops.views.import_cartrack_data')
    def test_pull_cartrack_range(self, mock_import):
        mock_import.return_value = {
            'success': True, 'processed': 4, 'trucks_found': 1,
            'import_date': self.today - timedelta(days=2),
            'import_date_end': self.today,
            'errors': [],
        }
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:pull_cartrack'), {
            'date': (self.today - timedelta(days=2)).isoformat(),
            'date_end': self.today.isoformat(),
            'data_types': ['trips'],
        })
        self.assertEqual(resp.status_code, 302)

    @patch('fleetops.views.import_cartrack_data')
    def test_pull_cartrack_errors_shown(self, mock_import):
        mock_import.return_value = {
            'success': True, 'processed': 0, 'trucks_found': 1,
            'import_date': self.today, 'import_date_end': self.today,
            'errors': ['Fuel API: 403 Forbidden'],
        }
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:pull_cartrack'), {
            'date': self.today.isoformat(),
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

    @patch('fleetops.views.import_cartrack_data')
    def test_pull_cartrack_failure(self, mock_import):
        mock_import.return_value = {
            'success': False, 'import_date': self.today,
            'error': 'Import failed', 'errors': ['API Error'],
        }
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('fleetops:pull_cartrack'), {
            'date': self.today.isoformat(),
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_pull_cartrack_get_redirects(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('fleetops:pull_cartrack'))
        self.assertEqual(resp.status_code, 302)

    def test_pull_cartrack_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.post(reverse('fleetops:pull_cartrack'), {
            'date': self.today.isoformat(),
        })
        self.assertEqual(resp.status_code, 302)


class SyncCartrackViewTests(TestCase):
    def setUp(self):
        self.today = timezone.now().date()

    def _post(self, body=None, token='secret-token', **headers):
        hdrs = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        hdrs.update(headers)
        payload = json.dumps(body) if body is not None else ''
        return self.client.post(
            reverse('fleetops:sync_cartrack'),
            data=payload,
            content_type='application/json',
            **hdrs,
        )

    @patch('fleetops.views.import_cartrack_data')
    def test_sync_requires_token(self, mock_import):
        resp = self.client.post(reverse('fleetops:sync_cartrack'))
        self.assertEqual(resp.status_code, 401)
        mock_import.assert_not_called()

    @patch('fleetops.views.import_cartrack_data')
    def test_sync_wrong_token_rejected(self, mock_import):
        resp = self._post(token='wrong-token')
        self.assertEqual(resp.status_code, 401)
        mock_import.assert_not_called()

    @patch('fleetops.views.import_cartrack_data')
    def test_sync_no_token_configured_rejected(self, mock_import):
        with patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('SYNC_TOKEN', None)
            resp = self._post(token='secret-token')
        self.assertEqual(resp.status_code, 401)
        mock_import.assert_not_called()

    @patch('fleetops.views.import_cartrack_data')
    def test_sync_ok(self, mock_import):
        mock_import.return_value = {
            'success': True, 'processed': 6, 'trucks_found': 1,
            'import_date': self.today - timedelta(days=6),
            'import_date_end': self.today,
            'errors': [], 'fuel_warnings': ['Truck X: no sensor'],
        }
        with patch.dict('os.environ', {'SYNC_TOKEN': 'secret-token'}):
            resp = self._post({'days_back': 7})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['processed'], 6)
        self.assertEqual(data['date_start'], (self.today - timedelta(days=6)).isoformat())
        mock_import.assert_called_once()
        kwargs = mock_import.call_args.kwargs
        self.assertEqual(kwargs['days_back'], 7)

    @patch('fleetops.views.import_cartrack_data')
    def test_sync_failure_status(self, mock_import):
        mock_import.return_value = {
            'success': False, 'processed': 0, 'trucks_found': 0,
            'import_date': self.today, 'import_date_end': self.today,
            'errors': [], 'error': 'Boom',
        }
        with patch.dict('os.environ', {'SYNC_TOKEN': 'secret-token'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()['error'], 'Boom')

    @patch('fleetops.views.import_cartrack_data')
    def test_sync_get_method_not_allowed(self, mock_import):
        with patch.dict('os.environ', {'SYNC_TOKEN': 'secret-token'}):
            resp = self.client.get(reverse('fleetops:sync_cartrack'))
        self.assertEqual(resp.status_code, 405)
        mock_import.assert_not_called()


class CartrackImportIntegrationTests(TestCase):
    def setUp(self):
        self.truck = create_truck(
            unit_number='T-INT', plate_number='INT-001',
        )
        self.today = timezone.now().date()

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_cartrack_creates_dailylog(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = 'test_token'
        mock_client.fetch_trips.return_value = {
            'data': [{
                'registration': 'INT-001',
                'trip_distance': 123456.0,
                'trip_duration_seconds': 28800.0,
                'idle_time_seconds': 3600.0,
                'end_odometer': 5000000.0,
                'clock_end': 360000.0,
                'max_speed': 80.0,
                'harsh_braking_events': 2,
                'harsh_acceleration_events': 1,
                'harsh_cornering_events': 0,
                'end_timestamp': f'{self.today.isoformat()} 12:00:00',
            }],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_consumed.return_value = {
            'data': [{'registration': 'INT-001', 'fuel_consumed': 100.0}],
            'error': None,
        }

        result = import_cartrack_data(
            import_date=self.today,
            api_token='test_token',
            api_username='SEVE00001',
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['processed'], 1)
        self.assertTrue(DailyLog.objects.filter(
            truck=self.truck, date=self.today
        ).exists())
        log = DailyLog.objects.get(truck=self.truck, date=self.today)
        self.assertAlmostEqual(float(log.distance_traveled_km), 123.46, places=1)
        self.assertAlmostEqual(float(log.operating_hours), 7.0, places=1)
        self.assertAlmostEqual(float(log.idle_hours), 1.0, places=1)
        self.assertEqual(log.max_speed_kmh, 80.0)
        self.assertEqual(log.data_source, DailyLog.DataSource.CARTRACK)

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_cartrack_dry_run(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = 'test_token'
        mock_client.fetch_trips.return_value = {
            'data': [{
                'registration': 'INT-001',
                'trip_distance': 50000.0,
                'trip_duration_seconds': 14400.0,
                'idle_time_seconds': 600.0,
                'end_odometer': 2000000.0,
                'clock_end': 180000.0,
                'end_timestamp': f'{self.today.isoformat()} 12:00:00',
            }],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_consumed.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_level.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_fills_all.return_value = {'data': [], 'error': None}

        result = import_cartrack_data(
            import_date=self.today, dry_run=True,
            api_token='test_token',
            api_username='SEVE00001',
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['processed'], 1)
        self.assertTrue(result['dry_run'])
        self.assertEqual(DailyLog.objects.count(), 0)

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_cartrack_no_token(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = ''
        result = import_cartrack_data(
            import_date=self.today,
            api_token='', api_username='SEVE00001',
        )
        self.assertFalse(result['success'])
        self.assertIn('No CARTRACK_API_TOKEN', result['error'])

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_cartrack_request_not_available(self, mock_client_cls):
        with patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', False):
            result = import_cartrack_data(
                import_date=self.today,
                api_token='test', api_username='test',
            )
            self.assertFalse(result['success'])

    @patch('fleetops.cartrack_import.REQUESTS_AVAILABLE', True)
    @patch('fleetops.cartrack_import.CartrackAPIClient')
    def test_import_cartrack_fuel_fallback_logged(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.token = 'test_token'
        mock_client.fetch_trips.return_value = {
            'data': [{
                'registration': 'INT-001',
                'trip_distance': 50000.0,
                'trip_duration_seconds': 14400.0,
                'idle_time_seconds': 600.0,
                'end_odometer': 2000000.0,
                'clock_end': 180000.0,
                'end_timestamp': f'{self.today.isoformat()} 12:00:00',
            }],
            'error': None,
        }
        mock_client.fetch_events.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_consumed.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_level.return_value = {'data': [], 'error': None}
        mock_client.fetch_fuel_fills_all.return_value = {
            'data': [{'registration': 'INT-001', 'fill_amount_litres': 50.0}],
            'error': None,
        }
        result = import_cartrack_data(
            import_date=self.today, data_types=['trips', 'fuel'],
            api_token='test_token', api_username='SEVE00001',
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['fuel_endpoint'], 'fuel/fills')
