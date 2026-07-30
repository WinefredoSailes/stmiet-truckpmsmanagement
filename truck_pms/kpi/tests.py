from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from trucks.models import Truck
from joborders.models import JobOrder, JobOrderLineItem
from contractors.models import Contractor


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


class KpiViewAccessTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()

    def test_mechanic_kpi_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:mechanic'))
        self.assertEqual(resp.status_code, 200)

    def test_mechanic_kpi_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('kpi:mechanic'))
        self.assertEqual(resp.status_code, 403)

    def test_mechanic_kpi_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('kpi:mechanic'))
        self.assertEqual(resp.status_code, 403)

    def test_contractor_kpi_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:contractor'))
        self.assertEqual(resp.status_code, 200)

    def test_truck_frequency_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:truck_frequency'))
        self.assertEqual(resp.status_code, 200)

    def test_truck_frequency_loads(self):
        self.client.login(username='admin', password='pass')
        t = create_truck()
        resp = self.client.get(reverse('kpi:truck_frequency'), {'truck': t.pk})
        self.assertEqual(resp.status_code, 200)

    def test_predictive_analytics_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:predictive'))
        self.assertEqual(resp.status_code, 200)

    def test_trainee_kpi_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:trainee'))
        self.assertEqual(resp.status_code, 200)

    def test_trainee_kpi_trainee_allowed(self):
        trainee = User.objects.create_user(
            username='trainee', password='pass', role=User.Role.TRAINEE
        )
        self.client.login(username='trainee', password='pass')
        resp = self.client.get(reverse('kpi:trainee'))
        self.assertEqual(resp.status_code, 200)

    def test_mechanic_kpi_no_data(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:mechanic'))
        self.assertEqual(resp.status_code, 200)

    def test_contractor_kpi_no_data(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('kpi:contractor'))
        self.assertEqual(resp.status_code, 200)
