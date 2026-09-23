from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import TimeEntry, Invoice, MpesaPayment, TrustAccount

User = get_user_model()


def validate_positive_kes(value, field_name='amount'):
    if value <= 0:
        raise serializers.ValidationError(
            f'{field_name} must be a positive integer in KES cents (e.g. 50000 = KES 500.00).'
        )
    return value


class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    class Meta:
        model  = User
        fields = ['id', 'first_name', 'last_name', 'full_name']
    def get_full_name(self, obj):
        return obj.get_full_name()


class MatterMinimalSerializer(serializers.Serializer):
    id        = serializers.IntegerField()
    reference = serializers.CharField()
    title     = serializers.CharField()


# ─── Time Entry ───────────────────────────────────────────────────────────────

class TimeEntrySerializer(serializers.ModelSerializer):
    attorney   = UserMinimalSerializer(read_only=True)
    matter     = MatterMinimalSerializer(read_only=True)
    amount_kes = serializers.IntegerField(read_only=True)

    class Meta:
        model  = TimeEntry
        fields = [
            'id', 'matter', 'attorney', 'description', 'date',
            'hours', 'rate_kes', 'amount_kes', 'is_billed', 'created_at',
        ]


class TimeEntryWriteSerializer(serializers.ModelSerializer):
    matter_id = serializers.IntegerField()

    class Meta:
        model  = TimeEntry
        fields = ['matter_id', 'description', 'date', 'hours', 'rate_kes']

    def validate_matter_id(self, value):
        from matters.models import Matter
        firm = self.context['request'].user.firm
        try:
            return Matter.objects.get(pk=value, firm=firm)
        except Matter.DoesNotExist:
            raise serializers.ValidationError('Matter not found in your firm.')

    def validate_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError('Hours must be greater than zero.')
        if value > 24:
            raise serializers.ValidationError('Hours cannot exceed 24 per entry.')
        return value

    def validate_rate_kes(self, value):
        return validate_positive_kes(value, 'Rate')

    def create(self, validated_data):
        matter = validated_data.pop('matter_id')
        return TimeEntry.objects.create(
            matter=matter,
            attorney=self.context['request'].user,
            **validated_data
        )


# ─── Invoice ──────────────────────────────────────────────────────────────────

class InvoiceSerializer(serializers.ModelSerializer):
    matter     = MatterMinimalSerializer(read_only=True)
    created_by = UserMinimalSerializer(read_only=True)
    total_kes  = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'matter', 'amount_kes',
            'vat_kes', 'total_kes', 'issued_date', 'due_date',
            'notes', 'created_by', 'created_at',
        ]


class InvoiceWriteSerializer(serializers.ModelSerializer):
    matter_id = serializers.IntegerField()

    class Meta:
        model  = Invoice
        fields = [
            'matter_id', 'amount_kes', 'vat_kes',
            'issued_date', 'due_date', 'notes',
        ]

    def validate_matter_id(self, value):
        from matters.models import Matter
        firm = self.context['request'].user.firm
        try:
            return Matter.objects.get(pk=value, firm=firm)
        except Matter.DoesNotExist:
            raise serializers.ValidationError('Matter not found in your firm.')

    def validate_amount_kes(self, value):
        return validate_positive_kes(value, 'Amount')

    def validate_vat_kes(self, value):
        if value < 0:
            raise serializers.ValidationError('VAT cannot be negative.')
        return value

    def validate(self, data):
        issued = data.get('issued_date')
        due    = data.get('due_date')
        if issued and due and due < issued:
            raise serializers.ValidationError(
                {'due_date': 'Due date cannot be before issued date.'}
            )
        return data

    def create(self, validated_data):
        matter = validated_data.pop('matter_id')
        return Invoice.objects.create(
            matter=matter,
            firm=self.context['request'].user.firm,
            created_by=self.context['request'].user,
            **validated_data
        )


class InvoiceStatusSerializer(serializers.ModelSerializer):
    """PATCH status only — used by send and cancel actions."""
    class Meta:
        model  = Invoice
        fields = ['status']

    def validate_status(self, value):
        instance = self.instance
        # Paid invoices cannot be cancelled directly
        if instance and instance.status == Invoice.Status.PAID and value == Invoice.Status.CANCELLED:
            raise serializers.ValidationError(
                'Paid invoices cannot be cancelled. Create a credit note instead.'
            )
        return value


# ─── M-Pesa ───────────────────────────────────────────────────────────────────

class MpesaSTKPushSerializer(serializers.Serializer):
    """POST /api/v1/billing/mpesa/stk-push/"""
    invoice_id   = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=15)

    def validate_invoice_id(self, value):
        firm = self.context['request'].user.firm
        try:
            invoice = Invoice.objects.get(pk=value, firm=firm)
        except Invoice.DoesNotExist:
            raise serializers.ValidationError('Invoice not found in your firm.')
        if invoice.status == Invoice.Status.PAID:
            raise serializers.ValidationError('This invoice is already paid.')
        if invoice.status == Invoice.Status.CANCELLED:
            raise serializers.ValidationError('Cannot pay a cancelled invoice.')
        return invoice

    def validate_phone_number(self, value):
        # Strip spaces and leading +
        phone = value.strip().replace(' ', '').replace('+', '')
        # Must be 12 digits starting with 254
        if not phone.startswith('254') or not phone.isdigit() or len(phone) != 12:
            raise serializers.ValidationError(
                'Phone number must be in format 2547XXXXXXXX (12 digits, no + prefix).'
            )
        return phone


class MpesaPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MpesaPayment
        fields = [
            'id', 'invoice', 'phone_number', 'amount_kes',
            'checkout_request_id', 'mpesa_receipt_number',
            'status', 'result_description', 'initiated_at', 'confirmed_at',
        ]


# ─── Trust Account ────────────────────────────────────────────────────────────

class TrustAccountSerializer(serializers.ModelSerializer):
    matter      = MatterMinimalSerializer(read_only=True)
    recorded_by = UserMinimalSerializer(read_only=True)

    class Meta:
        model  = TrustAccount
        fields = [
            'id', 'matter', 'entry_type', 'amount_kes', 'description',
            'date', 'reference', 'recorded_by', 'created_at',
        ]


class TrustAccountWriteSerializer(serializers.ModelSerializer):
    matter_id = serializers.IntegerField()

    class Meta:
        model  = TrustAccount
        fields = ['matter_id', 'entry_type', 'amount_kes', 'description', 'date', 'reference']

    def validate_matter_id(self, value):
        from matters.models import Matter
        firm = self.context['request'].user.firm
        try:
            return Matter.objects.get(pk=value, firm=firm)
        except Matter.DoesNotExist:
            raise serializers.ValidationError('Matter not found in your firm.')

    def validate_amount_kes(self, value):
        return validate_positive_kes(value, 'Amount')

    def validate(self, data):
        """
        For withdrawals, ensure the trust balance for this matter
        is sufficient. Cap 16 compliance — no negative trust balance.
        """
        if data.get('entry_type') == TrustAccount.EntryType.WITHDRAWAL:
            matter = data.get('matter_id')
            if matter:
                from django.db.models import Sum
                entries  = TrustAccount.objects.filter(matter=matter)
                deposits = entries.filter(
                    entry_type=TrustAccount.EntryType.DEPOSIT
                ).aggregate(total=Sum('amount_kes'))['total'] or 0
                withdrawals = entries.filter(
                    entry_type=TrustAccount.EntryType.WITHDRAWAL
                ).aggregate(total=Sum('amount_kes'))['total'] or 0
                balance = deposits - withdrawals
                if data.get('amount_kes', 0) > balance:
                    raise serializers.ValidationError({
                        'amount_kes': (
                            f'Insufficient trust balance. '
                            f'Available: KES {balance/100:.2f}'
                        )
                    })
        return data

    def create(self, validated_data):
        matter = validated_data.pop('matter_id')
        return TrustAccount.objects.create(
            matter=matter,
            firm=self.context['request'].user.firm,
            recorded_by=self.context['request'].user,
            **validated_data
        )