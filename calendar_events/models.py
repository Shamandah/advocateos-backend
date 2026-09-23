from django.db import models
from django.conf import settings
from django.utils import timezone


class CourtEvent(models.Model):

    class EventType(models.TextChoices):
        HEARING    = 'hearing',    'Hearing'
        DEADLINE   = 'deadline',   'Deadline'
        DEPOSITION = 'deposition', 'Deposition'
        MEDIATION  = 'mediation',  'Mediation'
        MENTION    = 'mention',    'Mention'
        OTHER      = 'other',      'Other'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        JICMS  = 'jicms',  'JICMS Sync'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        COMPLETED = 'completed', 'Completed'
        ADJOURNED = 'adjourned', 'Adjourned'
        CANCELLED = 'cancelled', 'Cancelled'

    # Core
    firm        = models.ForeignKey(
                    'accounts.Firm', on_delete=models.CASCADE, related_name='events'
                  )
    matter      = models.ForeignKey(
                    'matters.Matter', on_delete=models.CASCADE, related_name='events'
                  )
    title       = models.CharField(max_length=500)
    event_type  = models.CharField(
                    max_length=20, choices=EventType.choices, default=EventType.HEARING
                  )

    # Timing
    date        = models.DateField()
    start_time  = models.TimeField(null=True, blank=True)
    end_time    = models.TimeField(null=True, blank=True)
    all_day     = models.BooleanField(default=False)

    # Location
    court       = models.CharField(max_length=200, blank=True)
    judge       = models.CharField(max_length=200, blank=True)
    location    = models.CharField(max_length=300, blank=True)

    # Assignment
    assigned_to = models.ManyToManyField(
                    settings.AUTH_USER_MODEL,
                    related_name='court_events', blank=True
                  )

    # JICMS sync metadata
    source      = models.CharField(
                    max_length=10, choices=Source.choices, default=Source.MANUAL
                  )
    jicms_id    = models.CharField(
                    max_length=100, unique=True, null=True, blank=True
                  )

    # Status and outcome
    status      = models.CharField(
                    max_length=20, choices=Status.choices, default=Status.SCHEDULED
                  )
    notes       = models.TextField(blank=True)
    outcome     = models.TextField(blank=True)

    # Audit
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                    null=True, related_name='created_events'
                  )

    def __str__(self):
        return f'{self.title} — {self.date}'

    class Meta:
        ordering = ['date', 'start_time']

# Create your models here.
