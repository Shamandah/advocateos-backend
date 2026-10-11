from django.test import TestCase

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Firm
from matters.models import Client, Matter

from .models import (
    DocumentGeneration,
    Template,
    TemplateClause,
    TemplateVariable,
    TemplateVersion,
)

User = get_user_model()


class TemplateRegistryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.firm = Firm.objects.create(name="Registry Test Firm")
        cls.user = User.objects.create_user(
            email="registry-test@example.com",
            password="test-password-only",
            firm=cls.firm,
        )
        cls.client = Client.objects.create(
            firm=cls.firm,
            name="Test Client",
            created_by=cls.user,
        )
        cls.matter = Matter.objects.create(
            firm=cls.firm,
            client=cls.client,
            title="Test Matter",
            created_by=cls.user,
        )

        cls.template = Template.objects.create(
            name="Sample Plaint",
            slug="sample-plaint",
            category="LITIGATION",
            document_type="Plaint",
            jurisdiction="Kenya",
            owner_firm=cls.firm,
            created_by=cls.user,
        )

        cls.version = TemplateVersion.objects.create(
            template=cls.template,
            version_number=1,
            status="draft",
            created_by=cls.user,
        )

    def test_template_can_be_created(self):
        self.assertEqual(self.template.name, "Sample Plaint")
        self.assertEqual(self.template.owner_firm, self.firm)
        self.assertFalse(self.template.is_system_template)

    def test_system_template_can_be_created(self):
        template = Template.objects.create(
            name="System Demand Letter",
            slug="system-demand-letter",
            category="CORRESPONDENCE",
            document_type="Demand Letter",
            is_system_template=True,
            owner_firm=None,
        )

        self.assertTrue(template.is_system_template)
        self.assertIsNone(template.owner_firm)

    def test_template_versions_are_unique_per_template(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TemplateVersion.objects.create(
                    template=self.template,
                    version_number=1,
                )

    def test_template_versions_can_have_different_numbers(self):
        second = TemplateVersion.objects.create(
            template=self.template,
            version_number=2,
        )

        self.assertEqual(second.version_number, 2)
        self.assertEqual(self.template.versions.count(), 2)

    def test_variable_is_attached_to_template_version(self):
        variable = TemplateVariable.objects.create(
            template_version=self.version,
            key="CLIENT_NAME",
            label="Client Name",
            data_type="text",
            required=True,
            source_type="client",
            source_path="name",
        )

        self.assertEqual(variable.template_version, self.version)
        self.assertTrue(variable.required)

    def test_duplicate_variable_keys_are_rejected(self):
        TemplateVariable.objects.create(
            template_version=self.version,
            key="CLIENT_NAME",
            label="Client Name",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TemplateVariable.objects.create(
                    template_version=self.version,
                    key="CLIENT_NAME",
                    label="Another Client Name",
                )

    def test_clause_is_attached_to_template_version(self):
        clause = TemplateClause.objects.create(
            template_version=self.version,
            key="INTRODUCTION",
            title="Introduction",
            content="Synthetic test clause.",
        )

        self.assertEqual(clause.template_version, self.version)
        self.assertEqual(clause.content, "Synthetic test clause.")

    def test_duplicate_clause_keys_are_rejected(self):
        TemplateClause.objects.create(
            template_version=self.version,
            key="INTRODUCTION",
            content="First synthetic clause.",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TemplateClause.objects.create(
                    template_version=self.version,
                    key="INTRODUCTION",
                    content="Duplicate synthetic clause.",
                )

    def test_generation_records_inputs_and_review_status(self):
        generation = DocumentGeneration.objects.create(
            firm=self.firm,
            template_version=self.version,
            matter=self.matter,
            requested_by=self.user,
            input_data={"client_name": "Test Client"},
        )

        self.assertEqual(generation.firm, self.firm)
        self.assertEqual(generation.matter, self.matter)
        self.assertEqual(generation.status, "draft")
        self.assertEqual(
            generation.review_status,
            "pending_review",
        )
        self.assertEqual(
            generation.input_data["client_name"],
            "Test Client",
        )

    def test_generation_protects_referenced_template_version(self):
        generation = DocumentGeneration.objects.create(
            firm=self.firm,
            template_version=self.version,
            matter=self.matter,
            requested_by=self.user,
        )

        with self.assertRaises(Exception):
            self.version.delete()

        self.assertTrue(
            TemplateVersion.objects.filter(pk=self.version.pk).exists()
        )
        self.assertTrue(
            DocumentGeneration.objects.filter(pk=generation.pk).exists()
        )
# Create your tests here.


from rest_framework import status
from rest_framework.test import APITestCase, APIClient


class TemplateRegistryAPITests(APITestCase):
    def setUp(self):
        self.firm_a = Firm.objects.create(name="Registry API Firm A")
        self.firm_b = Firm.objects.create(name="Registry API Firm B")

        self.user_a = User.objects.create_user(
            email="registry-a@example.com",
            password="test-password-123",
            firm=self.firm_a,
        )
        self.user_b = User.objects.create_user(
            email="registry-b@example.com",
            password="test-password-123",
            firm=self.firm_b,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user_a)

        self.system_template = Template.objects.create(
            name="System Plaint",
            slug="system-plaint",
            category="LITIGATION",
            document_type="Plaint",
            owner_firm=None,
            is_system_template=True,
            is_active=True,
        )

        self.private_a = Template.objects.create(
            name="Firm A Lease",
            slug="firm-a-lease",
            category="PROPERTY",
            document_type="Lease Agreement",
            owner_firm=self.firm_a,
            is_system_template=False,
            created_by=self.user_a,
        )

        self.private_b = Template.objects.create(
            name="Firm B Defence",
            slug="firm-b-defence",
            category="LITIGATION",
            document_type="Defence",
            owner_firm=self.firm_b,
            is_system_template=False,
            created_by=self.user_b,
        )

    def test_list_shows_own_and_active_system_templates_only(self):
        response = self.client.get("/api/v1/templates/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visible_ids = {
            item["id"] for item in response.data["results"]
        }

        self.assertIn(self.system_template.id, visible_ids)
        self.assertIn(self.private_a.id, visible_ids)
        self.assertNotIn(self.private_b.id, visible_ids)

    def test_firm_cannot_retrieve_another_firms_template(self):
        response = self.client.get(
            f"/api/v1/templates/{self.private_b.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_firm_cannot_retrieve_another_firms_template_versions(self):
        response = self.client.get(
            f"/api/v1/templates/{self.private_b.id}/versions/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_firm_cannot_create_system_template_using_api(self):
        response = self.client.post(
            "/api/v1/templates/",
            {
                "name": "Forged System Template",
                "slug": "forged-system-template",
                "category": "LITIGATION",
                "document_type": "Plaint",
                "is_system_template": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(
            Template.objects.filter(
                slug="forged-system-template"
            ).exists()
        )

    def test_created_template_belongs_to_authenticated_firm(self):
        response = self.client.post(
            "/api/v1/templates/",
            {
                "name": "Firm A Demand Letter",
                "slug": "firm-a-demand-letter",
                "category": "CORRESPONDENCE",
                "document_type": "Demand Letter",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        template = Template.objects.get(
            slug="firm-a-demand-letter"
        )
        self.assertEqual(template.owner_firm, self.firm_a)
        self.assertFalse(template.is_system_template)
        self.assertEqual(template.created_by, self.user_a)

    def test_firm_cannot_create_version_of_system_template(self):
        response = self.client.post(
            f"/api/v1/templates/{self.system_template.id}/versions/",
            {"change_summary": "Attempted change"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.system_template.versions.count(), 0)

    def test_new_firm_template_versions_are_sequential_drafts(self):
        url = f"/api/v1/templates/{self.private_a.id}/versions/"

        first = self.client.post(
            url,
            {"change_summary": "Initial draft"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["version_number"], 1)
        self.assertEqual(first.data["status"], "draft")

        second = self.client.post(
            url,
            {"change_summary": "Second draft"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data["version_number"], 2)
        self.assertEqual(second.data["status"], "draft")

    def test_unauthenticated_user_cannot_list_templates(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/templates/")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
