from django.test import TestCase
from django.urls import reverse
from accounts.models import User


def create_user(role, username=None):
    return User.objects.create_user(
        username=username or role.lower(),
        password='pass',
        role=role,
        email=f'{role.lower()}@test.com',
        first_name=f'First{role}',
        last_name=f'Last{role}',
    )


class LoginTests(TestCase):
    def test_login_page_loads(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Login')

    def test_login_success(self):
        create_user(User.Role.STAFF, 'staffuser')
        resp = self.client.post(reverse('accounts:login'), {
            'username': 'staffuser', 'password': 'pass',
            'next': reverse('accounts:dashboard'),
        })
        self.assertEqual(resp.status_code, 302)

    def test_login_failure(self):
        resp = self.client.post(reverse('accounts:login'), {
            'username': 'nonexistent', 'password': 'wrong',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid username')


class DashboardTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='super', password='pass', role=User.Role.SUPER_ADMIN
        )
        self.admin = create_user(User.Role.ADMIN)
        self.staff = create_user(User.Role.STAFF)
        self.mechanic = create_user(User.Role.MECHANIC)

    def test_dashboard_redirects_anon(self):
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_loads_for_super(self):
        self.client.login(username='super', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_loads_for_admin(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_loads_for_staff(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_loads_for_mechanic(self):
        self.client.login(username='mechanic', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_staff_gets_performance_context(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['show_performance'])
        self.assertIn('performance', resp.context)
        self.assertContains(resp, 'Fleet Performance')

    def test_dashboard_mechanic_hides_performance_tab(self):
        self.client.login(username='mechanic', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['show_performance'])
        self.assertNotIn('performance', resp.context)
        self.assertNotContains(resp, 'Fleet Performance')

    def test_dashboard_trend_series(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(len(resp.context['trend_days']), 14)
        self.assertEqual(len(resp.context['trend_jo']), 14)
        self.assertEqual(len(resp.context['trend_pm']), 14)

    def test_dashboard_performance_tab_param(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'), {'tab': 'performance'})
        self.assertEqual(resp.context['active_tab'], 'performance')

    def test_dashboard_overview_default_tab(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.context['active_tab'], 'overview')

    def test_dashboard_performance_values(self):
        from fleetops.models import DailyLog
        from trucks.models import Truck
        from datetime import timedelta
        from django.utils import timezone
        Truck.objects.create(
            unit_number='T-DASH', plate_number='DASH-1',
            make='Isuzu', model='FVR', year=2020,
            current_mileage_km=1000, current_engine_hours=100,
            status='ACTIVE',
        )
        DailyLog.objects.create(
            truck=Truck.objects.get(unit_number='T-DASH'),
            date=timezone.localdate(),
            fuel_liters=50, distance_traveled_km=400,
            idle_hours=2, operating_hours=8,
        )
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.context['total_distance'], 400)
        self.assertEqual(resp.context['total_fuel'], 50)
        self.assertEqual(resp.context['total_efficiency'], 8.0)
        self.assertEqual(resp.context['total_utilization'], 80.0)


class UserManagementTests(TestCase):
    def setUp(self):
        self.super = User.objects.create_superuser(
            username='super', password='pass', role=User.Role.SUPER_ADMIN
        )
        self.admin = create_user(User.Role.ADMIN)
        self.staff = create_user(User.Role.STAFF)

    def test_user_list_super_allowed(self):
        self.client.login(username='super', password='pass')
        resp = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(resp.status_code, 200)

    def test_user_list_admin_denied(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(resp.status_code, 403)

    def test_user_list_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('accounts:user_list'))
        self.assertEqual(resp.status_code, 403)

    def test_user_list_role_filter(self):
        self.client.login(username='super', password='pass')
        resp = self.client.get(reverse('accounts:user_list'), {'role': 'STAFF'})
        self.assertEqual(resp.status_code, 200)

    def test_user_create_allowed(self):
        self.client.login(username='super', password='pass')
        resp = self.client.get(reverse('accounts:user_create'))
        self.assertEqual(resp.status_code, 200)

    def test_user_create_post(self):
        self.client.login(username='super', password='pass')
        resp = self.client.post(reverse('accounts:user_create'), {
            'username': 'newuser',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'role': User.Role.MECHANIC,
            'first_name': 'New',
            'last_name': 'User',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_user_create_admin_denied(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('accounts:user_create'))
        self.assertEqual(resp.status_code, 403)

    def test_user_update_allowed(self):
        self.client.login(username='super', password='pass')
        target = create_user(User.Role.MECHANIC, 'target_user')
        resp = self.client.get(reverse('accounts:user_update', args=[target.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_user_update_post(self):
        self.client.login(username='super', password='pass')
        target = create_user(User.Role.MECHANIC, 'target2')
        resp = self.client.post(
            reverse('accounts:user_update', args=[target.pk]),
            {'username': 'target2', 'role': User.Role.STAFF,
             'first_name': 'Updated', 'last_name': 'User'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.STAFF)

    def test_user_update_admin_denied(self):
        self.client.login(username='admin', password='pass')
        target = create_user(User.Role.MECHANIC, 'target3')
        resp = self.client.get(reverse('accounts:user_update', args=[target.pk]))
        self.assertEqual(resp.status_code, 403)


class RoleModelTests(TestCase):
    def test_user_creation_with_roles(self):
        for role, label in User.Role.choices:
            u = User.objects.create_user(
                username=role.lower(), password='pass', role=role
            )
            self.assertEqual(u.role, role)
            self.assertEqual(u.get_role_display(), label)

    def test_superuser_role_auto(self):
        u = User.objects.create_superuser(
            username='testsuper', password='pass', role=User.Role.SUPER_ADMIN
        )
        self.assertEqual(u.role, User.Role.SUPER_ADMIN)
        self.assertTrue(u.is_superuser)
