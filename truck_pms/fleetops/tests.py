from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from trucks.models import Truck
from .models import Driver, DriverAssignment, DailyLog


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
