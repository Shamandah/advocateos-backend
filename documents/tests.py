import uuid
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Firm, User
from matters.models import Client, Matter
from .models import Document, DocumentVersion


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


def make_matter(firm, user):
    client = Client.objects.create(
        firm=firm, name=f'Client-{uuid.uuid4().hex[:6]}', created_by=user
    )
    return Matter.objects.create(
        firm=firm, title='Test Matter',
        client=client, practice_area='litigation', created_by=user,
    )


def make_pdf(name='test.pdf'):
    return SimpleUploadedFile(
        name, b'%PDF-1.4 fake pdf content for testing',
        content_type='application/pdf'
    )


class DocumentUploadTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)

    def test_upload_document(self):
        res = self.api.post('/api/v1/documents/', {
            'matter_id':   self.matter.id,
            'title':       'Plaint — Smith v. Acme',
            'doc_type':    'pleading',
            'description': 'Original plaint filed 1 Aug 2026',
            'file':        make_pdf('plaint.pdf'),
        }, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['title'], 'Plaint — Smith v. Acme')
        self.assertEqual(res.data['doc_type'], 'pleading')
        self.assertEqual(res.data['version_count'], 1)
        self.assertEqual(res.data['latest_version']['version_number'], 1)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(DocumentVersion.objects.count(), 1)

    def test_file_too_large_rejected(self):
        big_file = SimpleUploadedFile(
            'big.pdf', b'x' * (21 * 1024 * 1024),
            content_type='application/pdf'
        )
        res = self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id,
            'title':     'Too Large',
            'file':      big_file,
        }, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_firm_matter_rejected(self):
        other_firm, other_user = make_firm_and_user('Other Firm', 'b@firm.co.ke')
        other_matter = make_matter(other_firm, other_user)
        res = self.api.post('/api/v1/documents/', {
            'matter_id': other_matter.id,
            'title':     'Bad Upload',
            'file':      make_pdf(),
        }, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_documents(self):
        # Upload two documents
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Doc A',
            'file': make_pdf('a.pdf'),
        }, format='multipart')
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Doc B',
            'file': make_pdf('b.pdf'),
        }, format='multipart')
        res = self.api.get('/api/v1/documents/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)

    def test_filter_by_matter(self):
        other_matter = make_matter(self.firm, self.user)
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Matter 1 Doc',
            'file': make_pdf(),
        }, format='multipart')
        self.api.post('/api/v1/documents/', {
            'matter_id': other_matter.id, 'title': 'Matter 2 Doc',
            'file': make_pdf(),
        }, format='multipart')
        res = self.api.get(f'/api/v1/documents/?matter_id={self.matter.id}')
        self.assertEqual(res.data['count'], 1)

    def test_search_documents(self):
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Plaint Smith',
            'file': make_pdf(),
        }, format='multipart')
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Affidavit Jones',
            'file': make_pdf(),
        }, format='multipart')
        res = self.api.get('/api/v1/documents/?search=Plaint')
        self.assertEqual(res.data['count'], 1)

    def test_other_firm_documents_invisible(self):
        other_firm, other_user = make_firm_and_user('Firm B', 'c@firm.co.ke')
        other_matter = make_matter(other_firm, other_user)
        other_api = auth_client(other_user)
        other_api.post('/api/v1/documents/', {
            'matter_id': other_matter.id, 'title': 'Hidden Doc',
            'file': make_pdf(),
        }, format='multipart')
        res = self.api.get('/api/v1/documents/')
        self.assertEqual(res.data['count'], 0)


class DocumentDetailTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)
        res = self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id,
            'title':     'Original Plaint',
            'doc_type':  'pleading',
            'file':      make_pdf('plaint.pdf'),
        }, format='multipart')
        self.doc_id = res.data['id']

    def test_get_document_detail(self):
        res = self.api.get(f'/api/v1/documents/{self.doc_id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], 'Original Plaint')
        self.assertEqual(res.data['version_count'], 1)

    def test_patch_document_metadata(self):
        res = self.api.patch(f'/api/v1/documents/{self.doc_id}/', {
            'title':       'Amended Plaint',
            'description': 'Updated after amendment',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], 'Amended Plaint')

    def test_delete_document(self):
        res = self.api.delete(f'/api/v1/documents/{self.doc_id}/')
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(DocumentVersion.objects.count(), 0)


class DocumentVersionTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)
        res = self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id,
            'title':     'Defence',
            'file':      make_pdf('defence_v1.pdf'),
        }, format='multipart')
        self.doc_id = res.data['id']

    def test_upload_new_version(self):
        res = self.api.post(f'/api/v1/documents/{self.doc_id}/versions/', {
            'file':        make_pdf('defence_v2.pdf'),
            'change_note': 'Added new paragraph 4',
        }, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['version_number'], 2)
        self.assertEqual(DocumentVersion.objects.count(), 2)

    def test_version_list(self):
        self.api.post(f'/api/v1/documents/{self.doc_id}/versions/', {
            'file': make_pdf('v2.pdf'), 'change_note': 'Version 2',
        }, format='multipart')
        res = self.api.get(f'/api/v1/documents/{self.doc_id}/versions/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['version_count'], 2)
        self.assertEqual(len(res.data['versions']), 2)

    def test_versions_are_sequential(self):
        self.api.post(f'/api/v1/documents/{self.doc_id}/versions/', {
            'file': make_pdf('v2.pdf'),
        }, format='multipart')
        self.api.post(f'/api/v1/documents/{self.doc_id}/versions/', {
            'file': make_pdf('v3.pdf'),
        }, format='multipart')
        res = self.api.get(f'/api/v1/documents/{self.doc_id}/versions/')
        nums = [v['version_number'] for v in res.data['versions']]
        self.assertIn(3, nums)
        self.assertIn(2, nums)
        self.assertIn(1, nums)


class MatterDocumentsTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)

    def test_matter_documents_endpoint(self):
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Doc 1',
            'file': make_pdf(),
        }, format='multipart')
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Doc 2',
            'file': make_pdf(),
        }, format='multipart')
        res = self.api.get(f'/api/v1/documents/matter/{self.matter.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)
        self.assertEqual(res.data['matter']['reference'], self.matter.reference)

    def test_document_stats(self):
        self.api.post('/api/v1/documents/', {
            'matter_id': self.matter.id, 'title': 'Pleading',
            'doc_type': 'pleading', 'file': make_pdf(),
        }, format='multipart')
        res = self.api.get('/api/v1/documents/stats/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['total_documents'], 1)
        self.assertEqual(res.data['total_versions'], 1)
        self.assertIn('total_size_mb', res.data)
        self.assertIn('by_type', res.data)