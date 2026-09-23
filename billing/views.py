from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TimeEntry, Invoice, MpesaPayment, TrustAccount
from .serializers import (
    TimeEntrySerializer, TimeEntryWriteSerializer,
    InvoiceSerializer, InvoiceWriteSerializer, InvoiceStatusSerializer,
    MpesaSTKPushSerializer, MpesaPaymentSerializer,
    TrustAccountSerializer, TrustAccountWriteSerializer,
)


def paginate(queryset, request, serializer_class):
    try:
        page     = max(1, int(request.query_params.get('page', 1)))
        per_page = 25
    except ValueError:
        page, per_page = 1, 25
    start = (page - 1) * per_page
    end   = start + per_page
    total = queryset.count()
    return {
        'count':    total,
        'page':     page,
        'pages':    (total + per_page - 1) // per_page,
        'next':     page + 1 if end < total else None,
        'previous': page - 1 if page > 1 else None,
        'results':  serializer_class(queryset[start:end], many=True).data,
    }


# ─── Time Entries ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def time_entry_list(request):
    """
    GET  /api/v1/billing/time-entries/
    POST /api/v1/billing/time-entries/
    """
    if request.method == 'GET':
        qs = (
            TimeEntry.objects
            .filter(matter__firm=request.user.firm)
            .select_related('matter', 'attorney')
        )
        if matter_id := request.query_params.get('matter_id'):
            qs = qs.filter(matter_id=matter_id)
        if attorney_id := request.query_params.get('attorney_id'):
            qs = qs.filter(attorney_id=attorney_id)
        if request.query_params.get('unbilled') == 'true':
            qs = qs.filter(is_billed=False)
        return Response(paginate(qs, request, TimeEntrySerializer))

    serializer = TimeEntryWriteSerializer(
        data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    entry = serializer.save()
    return Response(TimeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def time_entry_detail(request, pk):
    entry = get_object_or_404(TimeEntry, pk=pk, matter__firm=request.user.firm)

    if request.method == 'GET':
        return Response(TimeEntrySerializer(entry).data)

    if request.method == 'PATCH':
        if entry.is_billed:
            return Response(
                {'error': True, 'code': 'ERR_ALREADY_BILLED',
                 'detail': 'Billed time entries cannot be edited.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = TimeEntryWriteSerializer(
            entry, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TimeEntrySerializer(entry).data)

    if entry.is_billed:
        return Response(
            {'error': True, 'code': 'ERR_ALREADY_BILLED',
             'detail': 'Billed time entries cannot be deleted.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    entry.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Invoices ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def invoice_list(request):
    """
    GET  /api/v1/billing/invoices/
    POST /api/v1/billing/invoices/
    """
    if request.method == 'GET':
        qs = (
            Invoice.objects
            .filter(firm=request.user.firm)
            .select_related('matter', 'created_by')
        )
        if status_filter := request.query_params.get('status'):
            qs = qs.filter(status=status_filter)
        if matter_id := request.query_params.get('matter_id'):
            qs = qs.filter(matter_id=matter_id)
        return Response(paginate(qs, request, InvoiceSerializer))

    serializer = InvoiceWriteSerializer(
        data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    invoice = serializer.save()
    return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, firm=request.user.firm)

    if request.method == 'GET':
        return Response(InvoiceSerializer(invoice).data)

    if request.method == 'PATCH':
        serializer = InvoiceWriteSerializer(
            invoice, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(InvoiceSerializer(invoice).data)

    if invoice.status == Invoice.Status.PAID:
        return Response(
            {'error': True, 'code': 'ERR_INVOICE_PAID',
             'detail': 'Paid invoices cannot be deleted.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    invoice.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invoice_send(request, pk):
    """
    POST /api/v1/billing/invoices/{id}/send/
    Mark invoice as sent.
    Phase 2: triggers WhatsApp + email notification to client.
    """
    invoice = get_object_or_404(Invoice, pk=pk, firm=request.user.firm)
    if invoice.status != Invoice.Status.DRAFT:
        return Response(
            {'error': True, 'code': 'ERR_NOT_DRAFT',
             'detail': f'Only draft invoices can be sent. Current status: {invoice.status}.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    invoice.status = Invoice.Status.SENT
    invoice.save(update_fields=['status'])
    # TODO (Phase 2): trigger WhatsApp + email notification
    return Response({
        'status':  'sent',
        'sent_at': timezone.now().isoformat(),
        'invoice': InvoiceSerializer(invoice).data,
    })


# ─── M-Pesa ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mpesa_stk_push(request):
    """
    POST /api/v1/billing/mpesa/stk-push/
    Initiate M-Pesa STK push for an invoice.
    Phase 1: returns a sandbox stub response.
    Phase 2 (Dev B): calls MpesaDarajaService.stk_push()
    """
    serializer = MpesaSTKPushSerializer(
        data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)

    invoice      = serializer.validated_data['invoice_id']
    phone_number = serializer.validated_data['phone_number']

    # Phase 1 stub — generates a fake checkout_request_id
    # Phase 2: replace with real Daraja API call
    import uuid
    checkout_request_id = f'ws_CO_stub_{uuid.uuid4().hex[:16].upper()}'

    payment = MpesaPayment.objects.create(
        invoice=invoice,
        phone_number=phone_number,
        amount_kes=invoice.total_kes,
        checkout_request_id=checkout_request_id,
        status=MpesaPayment.Status.PENDING,
    )

    return Response({
        'checkout_request_id': checkout_request_id,
        'message': (
            f'STK push initiated to {phone_number}. '
            'Awaiting customer confirmation on their phone.'
        ),
        'amount_kes': invoice.total_kes,
        'payment_id': payment.id,
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
def mpesa_callback(request):
    """
    POST /api/v1/billing/mpesa/callback/
    Safaricom Daraja callback — no auth required (Safaricom posts here).
    Dev B owns the real implementation in Phase 2.
    This stub acknowledges the callback and updates payment status.
    """
    body = request.data.get('Body', {})
    stk  = body.get('stkCallback', {})

    checkout_request_id = stk.get('CheckoutRequestID')
    result_code         = stk.get('ResultCode')
    result_desc         = stk.get('ResultDesc', '')

    if not checkout_request_id:
        return Response({'ResultCode': 1, 'ResultDesc': 'Missing CheckoutRequestID'})

    try:
        payment = MpesaPayment.objects.get(checkout_request_id=checkout_request_id)
    except MpesaPayment.DoesNotExist:
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    if result_code == 0:
        # Success — extract receipt number from callback metadata
        items = stk.get('CallbackMetadata', {}).get('Item', [])
        receipt = next(
            (i.get('Value') for i in items if i.get('Name') == 'MpesaReceiptNumber'),
            ''
        )
        payment.status               = MpesaPayment.Status.SUCCESS
        payment.mpesa_receipt_number = receipt
        payment.confirmed_at         = timezone.now()
        payment.result_description   = result_desc
        payment.save()

        # Mark invoice as paid
        payment.invoice.status = Invoice.Status.PAID
        payment.invoice.save(update_fields=['status'])
    else:
        payment.status             = MpesaPayment.Status.FAILED
        payment.result_description = result_desc
        payment.save()

    # Safaricom expects this exact response shape
    return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ─── Trust Account ────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trust_list(request):
    """
    GET  /api/v1/billing/trust/
    POST /api/v1/billing/trust/
    Trust entries are immutable once created (Cap 16 compliance).
    """
    if request.method == 'GET':
        qs = (
            TrustAccount.objects
            .filter(firm=request.user.firm)
            .select_related('matter', 'recorded_by')
        )
        if matter_id := request.query_params.get('matter_id'):
            qs = qs.filter(matter_id=matter_id)
        if entry_type := request.query_params.get('entry_type'):
            qs = qs.filter(entry_type=entry_type)

        # Include running balance per matter in summary
        from django.db.models import Sum
        summary = qs.aggregate(
            total_deposits    = Sum('amount_kes', filter=__import__('django.db.models', fromlist=['Q']).Q(entry_type='deposit')),
            total_withdrawals = Sum('amount_kes', filter=__import__('django.db.models', fromlist=['Q']).Q(entry_type='withdrawal')),
        )
        deposits    = summary['total_deposits']    or 0
        withdrawals = summary['total_withdrawals'] or 0

        return Response({
            **paginate(qs, request, TrustAccountSerializer),
            'balance_kes': deposits - withdrawals,
        })

    serializer = TrustAccountWriteSerializer(
        data=request.data, context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    entry = serializer.save()
    return Response(TrustAccountSerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trust_detail(request, pk):
    """
    GET /api/v1/billing/trust/{id}/
    Trust entries are read-only after creation — Cap 16 compliance.
    """
    entry = get_object_or_404(TrustAccount, pk=pk, firm=request.user.firm)
    return Response(TrustAccountSerializer(entry).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def billing_summary(request):
    """
    GET /api/v1/billing/summary/
    Dashboard billing summary — unbilled hours, outstanding invoices, trust balance.
    """
    from django.db.models import Sum
    firm = request.user.firm

    unbilled_entries = TimeEntry.objects.filter(
        matter__firm=firm, is_billed=False
    ).aggregate(
        total_hours  = Sum('hours'),
        total_amount = Sum('rate_kes'),
    )

    invoice_summary = Invoice.objects.filter(firm=firm)

    trust = TrustAccount.objects.filter(firm=firm)
    deposits    = trust.filter(entry_type='deposit').aggregate(t=Sum('amount_kes'))['t'] or 0
    withdrawals = trust.filter(entry_type='withdrawal').aggregate(t=Sum('amount_kes'))['t'] or 0

    return Response({
        'unbilled': {
            'entry_count': TimeEntry.objects.filter(matter__firm=firm, is_billed=False).count(),
        },
        'invoices': {
            'draft':    invoice_summary.filter(status='draft').count(),
            'sent':     invoice_summary.filter(status='sent').count(),
            'overdue':  invoice_summary.filter(status='overdue').count(),
            'paid':     invoice_summary.filter(status='paid').count(),
        },
        'trust_balance_kes': deposits - withdrawals,
    })

# Create your views here.
