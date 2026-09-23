from django.db import models
from django.conf import settings
from django.utils import timezone


class TimeEntry(models.Model):
    """Billable time record — attached to a matter."""
    matter      = models.ForeignKey(
                    'matters.Matter', on_delete=models.CASCADE,
                    related_name='time_entries'
                  )
    attorney    = models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                    null=True, related_name='time_entries'
                  )
    description = models.TextField()
    date        = models.DateField()
    hours       = models.DecimalField(max_digits=5, decimal_places=2)
    rate_kes    = models.IntegerField()   # KES cents × 100 per hour
    is_billed   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    @property
    def amount_kes(self):
        """Total amount in KES cents."""
        return int(self.hours * self.rate_kes)

    def __str__(self):
        return f'{self.matter.reference} — {self.hours}hrs @ {self.rate_kes}'

    class Meta:
        ordering = ['-date']


class Invoice(models.Model):

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        SENT      = 'sent',      'Sent'
        PAID      = 'paid',      'Paid'
        OVERDUE   = 'overdue',   'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'

    firm           = models.ForeignKey(
                       'accounts.Firm', on_delete=models.CASCADE,
                       related_name='invoices'
                     )
    matter         = models.ForeignKey(
                       'matters.Matter', on_delete=models.CASCADE,
                       related_name='invoices'
                     )
    invoice_number = models.CharField(max_length=50, blank=True)
    status         = models.CharField(
                       max_length=20, choices=Status.choices,
                       default=Status.DRAFT
                     )
    amount_kes     = models.IntegerField()   # KES cents × 100
    vat_kes        = models.IntegerField(default=0)
    issued_date    = models.DateField()
    due_date       = models.DateField()
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    created_by     = models.ForeignKey(
                       settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                       null=True, related_name='created_invoices'
                     )

    @property
    def total_kes(self):
        return self.amount_kes + self.vat_kes

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    def _generate_invoice_number(self):
        year = timezone.now().year
        last = (
            Invoice.objects
            .filter(firm=self.firm, invoice_number__startswith=f'INV/{year}/')
            .order_by('-invoice_number')
            .first()
        )
        seq = 1
        if last:
            try:
                seq = int(last.invoice_number.split('/')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f'INV/{year}/{seq:03d}'

    def __str__(self):
        return f'{self.invoice_number} — {self.matter.reference}'

    class Meta:
        ordering = ['-issued_date']
        constraints = [
            models.UniqueConstraint(
                fields=['firm', 'invoice_number'],
                name='unique_invoice_number_per_firm'
            )
        ]


class MpesaPayment(models.Model):
    """
    M-Pesa STK push transaction via Daraja API.
    checkout_request_id is the idempotency key from Safaricom.
    Never create duplicate payments for the same checkout_request_id.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED  = 'failed',  'Failed'

    invoice               = models.ForeignKey(
                              Invoice, on_delete=models.CASCADE,
                              related_name='mpesa_payments'
                            )
    phone_number          = models.CharField(max_length=15)   # 2547XXXXXXXX
    amount_kes            = models.IntegerField()              # KES cents × 100
    checkout_request_id   = models.CharField(max_length=100, unique=True)
    mpesa_receipt_number  = models.CharField(max_length=20, blank=True)
    status                = models.CharField(
                              max_length=10, choices=Status.choices,
                              default=Status.PENDING
                            )
    result_description    = models.CharField(max_length=255, blank=True)
    initiated_at          = models.DateTimeField(auto_now_add=True)
    confirmed_at          = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.invoice.invoice_number} — {self.phone_number} — {self.status}'

    class Meta:
        ordering = ['-initiated_at']


class TrustAccount(models.Model):
    """
    Client trust ledger — Cap 16 (Advocates' Accounts Rules) compliant.
    Every deposit and withdrawal must be recorded with full attribution.
    This is a legal requirement — never delete trust entries.
    """
    class EntryType(models.TextChoices):
        DEPOSIT    = 'deposit',    'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'

    firm        = models.ForeignKey(
                    'accounts.Firm', on_delete=models.CASCADE,
                    related_name='trust_entries'
                  )
    matter      = models.ForeignKey(
                    'matters.Matter', on_delete=models.CASCADE,
                    related_name='trust_entries'
                  )
    entry_type  = models.CharField(max_length=15, choices=EntryType.choices)
    amount_kes  = models.IntegerField()   # KES cents × 100
    description = models.TextField()
    date        = models.DateField()
    reference   = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                    null=True, related_name='trust_entries'
                  )
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.entry_type} — {self.matter.reference} — KES {self.amount_kes/100:.2f}'

    class Meta:
        ordering = ['-date', '-created_at']

# Create your models here.
