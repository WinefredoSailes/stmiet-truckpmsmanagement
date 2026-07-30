from django.test import TestCase
from django.urls import reverse
from accounts.models import User
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


def create_contractor(**kw):
    defaults = dict(
        company_name='Test Welding Shop',
        contact_person='Juan Dela Cruz',
        mobile='09170000000',
        skills='Welding, Fabrication, Electrical',
    )
    defaults.update(kw)
    return Contractor.objects.create(**defaults)


class ContractorModelTests(TestCase):
    def test_contractor_creation(self):
        c = create_contractor()
        self.assertEqual(str(c), 'Test Welding Shop')

    def test_skills_list(self):
        c = create_contractor()
        self.assertEqual(c.skills_list(), ['Welding', 'Fabrication', 'Electrical'])

    def test_skills_list_empty(self):
        c = create_contractor(skills='')
        self.assertEqual(c.skills_list(), [])

    def test_is_active_default(self):
        c = create_contractor()
        self.assertTrue(c.is_active)


class ContractorViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.staff = create_staff()
        self.mechanic = create_mechanic()
        self.contractor = create_contractor()

    def test_list_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('contractors:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Welding Shop')

    def test_list_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('contractors:list'))
        self.assertEqual(resp.status_code, 403)

    def test_list_mechanic_denied(self):
        self.client.login(username='mech', password='pass')
        resp = self.client.get(reverse('contractors:list'))
        self.assertEqual(resp.status_code, 403)

    def test_detail_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('contractors:detail', args=[self.contractor.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_create_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('contractors:create'))
        self.assertEqual(resp.status_code, 200)

    def test_create_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('contractors:create'), {
            'company_name': 'New Welding',
            'contact_person': 'Pedro',
            'mobile': '09181111111',
            'skills': 'Welding',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Contractor.objects.filter(company_name='New Welding').exists())

    def test_update_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('contractors:update', args=[self.contractor.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_update_post(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(
            reverse('contractors:update', args=[self.contractor.pk]),
            {'company_name': 'Updated Shop', 'contact_person': 'Maria',
             'mobile': '09182222222', 'skills': 'Painting'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.contractor.refresh_from_db()
        self.assertEqual(self.contractor.company_name, 'Updated Shop')

    def test_update_staff_denied(self):
        self.client.login(username='staff', password='pass')
        resp = self.client.get(reverse('contractors:update', args=[self.contractor.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_redirect(self):
        resp = self.client.get(reverse('contractors:list'))
        self.assertEqual(resp.status_code, 302)
