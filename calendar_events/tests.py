from datetime import date, timedelta
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Firm, User
from matters.models import Client, Matter
from .models import CourtEvent


def make_firm_and_user(firm_name='Test Firm', email='amanda@firm.co.ke'):
    firm = Firm.objects.create(name=firm_name)
    user = User.objects.create_user(
        email=email, password='Pass1234!',
        first_name='Amanda', last_name='Test',
        firm=firm, role=User.Role.MANAGING_PARTNER,
    )
    return firm, user


def auth_client(user):
    c = APIClient()
    res = c.post('/api/v1/auth/login/',
                 {'email': user.email, 'password': 'Pass1234!'},
                 format='json')
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return c


def make_matter(firm, user, title='Test Matter'):
    """Create matter via API to trigger proper reference auto-generation."""
    from matters.models import Client
    import uuid
    # Use unique client name per call to avoid collisions
    client = Client.objects.create(
        firm=firm,
        name=f'Client-{uuid.uuid4().hex[:8]}',
        created_by=user
    )
    matter = Matter.objects.create(
        firm=firm,
        title=title,
        client=client,
        practice_area='litigation',
        created_by=user,
    )
    return matter


class CourtEventCRUDTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)
        self.today  = date.today().isoformat()

    def _create_event(self, overrides=None):
        payload = {
            'matter_id':  self.matter.id,
            'title':      'Smith v. Acme — Motion Hearing',
            'event_type': 'hearing',
            'date':       self.today,
            'start_time': '09:30:00',
            'end_time':   '11:00:00',
            'court':      'High Court Nairobi, Courtroom 4',
            'all_day':    False,
        }
        if overrides:
            payload.update(overrides)
        return self.api.post('/api/v1/calendar/events/', payload, format='json')

    # ── Create ────────────────────────────────────────────────────────────────

    def test_create_hearing_event(self):
        res = self._create_event()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], 'Smith v. Acme — Motion Hearing')
        self.assertEqual(res.data['event_type'], 'hearing')
        self.assertEqual(res.data['source'], 'manual')
        self.assertEqual(CourtEvent.objects.count(), 1)

    def test_create_all_day_deadline(self):
        res = self._create_event({
            'title':      'Filing Deadline — Chen LLC',
            'event_type': 'deadline',
            'all_day':    True,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['all_day'])
        # All-day events should have no time fields
        self.assertIsNone(res.data['start_time'])
        self.assertIsNone(res.data['end_time'])

    def test_end_time_before_start_time_rejected(self):
        res = self._create_event({
            'start_time': '11:00:00',
            'end_time':   '09:00:00',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_firm_matter_rejected(self):
        other_firm, other_user = make_firm_and_user('Other Firm', 'other@firm.co.ke')
        other_matter = make_matter(other_firm, other_user)
        res = self._create_event({'matter_id': other_matter.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ── List ─────────────────────────────────────────────────────────────────

    def test_list_events(self):
        self._create_event()
        self._create_event({'title': 'Second Event', 'event_type': 'mediation'})
        res = self.api.get('/api/v1/calendar/events/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)

    def test_filter_by_event_type(self):
        self._create_event({'event_type': 'hearing'})
        self._create_event({'title': 'Deadline', 'event_type': 'deadline'})
        res = self.api.get('/api/v1/calendar/events/?event_type=hearing')
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['results'][0]['event_type'], 'hearing')

    def test_filter_by_matter(self):
        other_matter = make_matter(self.firm, self.user)
        self._create_event()
        self._create_event({'matter_id': other_matter.id, 'title': 'Other Matter Event'})
        res = self.api.get(f'/api/v1/calendar/events/?matter_id={self.matter.id}')
        self.assertEqual(res.data['count'], 1)

    def test_filter_upcoming(self):
        past_date   = (date.today() - timedelta(days=5)).isoformat()
        future_date = (date.today() + timedelta(days=5)).isoformat()
        self._create_event({'date': past_date,   'title': 'Past Event'})
        self._create_event({'date': future_date, 'title': 'Future Event'})
        res = self.api.get('/api/v1/calendar/events/?upcoming=true')
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(res.data['results'][0]['title'], 'Future Event')

    def test_other_firm_events_invisible(self):
        other_firm, other_user = make_firm_and_user('Other Firm B', 'b@firm.co.ke')
        other_matter = make_matter(other_firm, other_user)
        CourtEvent.objects.create(
            firm=other_firm, matter=other_matter,
            title='Other Firm Event', event_type='hearing',
            date=date.today(), created_by=other_user,
        )
        res = self.api.get('/api/v1/calendar/events/')
        self.assertEqual(res.data['count'], 0)

    # ── Detail ────────────────────────────────────────────────────────────────

    def test_get_event_detail(self):
        res = self._create_event()
        event_id = res.data['id']
        res = self.api.get(f'/api/v1/calendar/events/{event_id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['court'], 'High Court Nairobi, Courtroom 4')

    def test_patch_event_status(self):
        res = self._create_event()
        event_id = res.data['id']
        patch = self.api.patch(
            f'/api/v1/calendar/events/{event_id}/',
            {'status': 'completed', 'outcome': 'Matter adjourned to 15 Oct.'},
            format='json'
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['status'], 'completed')
        self.assertEqual(patch.data['outcome'], 'Matter adjourned to 15 Oct.')

    def test_delete_manual_event(self):
        res = self._create_event()
        event_id = res.data['id']
        del_res = self.api.delete(f'/api/v1/calendar/events/{event_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CourtEvent.objects.count(), 0)

    def test_delete_jicms_event_blocked(self):
        event = CourtEvent.objects.create(
            firm=self.firm, matter=self.matter,
            title='JICMS Hearing', event_type='hearing',
            date=date.today(), source=CourtEvent.Source.JICMS,
            jicms_id='JICMS-12345', created_by=self.user,
        )
        res = self.api.delete(f'/api/v1/calendar/events/{event.id}/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['code'], 'ERR_JICMS_EVENT')
        self.assertEqual(CourtEvent.objects.count(), 1)

    # ── Upcoming summary ──────────────────────────────────────────────────────

    def test_upcoming_summary(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        next_week = (date.today() + timedelta(days=8)).isoformat()
        self._create_event({'date': tomorrow,  'event_type': 'hearing'})
        self._create_event({'date': tomorrow,  'event_type': 'deadline', 'title': 'Deadline'})
        self._create_event({'date': next_week, 'title': 'Next Week'})  # outside 7-day window
        res = self.api.get('/api/v1/calendar/upcoming/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['counts']['total'], 2)
        self.assertEqual(res.data['counts']['hearings'], 1)
        self.assertEqual(res.data['counts']['deadlines'], 1)

    # ── JICMS sync stub ───────────────────────────────────────────────────────

    def test_jicms_sync_returns_202(self):
        res = self.api.post('/api/v1/calendar/sync/jicms/')
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(res.data['status'], 'sync_queued')

# Create your tests here.
