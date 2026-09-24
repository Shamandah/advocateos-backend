from django.db import models
from django.conf import settings


# AFTER
def document_upload_path(instance, filename):
    return f'documents/firm_{instance.document.matter.firm_id}/matter_{instance.document.matter_id}/{filename}'

class Document(models.Model):
    """
    A document attached to a matter.
    The document record holds metadata — actual file is in DocumentVersion.
    """
    class DocType(models.TextChoices):
        PLEADING      = 'pleading',      'Pleading'
        AFFIDAVIT     = 'affidavit',     'Affidavit'
        CONTRACT      = 'contract',      'Contract'
        CORRESPONDENCE= 'correspondence','Correspondence'
        COURT_ORDER   = 'court_order',   'Court Order'
        EVIDENCE      = 'evidence',      'Evidence'
        OPINION       = 'opinion',       'Legal Opinion'
        TEMPLATE      = 'template',      'Template'
        OTHER         = 'other',         'Other'

    firm        = models.ForeignKey(
                    'accounts.Firm', on_delete=models.CASCADE,
                    related_name='documents'
                  )
    matter      = models.ForeignKey(
                    'matters.Matter', on_delete=models.CASCADE,
                    related_name='documents'
                  )
    title       = models.CharField(max_length=500)
    doc_type    = models.CharField(
                    max_length=20, choices=DocType.choices,
                    default=DocType.OTHER
                  )
    description = models.TextField(blank=True)
    tags        = models.CharField(max_length=500, blank=True)  # comma-separated

    # Audit
    uploaded_by = models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                    null=True, related_name='uploaded_documents'
                  )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title} — {self.matter.reference}'

    @property
    def latest_version(self):
        return self.versions.order_by('-version_number').first()

    @property
    def version_count(self):
        return self.versions.count()

    class Meta:
        ordering = ['-created_at']


class DocumentVersion(models.Model):
    """
    A specific version of a document.
    Versions are immutable — never delete or overwrite a version.
    """
    document       = models.ForeignKey(
                       Document, on_delete=models.CASCADE,
                       related_name='versions'
                     )
    version_number = models.PositiveIntegerField(default=1)
    file           = models.FileField(upload_to=document_upload_path)
    file_name      = models.CharField(max_length=255)
    file_size      = models.PositiveIntegerField()    # bytes
    mime_type      = models.CharField(max_length=100, blank=True)
    change_note    = models.CharField(max_length=500, blank=True)
    uploaded_by    = models.ForeignKey(
                       settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='document_versions'
                     )
    uploaded_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.document.title} v{self.version_number}'

    class Meta:
        ordering = ['-version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'version_number'],
                name='unique_version_per_document'
            )
        ]