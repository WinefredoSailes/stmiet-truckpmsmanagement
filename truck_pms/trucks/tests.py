import io
import csv
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User
from trucks.models import Truck
from pms.models import TaskCategory, TaskTemplate, PMSchedule


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


def create_super():
    return User.objects.create_superuser(
        username='super', password='pass', role=User.Role.SUPER_ADMIN
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


def create_category():
    return TaskCategory.objects.create(name='Engine', description='Engine tasks')


def create_template(category, interval_type='MILEAGE', interval_value=5000):
    return TaskTemplate.objects.create(
        category=category, name='Change Oil',
        interval_type=interval_type, interval_value=interval_value,
    )


class TruckModelTests(TestCase):
    def test_truck_creation(self):
        t = create_truck()
        self.assertEqual(str(t), 'T-001 - ABC-123')
        self.assertEqual(t.status, 'ACTIVE')

    def test_compliance_items_count(self):
        t = create_truck(
            or_expiry=date.today() + timedelta(days=90),
            cr_expiry=date.today() + timedelta(days=45),
            fire_conveyance_expiry=date.today() + timedelta(days=10),
            dost_calibration_expiry=date.today() - timedelta(days=5),
        )
        items = t.compliance_items()
        self.assertEqual(len(items), 4)

    def test_compliance_status_variants(self):
        t = create_truck(
            or_expiry=date.today() + timedelta(days=90),
            cr_expiry=date.today() + timedelta(days=45),
            fire_conveyance_expiry=date.today() + timedelta(days=10),
            dost_calibration_expiry=date.today() - timedelta(days=5),
        )
        items = t.compliance_items()
        self.assertEqual(items[0]['status'], 'ok')
        self.assertEqual(items[2]['status'], 'due_soon')
        self.assertEqual(items[3]['status'], 'overdue')

    def test_compliance_unknown(self):
        t = create_truck()
        items = t.compliance_items()
        self.assertEqual(items[1]['status'], 'unknown')


class TruckViewAccessTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.truck = create_truck()
        self.cat = create_category()
        self.tmpl = create_template(self.cat)

    def test_truck_list_loads(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'T-001')

    def test_truck_list_pagination(self):
        self.truck.delete()
        for i in range(55):
            create_truck(unit_number=f'T-{i:03d}', plate_number=f'PLT-{i:03d}')
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:list'))
        self.assertEqual(resp.status_code, 200)

    def test_truck_detail_loads(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:detail', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'T-001')

    def test_truck_create_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('trucks:create'))
        self.assertEqual(resp.status_code, 200)

    def test_truck_create_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:create'))
        self.assertEqual(resp.status_code, 403)

    def test_truck_create_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('trucks:create'))
        self.assertEqual(resp.status_code, 403)

    def test_truck_create_post_creates_pm_schedules(self):
        self.client.login(username='admin', password='pass')
        data = {
            'unit_number': 'T-NEW', 'plate_number': 'NEW-001',
            'make': 'Hino', 'model': 'GH', 'year': 2023,
            'status': 'ACTIVE', 'current_mileage_km': 0,
            'current_engine_hours': 0,
        }
        resp = self.client.post(reverse('trucks:create'), data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Truck.objects.filter(unit_number='T-NEW').exists())
        new_truck = Truck.objects.get(unit_number='T-NEW')
        self.assertEqual(PMSchedule.objects.filter(truck=new_truck).count(),
                         TaskTemplate.objects.count())

    def test_truck_update_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('trucks:update', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_truck_update_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:update', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_truck_update_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('trucks:update', args=[self.truck.pk]),
            {'unit_number': 'T-001', 'plate_number': 'ABC-123',
             'make': 'Isuzu', 'model': 'FVR', 'year': 2021,
             'status': 'ACTIVE',
             'current_mileage_km': self.truck.current_mileage_km,
             'current_engine_hours': self.truck.current_engine_hours,
             },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.truck.refresh_from_db()
        self.assertEqual(self.truck.year, 2021)

    def test_export_csv(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:export_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')

    def test_export_csv_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('trucks:export_csv'))
        self.assertEqual(resp.status_code, 403)

    def test_import_csv_creates_new(self):
        self.client.login(username='admin', password='pass')
        csv_content = (
            'unit_number,plate_number,make,model,year,status\n'
            'T-IMP,IMP-001,Hino,GH,2023,ACTIVE\n'
        )
        resp = self.client.post(
            reverse('trucks:import_csv'),
            {'csv_file': SimpleUploadedFile('trucks.csv', csv_content.encode(), content_type='text/csv')},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Truck.objects.filter(unit_number='T-IMP').exists())

    def test_import_csv_updates_existing(self):
        create_truck(unit_number='T-IMP', plate_number='IMP-001')
        self.client.login(username='admin', password='pass')
        csv_content = (
            'unit_number,plate_number,make,model,year,status\n'
            'T-IMP,IMP-001,Toyota,GH,2023,ACTIVE\n'
        )
        resp = self.client.post(
            reverse('trucks:import_csv'),
            {'csv_file': SimpleUploadedFile('trucks.csv', csv_content.encode(), content_type='text/csv')},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        t = Truck.objects.get(unit_number='T-IMP')
        self.assertEqual(t.make, 'Toyota')

    def test_import_csv_requires_csv_extension(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('trucks:import_csv'),
            {'csv_file': SimpleUploadedFile('data.txt', b'data', content_type='text/plain')},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Only CSV')

    def test_import_csv_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('trucks:import_csv'))
        self.assertEqual(resp.status_code, 403)

    def test_batch_mileage_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('trucks:batch_mileage'))
        self.assertEqual(resp.status_code, 200)

    def test_batch_mileage_staff_allowed(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('trucks:batch_mileage'))
        self.assertEqual(resp.status_code, 200)

    def test_batch_mileage_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('trucks:batch_mileage'),
            {f'mileage_{self.truck.pk}': 15000, f'hours_{self.truck.pk}': 750},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.truck.refresh_from_db()
        self.assertEqual(self.truck.current_mileage_km, 15000)
        self.assertEqual(float(self.truck.current_engine_hours), 750)

    def test_truck_unauthenticated_redirect(self):
        resp = self.client.get(reverse('trucks:list'))
        self.assertEqual(resp.status_code, 302)

    def test_truck_detail_contains_compliance(self):
        self.client.login(username='staff', password='pass')
        t = create_truck(
            unit_number='T-COMP', plate_number='COMP-001',
            or_expiry=date.today() + timedelta(days=90),
        )
        resp = self.client.get(reverse('trucks:detail', args=[t.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Compliance')
