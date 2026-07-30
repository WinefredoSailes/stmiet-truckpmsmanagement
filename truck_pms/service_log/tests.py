from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from trucks.models import Truck
from service_log.models import ServiceLogEntry, ServiceLogPart


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


def create_truck(**kw):
    defaults = dict(
        unit_number='T-001', plate_number='ABC-123',
        make='Isuzu', model='FVR', year=2020,
        status='ACTIVE',
    )
    defaults.update(kw)
    return Truck.objects.create(**defaults)


class ServiceLogModelTests(TestCase):
    def setUp(self):
        self.truck = create_truck()
        self.admin = create_admin()
        self.entry = ServiceLogEntry.objects.create(
            truck=self.truck,
            action='Oil Change',
            description='Changed engine oil and filter',
            performed_by=self.admin,
            performed_at=timezone.now(),
            mileage_at=10000,
            engine_hours_at=500,
            labor_hours=2.0,
            parts_cost=1500.00,
        )

    def test_entry_creation(self):
        self.assertEqual(str(self.entry.action), 'Oil Change')
        self.assertEqual(self.entry.mileage_at, 10000)

    def test_entry_str(self):
        self.assertIn(self.truck.unit_number, str(self.entry))
        self.assertIn('Oil Change', str(self.entry))

    def test_parts_relation(self):
        part = ServiceLogPart.objects.create(
            service_log=self.entry,
            part_name='Oil Filter',
            quantity=1,
            unit_cost=500.00,
        )
        self.assertEqual(part.total_cost(), 500.00)
        self.assertEqual(self.entry.parts.count(), 1)

    def test_multiple_parts(self):
        ServiceLogPart.objects.create(service_log=self.entry, part_name='Oil', quantity=2, unit_cost=300)
        ServiceLogPart.objects.create(service_log=self.entry, part_name='Filter', quantity=1, unit_cost=500)
        self.assertEqual(self.entry.parts.count(), 2)
        total = sum(p.total_cost() for p in self.entry.parts.all())
        self.assertEqual(total, 1100.00)


class ServiceLogViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.truck = create_truck()
        ServiceLogEntry.objects.create(
            truck=self.truck, action='Oil Change',
            description='Routine PM', performed_at=timezone.now(),
            performed_by=self.admin,
        )

    def test_truck_ledger_loads(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('service_log:truck_ledger', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Oil Change')

    def test_truck_ledger_unauthenticated_redirect(self):
        resp = self.client.get(reverse('service_log:truck_ledger', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_full_ledger_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('service_log:full_ledger'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Oil Change')

    def test_full_ledger_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('service_log:full_ledger'))
        self.assertEqual(resp.status_code, 403)

    def test_full_ledger_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('service_log:full_ledger'))
        self.assertEqual(resp.status_code, 403)

    def test_full_ledger_with_truck_filter(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('service_log:full_ledger'), {'truck': self.truck.pk})
        self.assertEqual(resp.status_code, 200)

    def test_full_ledger_with_action_filter(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('service_log:full_ledger'), {'action': 'Oil'})
        self.assertEqual(resp.status_code, 200)

    def test_full_ledger_pagination(self):
        for i in range(55):
            ServiceLogEntry.objects.create(
                truck=self.truck, action=f'Service {i}',
                description=f'Entry {i}', performed_at=timezone.now(),
                performed_by=self.admin,
            )
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('service_log:full_ledger'))
        self.assertEqual(resp.status_code, 200)

    def test_truck_ledger_displays_parts(self):
        self.client.login(username='staff', password='pass')
        entry = ServiceLogEntry.objects.create(
            truck=self.truck, action='Brake Repair',
            description='Fixed brakes', performed_at=timezone.now(),
            performed_by=self.admin,
        )
        ServiceLogPart.objects.create(
            service_log=entry, part_name='Brake Pad',
            quantity=2, unit_cost=1500,
        )
        resp = self.client.get(reverse('service_log:truck_ledger', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 200)


class ServiceLogEdgeCaseTests(TestCase):
    def test_entry_with_null_job_order(self):
        truck = create_truck()
        entry = ServiceLogEntry.objects.create(
            truck=truck, action='Inspection',
            description='Null JO test', performed_at=timezone.now(),
            job_order=None, line_item=None,
        )
        self.assertIsNone(entry.job_order)
        self.assertIsNone(entry.line_item)

    def test_entry_with_null_performed_by(self):
        truck = create_truck()
        entry = ServiceLogEntry.objects.create(
            truck=truck, action='Walkthrough',
            description='No performer', performed_at=timezone.now(),
            performed_by=None,
        )
        self.assertIsNone(entry.performed_by)
