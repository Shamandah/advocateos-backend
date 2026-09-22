"""matters/models.py
Client, Matter, MatterNote — the central hub of AdvocateOS.
Every other module (billing, calendar, documents) has a FK to Matter.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class Client(models.Model):
    firm = models.ForeignKey(
        'accounts.Firm',
        on_delete=models.CASCADE,
        related_name='clients'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    is_company = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_clients'
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Matter(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        ON_HOLD = 'on_hold', 'On Hold'
        CLOSED = 'closed', 'Closed'
        ARCHIVED = 'archived', 'Archived'

    class PracticeArea(models.TextChoices):
        LITIGATION = 'litigation', 'Litigation'
        CONVEYANCING = 'conveyancing', 'Conveyancing'
        CORPORATE = 'corporate', 'Corporate & Commercial'
        EMPLOYMENT = 'employment', 'Employment & Labour'
        FAMILY = 'family', 'Family'
        SUCCESSION = 'succession', 'Succession & Probate'
        CRIMINAL = 'criminal', 'Criminal'
        LAND = 'land', 'Land & Environment'
        IP = 'ip', 'Intellectual Property'
        OTHER = 'other', 'Other'

    firm = models.ForeignKey(
        'accounts.Firm',
        on_delete=models.CASCADE,
        related_name='matters'
    )
    reference = models.CharField(max_length=50, unique=True, blank=True)
    title = models.CharField(max_length=500)
    cause_number = models.CharField(max_length=100, blank=True)

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='matters'
    )
    lead_attorney = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_matters'
    )
    team = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='matters',
        blank=True
    )

    practice_area = models.CharField(
        max_length=30,
        choices=PracticeArea.choices,
        default=PracticeArea.OTHER
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )
    court = models.CharField(max_length=200, blank=True)
    judge = models.CharField(max_length=200, blank=True)

    opened_date = models.DateField(default=timezone.localdate)
    closed_date = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_matters'
    )

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        super().save(*args, **kwargs)

    def _generate_reference(self):
        """Auto-generate reference: ADV/YYYY/NNN scoped per firm."""
        year = timezone.now().year
        last = (
            Matter.objects
            .filter(
                firm=self.firm,
                reference__startswith=f'ADV/{year}/'
            )
            .order_by('-reference')
            .first()
        )

        if last:
            try:
                seq = int(last.reference.split('/')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1

        return f'ADV/{year}/{seq:03d}'

    def __str__(self):
        return f'{self.reference} — {self.title}'

    class Meta:
        ordering = ['-created_at']


class MatterNote(models.Model):
    matter = models.ForeignKey(
        Matter,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='matter_notes'
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Note on {self.matter.reference} by {self.author}'
