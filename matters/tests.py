"""
matters/tests.py
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Firm, User
from .models import Client, Matter


def make_firm_and_user(firm_name='Test Firm', email='amanda@firm.co.ke', role=User.Role.MANAGING_PARTNER):
    # No lsk_number — avoids UNIQUE constraint across tests
    firm = Firm.objects.create(name=firm_name)
    user = User.objects.create_user(
        email=email, password='Pass1234!',
        first_name='Amanda', last_name='Test',
        firm=firm, role=role,
    )
    return firm, user


def auth_client(user):
    c = APIClient()
    res = c.post('/api/v1/auth/login/',
                 {'email': user.email, 'password': 'Pass1234!'},
                 format='json')
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return c


class ClientAPITestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api = auth_client(self.user)

    def test_create_client(self):
        res = self.api.post('/api/v1/clients/', {
            'name': 'John Otieno', 'email': 'john@email.com',
            'phone': '+254712345678', 'is_company': False,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], 'John Otieno')
        self.assertEqual(Client.objects.count(), 1)

    def test_create_company_client(self):
        res = self.api.post('/api/v1/clients/', {
            'name': 'Acme Corp Ltd', 'is_company': True,
            'id_number': 'CPR/2020/12345',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['is_company'])

    def test_list_clients(self):
        Client.objects.create(firm=self.firm, name='Alice', created_by=self.user)
        Client.objects.create(firm=self.firm, name='Bob', created_by=self.user)
        res = self.api.get('/api/v1/clients/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)

    def test_search_clients(self):
        Client.objects.create(firm=self.firm, name='Alice Wanjiru', created_by=self.user)
        Client.objects.create(firm=self.firm, name='Bob Otieno', created_by=self.user)
        res = self.api.get('/api/v1/clients/?search=Alice')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)

    def test_other_firm_clients_invisible(self):
        # Use unique firm name — no lsk_number to avoid UNIQUE constraint
        other_firm = Firm.objects.create(name='Other Firm XYZ')
        Client.objects.create(firm=other_firm, name='Ghost Client')
        res = self.api.get('/api/v1/clients/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 0)

    def test_delete_client_with_matters_blocked(self):
        client = Client.objects.create(
            firm=self.firm, name='Client A', created_by=self.user
        )
        Matter.objects.create(
            firm=self.firm, title='Test Matter', client=client,
            practice_area='litigation', created_by=self.user,
        )
        res = self.api.delete(f'/api/v1/clients/{client.id}/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['code'], 'ERR_HAS_MATTERS')


class MatterAPITestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api        = auth_client(self.user)
        self.client_obj = Client.objects.create(
            firm=self.firm, name='Test Client', created_by=self.user
        )

    def _create_matter(self, title='Smith v. Acme'):
        res = self.api.post('/api/v1/matters/', {
            'title':         title,
            'client_id':     self.client_obj.id,
            'practice_area': 'litigation',
            'court':         'High Court Nairobi',
        }, format='json')
        return res

    def test_create_matter_auto_reference(self):
        res = self._create_matter()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['reference'].startswith('ADV/'))
        self.assertEqual(Matter.objects.count(), 1)

    def test_references_are_sequential(self):
        res1 = self._create_matter('Matter One')
        res2 = self._create_matter('Matter Two')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['reference'].split('/')[-1], '001')
        self.assertEqual(res2.data['reference'].split('/')[-1], '002')

    def test_list_matters(self):
        self._create_matter('Matter A')
        self._create_matter('Matter B')
        res = self.api.get('/api/v1/matters/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)

    def test_filter_by_status(self):
        res = self._create_matter('Open Matter')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        matter_id = res.data['id']
        self.api.patch(f'/api/v1/matters/{matter_id}/', {'status': 'closed'}, format='json')
        res_open   = self.api.get('/api/v1/matters/?status=open')
        res_closed = self.api.get('/api/v1/matters/?status=closed')
        self.assertEqual(res_open.data['count'],   0)
        self.assertEqual(res_closed.data['count'], 1)

    def test_search_matters(self):
        self._create_matter('Smith v. Acme')
        self._create_matter('Jones v. State')
        res = self.api.get('/api/v1/matters/?search=Smith')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)

    def test_other_firm_matters_invisible(self):
        other_firm   = Firm.objects.create(name='Other Firm ABC')
        other_client = Client.objects.create(firm=other_firm, name='Other Client')
        Matter.objects.create(
            firm=other_firm, title='Other Matter',
            client=other_client, practice_area='litigation',
        )
        res = self.api.get('/api/v1/matters/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 0)

    def test_patch_matter_status(self):
        res = self._create_matter()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        matter_id = res.data['id']
        patch_res = self.api.patch(
            f'/api/v1/matters/{matter_id}/', {'status': 'closed'}, format='json'
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['status'], 'closed')

    def test_delete_non_archived_matter_blocked(self):
        res = self._create_matter()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        matter_id = res.data['id']
        del_res = self.api.delete(f'/api/v1/matters/{matter_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(del_res.data['code'], 'ERR_NOT_ARCHIVED')

    def test_delete_archived_matter(self):
        res = self._create_matter()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        matter_id = res.data['id']
        self.api.patch(f'/api/v1/matters/{matter_id}/', {'status': 'archived'}, format='json')
        del_res = self.api.delete(f'/api/v1/matters/{matter_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

    def test_cross_firm_client_rejected(self):
        other_firm   = Firm.objects.create(name='Foreign Firm DEF')
        other_client = Client.objects.create(firm=other_firm, name='Foreign Client')
        res = self.api.post('/api/v1/matters/', {
            'title':         'Bad Matter',
            'client_id':     other_client.id,
            'practice_area': 'litigation',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class MatterNoteTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        client      = Client.objects.create(
            firm=self.firm, name='Client A', created_by=self.user
        )
        res = self.api.post('/api/v1/matters/', {
            'title':         'Test Matter',
            'client_id':     client.id,
            'practice_area': 'litigation',
        }, format='json')
        self.matter_id = res.data['id']

    def test_add_note(self):
        res = self.api.post(f'/api/v1/matters/{self.matter_id}/notes/', {
            'body': 'Client confirmed settlement.'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['body'], 'Client confirmed settlement.')

    def test_list_notes(self):
        self.api.post(f'/api/v1/matters/{self.matter_id}/notes/', {'body': 'Note 1'}, format='json')
        self.api.post(f'/api/v1/matters/{self.matter_id}/notes/', {'body': 'Note 2'}, format='json')
        res = self.api.get(f'/api/v1/matters/{self.matter_id}/notes/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)

    def test_blank_note_rejected(self):
        res = self.api.post(f'/api/v1/matters/{self.matter_id}/notes/', {
            'body': '   '
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)