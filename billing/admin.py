from django.contrib import admin
from .models import TimeEntry, Invoice, MpesaPayment, TrustAccount


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display  = ['matter', 'attorney', 'date', 'hours', 'rate_kes', 'is_billed']
    list_filter   = ['is_billed', 'date']
    search_fields = ['description', 'matter__reference']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ['invoice_number', 'matter', 'firm', 'status', 'amount_kes', 'total_kes', 'issued_date', 'due_date']
    list_filter   = ['status', 'firm']
    search_fields = ['invoice_number', 'matter__reference']
    readonly_fields = ['invoice_number', 'created_at']


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display  = ['invoice', 'phone_number', 'amount_kes', 'status', 'mpesa_receipt_number', 'initiated_at']
    list_filter   = ['status']
    search_fields = ['phone_number', 'checkout_request_id', 'mpesa_receipt_number']
    readonly_fields = ['checkout_request_id', 'initiated_at']


@admin.register(TrustAccount)
class TrustAccountAdmin(admin.ModelAdmin):
    list_display  = ['matter', 'firm', 'entry_type', 'amount_kes', 'date', 'recorded_by']
    list_filter   = ['entry_type', 'firm']
    search_fields = ['description', 'reference', 'matter__reference']

# Register your models here.
