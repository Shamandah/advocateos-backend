from django.db import models
from django.conf import settings
from django.db import models


class Template(models.Model):
    """
    Represents a logical document template.

    A Template is the document type itself, while TemplateVersion
    represents a specific approved/revised version of that template.
    """

    CATEGORY_CHOICES = [
        ("LITIGATION", "Litigation"),
        ("APPLICATION", "Application"),
        ("AFFIDAVIT", "Affidavit"),
        ("COURT_PREPARATION", "Court Preparation"),
        ("COMMERCIAL", "Commercial"),
        ("PROPERTY", "Property"),
        ("CORPORATE", "Corporate"),
        ("CORRESPONDENCE", "Correspondence"),
        ("INTERNAL", "Internal"),
        ("OTHER", "Other"),
    ]

    id = models.BigAutoField(primary_key=True)

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
    )

    document_type = models.CharField(
        max_length=100,
        help_text="Specific document type, e.g. Plaint, Lease Agreement, Demand Letter.",
    )

    practice_area = models.CharField(
        max_length=100,
        blank=True,
    )

    jurisdiction = models.CharField(
        max_length=100,
        default="Kenya",
    )

    description = models.TextField(
        blank=True,
    )

    # Null means this is a system-wide template.
    owner_firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="document_templates",
    )

    is_system_template = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_document_templates",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner_firm", "slug"],
                name="unique_template_slug_per_firm",
            ),
        ]

    def __str__(self):
        return self.name


class TemplateVersion(models.Model):
    """
    A specific version of a Template.

    Only approved versions should be used for production generation.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("review", "Review"),
        ("approved", "Approved"),
        ("archived", "Archived"),
    ]

    RENDERER_CHOICES = [
        ("docx", "DOCX"),
    ]

    id = models.BigAutoField(primary_key=True)

    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    version_number = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    renderer = models.CharField(
        max_length=20,
        choices=RENDERER_CHOICES,
        default="docx",
    )

    # Original lawyer-provided/reference document.
    source_file = models.FileField(
        upload_to="template_sources/",
        null=True,
        blank=True,
    )

    # Structured/renderable template used by the generation engine.
    template_file = models.FileField(
        upload_to="template_files/",
        null=True,
        blank=True,
    )

    source_checksum = models.CharField(
        max_length=64,
        blank=True,
    )

    effective_from = models.DateField(
        null=True,
        blank=True,
    )

    effective_to = models.DateField(
        null=True,
        blank=True,
    )

    change_summary = models.TextField(
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_template_versions",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_template_versions",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["template", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version_number"],
                name="unique_template_version_number",
            ),
        ]

    def __str__(self):
        return f"{self.template.name} v{self.version_number}"


class TemplateVariable(models.Model):
    """
    Defines a value required by a TemplateVersion.
    """

    DATA_TYPE_CHOICES = [
        ("text", "Text"),
        ("long_text", "Long Text"),
        ("integer", "Integer"),
        ("decimal", "Decimal"),
        ("date", "Date"),
        ("boolean", "Boolean"),
        ("choice", "Choice"),
        ("party", "Party"),
        ("address", "Address"),
        ("money", "Money"),
        ("percentage", "Percentage"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("manual", "Manual"),
        ("matter", "Matter"),
        ("client", "Client"),
        ("user", "User"),
        ("firm", "Firm"),
        ("system", "System"),
    ]

    id = models.BigAutoField(primary_key=True)

    template_version = models.ForeignKey(
        TemplateVersion,
        on_delete=models.CASCADE,
        related_name="variables",
    )

    key = models.CharField(
        max_length=100,
    )

    label = models.CharField(
        max_length=255,
    )

    data_type = models.CharField(
        max_length=30,
        choices=DATA_TYPE_CHOICES,
        default="text",
    )

    required = models.BooleanField(
        default=False,
    )

    default_value = models.TextField(
        blank=True,
    )

    help_text = models.TextField(
        blank=True,
    )

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default="manual",
    )

    # Example:
    # client.name
    # matter.reference
    # matter.cause_number
    # firm.name
    source_path = models.CharField(
        max_length=255,
        blank=True,
    )

    validation_rules = models.JSONField(
        default=dict,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template_version", "key"],
                name="unique_template_variable_key",
            ),
        ]

    def __str__(self):
        return f"{self.template_version} - {self.key}"


class TemplateClause(models.Model):
    """
    A clause/section belonging to a particular TemplateVersion.

    We intentionally keep clauses version-specific for v1.
    A global clause library can be introduced later once real
    lawyer-provided documents reveal recurring clauses.
    """

    CLAUSE_TYPE_CHOICES = [
        ("heading", "Heading"),
        ("paragraph", "Paragraph"),
        ("party", "Party Section"),
        ("statement", "Statement"),
        ("terms", "Terms"),
        ("prayer", "Prayer"),
        ("signature", "Signature"),
        ("schedule", "Schedule"),
        ("other", "Other"),
    ]

    id = models.BigAutoField(primary_key=True)

    template_version = models.ForeignKey(
        TemplateVersion,
        on_delete=models.CASCADE,
        related_name="clauses",
    )

    key = models.CharField(
        max_length=100,
    )

    title = models.CharField(
        max_length=255,
        blank=True,
    )

    clause_type = models.CharField(
        max_length=30,
        choices=CLAUSE_TYPE_CHOICES,
        default="paragraph",
    )

    content = models.TextField()

    required = models.BooleanField(
        default=True,
    )

    # Declarative rules only. Never execute this as Python.
    condition = models.JSONField(
        default=dict,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template_version", "key"],
                name="unique_template_clause_key",
            ),
        ]

    def __str__(self):
        return f"{self.template_version} - {self.key}"


class DocumentGeneration(models.Model):
    """
    Records one attempt to generate a document from a TemplateVersion.

    A new generation record is created for every generation attempt.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("validating", "Validating"),
        ("rendering", "Rendering"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    REVIEW_STATUS_CHOICES = [
        ("pending_review", "Pending Review"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    id = models.BigAutoField(primary_key=True)

    firm = models.ForeignKey(
        "accounts.Firm",
        on_delete=models.CASCADE,
        related_name="document_generations",
    )

    template_version = models.ForeignKey(
        TemplateVersion,
        on_delete=models.PROTECT,
        related_name="generations",
    )

    matter = models.ForeignKey(
        "matters.Matter",
        on_delete=models.PROTECT,
        related_name="document_generations",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_generations",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default="pending_review",
    )

    # Snapshot of the exact data used during generation.
    input_data = models.JSONField(
        default=dict,
        blank=True,
    )

    output_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generations",
    )

    error_message = models.TextField(
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Generation #{self.id} - {self.template_version}"
# Create your models here.
