from datetime import date, time, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from training.models import Training, Attendance, TaskRating, WeeklyReview, Holiday
from pms.models import TaskCategory, TaskTemplate


def create_supervisor():
    return User.objects.create_user(
        username='supervisor', password='pass', role=User.Role.STAFF
    )


def create_trainee():
    return User.objects.create_user(
        username='trainee1', password='pass', role=User.Role.TRAINEE
    )


def create_admin():
    return User.objects.create_user(
        username='admin', password='pass', role=User.Role.ADMIN
    )


def create_training(trainee=None, supervisor=None):
    if trainee is None:
        trainee = create_trainee()
    if supervisor is None:
        supervisor = create_supervisor()
    return Training.objects.create(
        ojt=trainee,
        supervisor=supervisor,
        start_date=timezone.now().date() - timedelta(days=30),
        status='ACTIVE',
    )


class TrainingModelTests(TestCase):
    def setUp(self):
        self.trainee = create_trainee()
        self.supervisor = create_supervisor()
        self.training = create_training(self.trainee, self.supervisor)

    def test_training_creation(self):
        self.assertEqual(self.training.status, 'ACTIVE')
        self.assertEqual(self.training.ojt, self.trainee)

    def test_attendance_check_in(self):
        att = Attendance.objects.create(training=self.training)
        self.assertIsNotNone(att.time_in)
        self.assertIsNone(att.time_out)

    def test_attendance_check_out(self):
        att = Attendance.objects.create(training=self.training)
        att.time_out = timezone.now().time()
        att.save()
        self.assertIsNotNone(att.time_out)

    def test_task_rating_creation(self):
        rating = TaskRating.objects.create(
            training=self.training,
            supervisor=self.supervisor,
            task_name='Oil Change',
            rating=4,
        )
        self.assertEqual(rating.rating, 4)

    def test_weekly_review_creation(self):
        review = WeeklyReview.objects.create(
            training=self.training,
            week_start=timezone.now().date() - timedelta(days=7),
            week_end=timezone.now().date(),
            overall_score=4.5,
        )
        self.assertEqual(review.overall_score, 4.5)
        self.assertEqual(review.status, 'DRAFT')

    def test_holiday_creation(self):
        holiday = Holiday.objects.create(
            date=date(2026, 12, 25),
            name='Christmas Day',
            created_by=self.admin if hasattr(self, 'admin') else create_admin(),
        )
        self.assertIn('Christmas Day', str(holiday))
        self.assertIn('2026-12-25', str(holiday))


class TrainingViewTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.supervisor = create_supervisor()
        self.trainee = create_trainee()
        self.other_trainee = User.objects.create_user(
            username='trainee2', password='pass', role=User.Role.TRAINEE
        )
        self.training = create_training(self.trainee, self.supervisor)
        # Create second training for other_trainee with same supervisor
        self.training2 = Training.objects.create(
            ojt=self.other_trainee,
            supervisor=self.supervisor,
            start_date=timezone.now().date() - timedelta(days=15),
            status='ACTIVE',
        )

    def test_dashboard_trainee_loads(self):
        self.client.login(username='trainee1', password='pass')
        resp = self.client.get(reverse('training:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_supervisor_loads(self):
        self.client.login(username='supervisor', password='pass')
        resp = self.client.get(reverse('training:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_unauthenticated_redirect(self):
        resp = self.client.get(reverse('training:dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_attendance_check_in(self):
        self.client.login(username='trainee1', password='pass')
        resp = self.client.post(reverse('training:attendance_check_in'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Attendance.objects.filter(
            training=self.training, date=timezone.now().date()
        ).exists())

    def test_attendance_check_in_already_checked(self):
        self.client.login(username='trainee1', password='pass')
        self.client.post(reverse('training:attendance_check_in'))
        resp = self.client.post(reverse('training:attendance_check_in'))
        self.assertEqual(resp.status_code, 302)

    def test_attendance_check_out(self):
        self.client.login(username='trainee1', password='pass')
        self.client.post(reverse('training:attendance_check_in'))
        resp = self.client.post(reverse('training:attendance_check_out'))
        self.assertEqual(resp.status_code, 302)

    def test_attendance_list_trainee(self):
        self.client.login(username='trainee1', password='pass')
        resp = self.client.get(reverse('training:attendance_list'))
        self.assertEqual(resp.status_code, 200)

    def test_rating_create_admin_allowed(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:rating_create'))
        self.assertEqual(resp.status_code, 200)

    def test_rating_create_post(self):
        self.client.login(username='supervisor', password='pass')
        cat = TaskCategory.objects.create(name='Engine')
        tmpl = TaskTemplate.objects.create(
            category=cat, name='Oil Change',
            interval_type='MILEAGE', interval_value=5000,
        )
        resp = self.client.post(reverse('training:rating_create'), {
            'training': self.training.pk,
            'task_template': tmpl.pk,
            'rating': 4,
            'comments': 'Good job',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(TaskRating.objects.filter(
            training=self.training, rating=4
        ).exists())

    def test_rating_list(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:rating_list'))
        self.assertEqual(resp.status_code, 200)

    def test_rating_detail(self):
        self.client.login(username='admin', password='pass')
        rating = TaskRating.objects.create(
            training=self.training, supervisor=self.supervisor,
            task_name='Test', rating=5,
        )
        resp = self.client.get(reverse('training:rating_detail', args=[rating.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_review_create_post(self):
        self.client.login(username='supervisor', password='pass')
        resp = self.client.post(reverse('training:review_create'), {
            'training': self.training.pk,
            'week_start': timezone.now().date() - timedelta(days=7),
            'week_end': timezone.now().date(),
            'overall_score': 4.0,
            'strengths': 'Good progress',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(WeeklyReview.objects.filter(
            training=self.training, overall_score=4.0
        ).exists())

    def test_review_list(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:review_list'))
        self.assertEqual(resp.status_code, 200)

    def test_ojt_detail(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:ojt_detail', args=[self.training.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_ojt_rating_list(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:ojt_rating_list', args=[self.training.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_ojt_review_list(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:ojt_review_list', args=[self.training.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_assign_training(self):
        self.client.login(username='admin', password='pass')
        new_trainee = User.objects.create_user(
            username='newtrainee', password='pass', role=User.Role.TRAINEE
        )
        resp = self.client.post(reverse('training:assign'), {
            'ojt': new_trainee.pk,
            'supervisor': self.supervisor.pk,
            'start_date': timezone.now().date(),
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Training.objects.filter(ojt=new_trainee).exists())

    def test_holiday_list(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('training:holiday_list'))
        self.assertEqual(resp.status_code, 200)

    def test_no_active_training_message(self):
        no_training_user = User.objects.create_user(
            username='notrainee', password='pass', role=User.Role.TRAINEE
        )
        self.client.login(username='notrainee', password='pass')
        resp = self.client.get(reverse('training:dashboard'))
        self.assertEqual(resp.status_code, 200)
