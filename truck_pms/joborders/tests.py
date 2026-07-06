from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from trucks.models import Truck
from pms.models import TaskCategory, TaskTemplate, PMSchedule
from joborders.models import JobOrder, JobOrderLineItem, LineItemPart
from service_log.models import ServiceLogEntry
from contractors.models import Contractor

User = get_user_model()


# ─── Fixture helpers ───────────────────────────────────────────────

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

def create_super():
    return User.objects.create_superuser(
        username='super', password='pass', role=User.Role.SUPER_ADMIN
    )

def create_truck():
    return Truck.objects.create(
        unit_number='T-001', plate_number='ABC-123',
        make='Isuzu', model='FVR', year=2020,
        current_mileage_km=10000
    )

def create_category():
    return TaskCategory.objects.create(name='Test Engine', description='Engine tasks')

def create_template(category, interval_type='MILEAGE', interval_value=5000):
    return TaskTemplate.objects.create(
        category=category,
        name='Change Oil',
        interval_type=interval_type,
        interval_value=interval_value,
        estimated_labor_hours=1.0
    )

def create_contractor():
    return Contractor.objects.create(
        company_name='Test Welding',
        contact_person='Juan',
        mobile='09170000000',
        skills='Welding, Fabrication'
    )


# ─── 1. MODEL TESTS ─────────────────────────────────────────────

class ModelTests(TestCase):

    def test_user_creation_with_roles(self):
        for role, label in User.Role.choices:
            u = User.objects.create_user(
                username=role.lower(), password='pass', role=role
            )
            self.assertEqual(u.role, role)
            self.assertEqual(u.get_role_display(), label)

    def test_truck_creation(self):
        t = create_truck()
        self.assertEqual(str(t), 'T-001 - ABC-123')
        self.assertEqual(t.status, 'ACTIVE')

    def test_task_category_str(self):
        c = create_category()
        self.assertEqual(str(c), 'Test Engine')

    def test_task_template_str(self):
        c = create_category()
        t = create_template(c)
        self.assertIn('Test Engine', str(t))
        self.assertIn('Change Oil', str(t))

    def test_pm_schedule_status_mileage_ok(self):
        truck = create_truck()  # mileage = 10000
        cat = create_category()
        tmpl = create_template(cat, 'MILEAGE', 5000)
        pm = PMSchedule.objects.create(
            truck=truck, task_template=tmpl,
            last_mileage_km=3000
        )
        # Next due at 8000 (3000 + 5000), current is 10000
        self.assertEqual(pm.status(), 'overdue')

    def test_pm_schedule_status_mileage_ok(self):
        truck = create_truck()
        truck.current_mileage_km = 7500
        truck.save()
        cat = create_category()
        tmpl = create_template(cat, 'MILEAGE', 5000)
        pm = PMSchedule.objects.create(
            truck=truck, task_template=tmpl,
            last_mileage_km=3000
        )
        # Next due at 8000, current 7500, 10% of 5000 = 500
        # 8000 - 7500 = 500 → within 10% → 'due'
        self.assertEqual(pm.status(), 'due')

    def test_pm_schedule_status_mileage_ok_ok(self):
        truck = create_truck()
        truck.current_mileage_km = 7000
        truck.save()
        cat = create_category()
        tmpl = create_template(cat, 'MILEAGE', 5000)
        pm = PMSchedule.objects.create(
            truck=truck, task_template=tmpl,
            last_mileage_km=3000
        )
        self.assertEqual(pm.status(), 'ok')

    def test_pm_schedule_status_calendar(self):
        truck = create_truck()
        cat = create_category()
        tmpl = create_template(cat, 'CALENDAR', 30)
        pm = PMSchedule.objects.create(
            truck=truck, task_template=tmpl,
            last_completed_at=timezone.now() - timedelta(days=40)
        )
        self.assertEqual(pm.status(), 'overdue')

    def test_pm_schedule_status_visual(self):
        truck = create_truck()
        cat = create_category()
        tmpl = create_template(cat, 'VISUAL', None)
        pm = PMSchedule.objects.create(truck=truck, task_template=tmpl)
        self.assertEqual(pm.status(), 'visual')

    def test_pm_schedule_inactive(self):
        truck = create_truck()
        cat = create_category()
        tmpl = create_template(cat, 'MILEAGE', 5000)
        pm = PMSchedule.objects.create(
            truck=truck, task_template=tmpl, is_active=False
        )
        self.assertEqual(pm.status(), 'inactive')

    def test_job_order_auto_number(self):
        jo = JobOrder.objects.create(
            truck=create_truck(), title='Test JO',
            created_by=create_admin()
        )
        year = timezone.now().year
        self.assertEqual(jo.jo_number, f'JO-{year}-0001')

    def test_job_order_auto_number_increment(self):
        truck = create_truck()
        admin = create_admin()
        JobOrder.objects.create(truck=truck, title='First', created_by=admin)
        jo2 = JobOrder.objects.create(truck=truck, title='Second', created_by=admin)
        year = timezone.now().year
        self.assertEqual(jo2.jo_number, f'JO-{year}-0002')

    def test_line_item_parts_cost(self):
        jo = JobOrder.objects.create(
            truck=create_truck(), title='Test', created_by=create_admin()
        )
        item = JobOrderLineItem.objects.create(
            job_order=jo, description='Change Oil', status='DONE'
        )
        LineItemPart.objects.create(
            line_item=item, part_name='Oil', quantity=5, unit_cost=100
        )
        LineItemPart.objects.create(
            line_item=item, part_name='Filter', quantity=1, unit_cost=250
        )
        self.assertEqual(item.total_parts_cost(), 750.0)
        self.assertEqual(jo.total_parts_cost(), 750.0)

    def test_service_log_entry(self):
        truck = create_truck()
        admin = create_admin()
        jo = JobOrder.objects.create(truck=truck, title='Test', created_by=admin)
        entry = ServiceLogEntry.objects.create(
            job_order=jo, truck=truck,
            action='CLOSED',
            description='Test log',
            performed_by=admin,
            labor_hours=2.5,
            parts_cost=500.0
        )
        self.assertEqual(str(entry).split('|')[1].strip(), truck.unit_number)
        self.assertEqual(entry.labor_hours, 2.5)

    def test_contractor_skills(self):
        c = create_contractor()
        self.assertIn('Welding', c.skills_list())
        self.assertIn('Fabrication', c.skills_list())


# ─── 2. VIEW & ACCESS CONTROL TESTS ────────────────────────────

class ViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.super = create_super()
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.contractor_user = create_contractor_user()
        self.truck = create_truck()
        self.cat = create_category()
        self.tmpl = create_template(self.cat)
        self.contractor = create_contractor()
        # Create PM schedule for truck
        PMSchedule.objects.create(truck=self.truck, task_template=self.tmpl)

    def test_login_required_redirects(self):
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_login_success(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)

    # ── Dashboard ──

    def test_dashboard_loads_for_all_roles(self):
        for user in [self.super, self.admin, self.staff, self.mechanic, self.contractor_user]:
            self.client.login(username=user.username, password='pass')
            response = self.client.get(reverse('accounts:dashboard'))
            self.assertEqual(response.status_code, 200)
            self.client.logout()

    # ── Trucks ──

    def test_truck_list_loads(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('trucks:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'T-001')

    def test_truck_create_allowed_for_admin(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('trucks:create'))
        self.assertEqual(response.status_code, 200)

    def test_truck_create_allowed_for_super(self):
        self.client.login(username='super', password='pass')
        response = self.client.get(reverse('trucks:create'))
        self.assertEqual(response.status_code, 200)

    def test_truck_create_denied_for_staff(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('trucks:create'))
        self.assertEqual(response.status_code, 403)

    def test_truck_create_denied_for_mechanic(self):
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('trucks:create'))
        self.assertEqual(response.status_code, 403)

    def test_truck_post_creates_pm_schedules(self):
        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('trucks:create'), {
            'unit_number': 'T-002', 'plate_number': 'XYZ-999',
            'make': 'Hino', 'model': 'GH', 'year': 2021,
            'current_mileage_km': 5000,
            'current_engine_hours': 0,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        truck = Truck.objects.get(unit_number='T-002')
        self.assertTrue(PMSchedule.objects.filter(truck=truck).exists())

    def test_truck_detail_loads(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('trucks:detail', args=[self.truck.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'T-001')

    # ── PMS ──

    def test_pm_schedule_list_loads(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('pms:schedule_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'T-001')

    def test_pm_schedule_list_with_filter(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(
            reverse('pms:schedule_list'),
            {'truck': self.truck.pk}
        )
        self.assertEqual(response.status_code, 200)

    def test_pm_sync_all(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('pms:sync_all'), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_pm_sync_truck(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(
            reverse('pms:sync_truck', args=[self.truck.pk]),
            follow=True
        )
        self.assertEqual(response.status_code, 200)

    def test_category_create_allowed_for_admin(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('pms:category_create'))
        self.assertEqual(response.status_code, 200)

    def test_category_create_denied_for_staff(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('pms:category_create'))
        self.assertEqual(response.status_code, 403)

    def test_template_create_allowed_for_admin(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('pms:template_create'))
        self.assertEqual(response.status_code, 200)

    # ── Job Orders ──

    def test_job_order_list_access(self):
        """Staff should see all JOs, mechanic should only see theirs"""
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test JO',
            created_by=self.admin, assigned_to=self.mechanic
        )
        # Staff sees all
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('joborders:list'))
        self.assertContains(response, 'Test JO')

    def test_job_order_list_mechanic_filtered(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test JO',
            created_by=self.admin, assigned_to=self.mechanic
        )
        # Another mechanic should not see it
        other_mech = User.objects.create_user(
            username='mech2', password='pass', role=User.Role.MECHANIC
        )
        self.client.login(username='mech2', password='pass')
        response = self.client.get(reverse('joborders:list'))
        self.assertNotContains(response, 'Test JO')

    def test_job_order_create_allowed_for_staff(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('joborders:create'))
        self.assertEqual(response.status_code, 200)

    def test_job_order_create_denied_for_mechanic(self):
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('joborders:create'))
        self.assertEqual(response.status_code, 403)

    def test_job_order_detail_mechanic_can_view_assigned(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='My JO',
            created_by=self.admin, assigned_to=self.mechanic
        )
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('joborders:detail', args=[jo.pk]))
        self.assertEqual(response.status_code, 200)

    def test_job_order_detail_mechanic_cannot_view_others(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Not Mine',
            created_by=self.admin, assigned_to=self.admin
        )
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('joborders:detail', args=[jo.pk]))
        self.assertEqual(response.status_code, 302)  # redirect

    def test_my_assignments_shows_only_assigned(self):
        JobOrder.objects.create(
            truck=self.truck, title='Mine',
            created_by=self.admin, assigned_to=self.mechanic
        )
        JobOrder.objects.create(
            truck=self.truck, title='Not Mine',
            created_by=self.admin, assigned_to=self.admin
        )
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('joborders:my_assignments'))
        self.assertContains(response, 'Mine')
        self.assertNotContains(response, 'Not Mine')

    def test_update_line_item_guarded(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test',
            created_by=self.admin, assigned_to=self.mechanic
        )
        item = JobOrderLineItem.objects.create(
            job_order=jo, description='Fix engine', status='PENDING'
        )
        # Other mechanic tries to update
        other = User.objects.create_user(
            username='mech3', password='pass', role=User.Role.MECHANIC
        )
        self.client.login(username='mech3', password='pass')
        response = self.client.get(
            reverse('joborders:update_line_item', args=[item.pk])
        )
        self.assertEqual(response.status_code, 302)  # redirect with error

    def test_update_line_item_owner_can_update(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test',
            created_by=self.admin, assigned_to=self.mechanic
        )
        item = JobOrderLineItem.objects.create(
            job_order=jo, description='Fix engine', status='PENDING'
        )
        self.client.login(username='mech', password='pass')
        response = self.client.get(
            reverse('joborders:update_line_item', args=[item.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_add_line_item_part_guarded(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test',
            created_by=self.admin, assigned_to=self.mechanic
        )
        item = JobOrderLineItem.objects.create(
            job_order=jo, description='Fix'
        )
        other = User.objects.create_user(
            username='mech4', password='pass', role=User.Role.MECHANIC
        )
        self.client.login(username='mech4', password='pass')
        response = self.client.get(
            reverse('joborders:add_line_item_part', args=[item.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_close_jo_allowed_for_staff(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test',
            created_by=self.admin
        )
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('joborders:close', args=[jo.pk]))
        self.assertEqual(response.status_code, 200)

    def test_close_jo_denied_for_mechanic(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test',
            created_by=self.admin, assigned_to=self.mechanic
        )
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('joborders:close', args=[jo.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cannot_edit_closed_jo(self):
        jo = JobOrder.objects.create(
            truck=self.truck, title='Test', status='CLOSED',
            created_by=self.admin
        )
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('joborders:update', args=[jo.pk]))
        self.assertEqual(response.status_code, 302)  # redirect with warning

    # ── Integration: JO→Close→PM Update ──

    def test_close_jo_updates_pm_schedule(self):
        self.client.login(username='admin', password='pass')
        jo = JobOrder.objects.create(
            truck=self.truck, title='PM Test',
            created_by=self.admin, assigned_to=self.mechanic
        )
        item = JobOrderLineItem.objects.create(
            job_order=jo, description='Change Oil',
            task_template=self.tmpl, status='DONE',
            actual_hours=1.5
        )
        response = self.client.post(
            reverse('joborders:close', args=[jo.pk]),
            {'status': 'CLOSED', 'completed_mileage_km': 10500},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        # PM schedule should be updated
        pm = PMSchedule.objects.get(truck=self.truck, task_template=self.tmpl)
        self.assertEqual(pm.last_mileage_km, 10500)
        # Service log should exist
        self.assertTrue(
            ServiceLogEntry.objects.filter(job_order=jo).exists()
        )

    # ── Contractor JO Flow ──

    def test_contractor_job_creation(self):
        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('joborders:create'), {
            'truck': self.truck.pk,
            'title': 'Contractor Work',
            'job_type': 'CONTRACTOR',
            'contractor': self.contractor.pk,
            'priority': 'MEDIUM',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            JobOrder.objects.filter(title='Contractor Work').exists()
        )

    # ── Service Log ──

    def test_service_log_ledger_loads(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('service_log:full_ledger'))
        self.assertEqual(response.status_code, 200)

    def test_truck_ledger_loads(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(
            reverse('service_log:truck_ledger', args=[self.truck.pk])
        )
        self.assertEqual(response.status_code, 200)

    # ── Contractors ──

    def test_contractor_list_allowed_for_admin(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('contractors:list'))
        self.assertEqual(response.status_code, 200)

    def test_contractor_list_denied_for_mechanic(self):
        self.client.login(username='mech', password='pass')
        response = self.client.get(reverse('contractors:list'))
        self.assertEqual(response.status_code, 403)

    def test_contractor_detail(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(
            reverse('contractors:detail', args=[self.contractor.pk])
        )
        self.assertEqual(response.status_code, 200)

    # ── KPI ──

    def test_kpi_mechanic_allowed_for_admin(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('kpi:mechanic'))
        self.assertEqual(response.status_code, 200)

    def test_kpi_mechanic_denied_for_staff(self):
        self.client.login(username='staff', password='pass')
        response = self.client.get(reverse('kpi:mechanic'))
        self.assertEqual(response.status_code, 403)

    def test_kpi_contractor(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('kpi:contractor'))
        self.assertEqual(response.status_code, 200)

    def test_kpi_truck_frequency(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('kpi:truck_frequency'))
        self.assertEqual(response.status_code, 200)

    # ── User Management ──

    def test_user_list_allowed_for_super(self):
        self.client.login(username='super', password='pass')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 200)

    def test_user_list_denied_for_admin(self):
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(response.status_code, 403)

    def test_user_list_role_filter(self):
        self.client.login(username='super', password='pass')
        response = self.client.get(
            reverse('accounts:user_list'), {'role': 'MECHANIC'}
        )
        self.assertEqual(response.status_code, 200)

    def test_user_create_allowed_for_super(self):
        self.client.login(username='super', password='pass')
        response = self.client.get(reverse('accounts:user_create'))
        self.assertEqual(response.status_code, 200)

    def test_user_create_post(self):
        self.client.login(username='super', password='pass')
        response = self.client.post(reverse('accounts:user_create'), {
            'username': 'newuser',
            'password1': 'Complex123!',
            'password2': 'Complex123!',
            'role': 'MECHANIC',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    # ── Pagination ──

    def test_truck_list_pagination(self):
        self.client.login(username='admin', password='pass')
        for i in range(5):
            Truck.objects.create(
                unit_number=f'BULK-{i:03d}',
                plate_number=f'PLT-{i:03d}',
                make='Test', model='X', year=2020
            )
        response = self.client.get(reverse('trucks:list'), {'page': 1})
        self.assertEqual(response.status_code, 200)
