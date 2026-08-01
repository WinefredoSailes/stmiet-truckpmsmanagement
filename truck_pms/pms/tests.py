from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from trucks.models import Truck
from pms.models import TaskCategory, TaskTemplate, PMSchedule
from service_log.models import ServiceLogEntry


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


def create_template(category=None, interval_type='MILEAGE', interval_value=5000, **kw):
    if category is None:
        category = create_category()
    defaults = dict(
        category=category, name='Change Oil',
        interval_type=interval_type, interval_value=interval_value,
        estimated_labor_hours=1.0,
    )
    defaults.update(kw)
    return TaskTemplate.objects.create(**defaults)


class CategoryModelTests(TestCase):
    def test_category_str(self):
        c = create_category()
        self.assertEqual(str(c), 'Engine')

    def test_template_str(self):
        c = create_category()
        t = create_template(c)
        self.assertIn('Engine', str(t))
        self.assertIn('Change Oil', str(t))


class PMScheduleModelTests(TestCase):
    def setUp(self):
        self.truck = create_truck()
        self.cat = create_category()
        self.tmpl = create_template(self.cat, 'MILEAGE', 5000)
        self.schedule = PMSchedule.objects.create(
            truck=self.truck, task_template=self.tmpl,
            last_mileage_km=5000, last_engine_hours=250,
            last_completed_at=timezone.now() - timedelta(days=30),
        )

    def test_status_mileage_ok(self):
        self.truck.current_mileage_km = 8000
        self.truck.save()
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status(), 'ok')

    def test_status_mileage_due(self):
        self.truck.current_mileage_km = 9900
        self.truck.save()
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status(), 'due')

    def test_status_mileage_overdue(self):
        self.truck.current_mileage_km = 11000
        self.truck.save()
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status(), 'overdue')

    def test_completed_on(self):
        self.schedule.last_completed_at = timezone.now()
        self.schedule.save()
        self.assertTrue(self.schedule.completed_on())
        self.assertTrue(self.schedule.completed_on(timezone.localdate()))
        self.assertFalse(self.schedule.completed_on(
            timezone.localdate() - timedelta(days=1)
        ))

    def test_completed_on_returns_false_when_never_completed(self):
        tmpl2 = create_template(self.cat, 'CALENDAR', 30)
        sched = PMSchedule.objects.create(
            truck=self.truck, task_template=tmpl2,
        )
        self.assertFalse(sched.completed_on())

    def test_status_calendar_overdue(self):
        tmpl = create_template(self.cat, 'CALENDAR', 30)
        sched = PMSchedule.objects.create(
            truck=self.truck, task_template=tmpl,
            last_completed_at=timezone.now() - timedelta(days=60),
        )
        self.assertEqual(sched.status(), 'overdue')

    def test_status_visual(self):
        tmpl = create_template(self.cat, 'VISUAL')
        sched = PMSchedule.objects.create(truck=self.truck, task_template=tmpl)
        self.assertEqual(sched.status(), 'visual')

    def test_status_inactive(self):
        self.schedule.is_active = False
        self.schedule.save()
        self.assertEqual(self.schedule.status(), 'inactive')

    def test_status_no_data(self):
        tmpl = create_template(self.cat, 'MILEAGE', 3000)
        sched = PMSchedule.objects.create(
            truck=self.truck, task_template=tmpl,
            last_mileage_km=None, last_completed_at=None,
        )
        self.assertEqual(sched.status(), 'no_data')

    def test_next_due_mileage(self):
        self.assertEqual(self.schedule.next_due_mileage(), 10000)

    def test_next_due_hours(self):
        tmpl = create_template(self.cat, 'HOURS', 5000)
        sched = PMSchedule.objects.create(
            truck=self.truck, task_template=tmpl,
            last_engine_hours=250,
        )
        self.assertEqual(sched.next_due_hours(), 5250)


class CategoryViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.cat = create_category()

    def test_category_list_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:category_list'))
        self.assertEqual(resp.status_code, 200)

    def test_category_list_staff_allowed(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:category_list'))
        self.assertEqual(resp.status_code, 200)

    def test_category_create_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:category_create'))
        self.assertEqual(resp.status_code, 200)

    def test_category_create_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('pms:category_create'), {
            'name': 'Brakes', 'description': 'Brake system tasks',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(TaskCategory.objects.filter(name='Brakes').exists())

    def test_category_update(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('pms:category_update', args=[self.cat.pk]),
            {'name': 'Updated Engine', 'description': 'Updated'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, 'Updated Engine')


class TemplateViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.cat = create_category()
        self.tmpl = create_template(self.cat)

    def test_template_list_loads(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:template_list'))
        self.assertEqual(resp.status_code, 200)

    def test_template_create_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:template_create'))
        self.assertEqual(resp.status_code, 200)

    def test_template_create_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('pms:template_create'), {
            'category': self.cat.pk,
            'name': 'Oil Change',
            'interval_type': 'MILEAGE',
            'interval_value': 5000,
            'estimated_labor_hours': 2.0,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(TaskTemplate.objects.filter(name='Oil Change').exists())

    def test_template_update(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('pms:template_update', args=[self.tmpl.pk]),
            {'category': self.cat.pk, 'name': 'Updated Template',
             'interval_type': 'HOURS', 'interval_value': 250,
             'estimated_labor_hours': 2.0},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.tmpl.refresh_from_db()
        self.assertEqual(self.tmpl.name, 'Updated Template')


class ScheduleViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.superuser = create_super()
        self.truck = create_truck()
        self.cat = create_category()
        self.tmpl = create_template(self.cat, 'MILEAGE', 5000)
        self.schedule = PMSchedule.objects.create(
            truck=self.truck, task_template=self.tmpl,
            last_mileage_km=5000, is_active=True,
        )

    def test_schedule_list_loads(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:schedule_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Change Oil')

    def test_schedule_list_with_filter(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:schedule_list'), {'status': 'no_data', 'search': 'Oil'})
        self.assertEqual(resp.status_code, 200)

    def test_schedule_list_unauthenticated(self):
        resp = self.client.get(reverse('pms:schedule_list'))
        self.assertEqual(resp.status_code, 302)

    def test_schedule_csv(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:schedule_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')

    def test_schedule_print(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:schedule_print'))
        self.assertEqual(resp.status_code, 200)

    def test_schedule_pdf(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:schedule_pdf'))
        self.assertIn(resp.status_code, (200, 302))

    def test_schedule_update_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:schedule_update', args=[self.schedule.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_complete_task_loads_for_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:complete_task', args=[self.schedule.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_complete_task_loads_for_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('pms:complete_task', args=[self.schedule.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_complete_task_denied_for_mechanic(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('pms:complete_task', args=[self.schedule.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_complete_task_updates_schedule(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('pms:complete_task', args=[self.schedule.pk]),
            {'actual_hours': 2.5, 'part_name_1': 'Oil Filter',
             'quantity_1': 1, 'unit_cost_1': 500},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.schedule.refresh_from_db()
        self.assertIsNotNone(self.schedule.last_completed_at)
        self.assertIsNotNone(self.schedule.last_mileage_km)
        self.assertTrue(ServiceLogEntry.objects.filter(
            truck=self.truck, action__icontains='Change Oil'
        ).exists())

    def test_complete_task_records_source_and_performer(self):
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('pms:complete_task', args=[self.schedule.pk]),
            {'actual_hours': 1.0},
            follow=True,
        )
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.last_completed_source, 'MANUAL')
        self.assertEqual(self.schedule.last_completed_by.username, 'admin')

    def test_complete_task_blocks_same_day_duplicate(self):
        self.client.login(username='admin', password='pass')
        url = reverse('pms:complete_task', args=[self.schedule.pk])
        local_now = timezone.localtime(timezone.now())
        data = {
            'completed_at': local_now.strftime('%Y-%m-%dT%H:%M'),
            'mileage_km': 10000, 'engine_hours': 500, 'labor_hours': 1.0,
        }
        self.client.post(url, data)
        self.schedule.refresh_from_db()
        first_completed = self.schedule.last_completed_at
        log_count = ServiceLogEntry.objects.filter(
            truck=self.truck, action__startswith='PM completed'
        ).count()
        self.assertEqual(log_count, 1)
        # Second person tries to complete the same PM on the same date
        resp = self.client.post(url, data)
        self.assertRedirects(resp, url)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.last_completed_at, first_completed)
        self.assertEqual(ServiceLogEntry.objects.filter(
            truck=self.truck, action__startswith='PM completed'
        ).count(), 1)

    def test_complete_task_allows_different_dates(self):
        self.client.login(username='admin', password='pass')
        url = reverse('pms:complete_task', args=[self.schedule.pk])
        past = timezone.localtime(timezone.now()) - timedelta(days=5)
        self.client.post(url, {
            'completed_at': past.strftime('%Y-%m-%dT%H:%M'),
            'mileage_km': 9000, 'engine_hours': 450,
        })
        self.schedule.refresh_from_db()
        self.assertEqual(
            timezone.localtime(self.schedule.last_completed_at).date(),
            past.date()
        )
        # Backdating to an EMPTY date is allowed (staff may log late)
        resp = self.client.post(url, {
            'completed_at': timezone.localtime(timezone.now()).strftime(
                '%Y-%m-%dT%H:%M'
            ),
            'mileage_km': 10000, 'engine_hours': 500,
        })
        self.assertRedirects(resp, reverse('pms:schedule_list'))
        self.schedule.refresh_from_db()
        self.assertTrue(self.schedule.completed_on())
        self.assertEqual(ServiceLogEntry.objects.filter(
            truck=self.truck, action__startswith='PM completed'
        ).count(), 2)

    def test_complete_task_creates_audit_entry(self):
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('pms:complete_task', args=[self.schedule.pk]),
            {'actual_hours': 1.0, 'notes': 'Routine PM'},
            follow=True,
        )
        entries = ServiceLogEntry.objects.filter(truck=self.truck)
        self.assertGreaterEqual(entries.count(), 1)

    def test_sync_truck(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:sync_truck', args=[self.truck.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_sync_all_trucks(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('pms:sync_all'))
        self.assertEqual(resp.status_code, 302)

    def test_unauthenticated_redirect(self):
        resp = self.client.get(reverse('pms:schedule_list'))
        self.assertEqual(resp.status_code, 302)
