from datetime import date, timedelta
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Firm, User
from matters.models import Client, Matter
from .models import TimeEntry, Invoice, MpesaPayment, TrustAccount


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
    import uuid
    client = Client.objects.create(
        firm=firm, name=f'Client-{uuid.uuid4().hex[:6]}', created_by=user
    )
    return Matter.objects.create(
        firm=firm, title='Test Matter',
        client=client, practice_area='litigation', created_by=user,
    )


class TimeEntryTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)

    def test_create_time_entry(self):
        res = self.api.post('/api/v1/billing/time-entries/', {
            'matter_id':   self.matter.id,
            'description': 'Drafted motion to compel',
            'date':        date.today().isoformat(),
            'hours':       '2.50',
            'rate_kes':    1500000,   # KES 15,000/hr
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['hours'], '2.50')
        self.assertEqual(res.data['rate_kes'], 1500000)

    def test_zero_hours_rejected(self):
        res = self.api.post('/api/v1/billing/time-entries/', {
            'matter_id': self.matter.id, 'description': 'Test',
            'date': date.today().isoformat(), 'hours': '0', 'rate_kes': 100000,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_rate_rejected(self):
        res = self.api.post('/api/v1/billing/time-entries/', {
            'matter_id': self.matter.id, 'description': 'Test',
            'date': date.today().isoformat(), 'hours': '1', 'rate_kes': -100,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_time_entries(self):
        TimeEntry.objects.create(
            matter=self.matter, attorney=self.user,
            description='Research', date=date.today(),
            hours=1, rate_kes=100000,
        )
        res = self.api.get('/api/v1/billing/time-entries/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)

    def test_filter_unbilled(self):
        TimeEntry.objects.create(
            matter=self.matter, attorney=self.user,
            description='Unbilled', date=date.today(),
            hours=1, rate_kes=100000, is_billed=False,
        )
        TimeEntry.objects.create(
            matter=self.matter, attorney=self.user,
            description='Billed', date=date.today(),
            hours=1, rate_kes=100000, is_billed=True,
        )
        res = self.api.get('/api/v1/billing/time-entries/?unbilled=true')
        self.assertEqual(res.data['count'], 1)

    def test_cannot_edit_billed_entry(self):
        entry = TimeEntry.objects.create(
            matter=self.matter, attorney=self.user,
            description='Billed work', date=date.today(),
            hours=1, rate_kes=100000, is_billed=True,
        )
        res = self.api.patch(
            f'/api/v1/billing/time-entries/{entry.id}/',
            {'hours': '2'}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['code'], 'ERR_ALREADY_BILLED')


class InvoiceTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)
        self.today  = date.today().isoformat()
        self.future = (date.today() + timedelta(days=30)).isoformat()

    def _create_invoice(self, overrides=None):
        payload = {
            'matter_id':   self.matter.id,
            'amount_kes':  7500000,    # KES 75,000.00
            'vat_kes':     1200000,    # KES 12,000.00
            'issued_date': self.today,
            'due_date':    self.future,
            'notes':       'Professional fees — August 2026',
        }
        if overrides:
            payload.update(overrides)
        return self.api.post('/api/v1/billing/invoices/', payload, format='json')

    def test_create_invoice_auto_number(self):
        res = self._create_invoice()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['invoice_number'].startswith('INV/'))
        self.assertEqual(res.data['status'], 'draft')
        self.assertEqual(res.data['total_kes'], 8700000)   # 75000 + 12000 (KES cents)

    def test_invoice_numbers_sequential(self):
        res1 = self._create_invoice()
        res2 = self._create_invoice()
        self.assertEqual(res1.data['invoice_number'].split('/')[-1], '001')
        self.assertEqual(res2.data['invoice_number'].split('/')[-1], '002')

    def test_due_date_before_issued_date_rejected(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        res = self._create_invoice({'due_date': yesterday})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_amount_rejected(self):
        res = self._create_invoice({'amount_kes': 0})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_invoice(self):
        res = self._create_invoice()
        invoice_id = res.data['id']
        send_res = self.api.post(f'/api/v1/billing/invoices/{invoice_id}/send/')
        self.assertEqual(send_res.status_code, status.HTTP_200_OK)
        self.assertEqual(send_res.data['status'], 'sent')

    def test_send_already_sent_invoice_blocked(self):
        res = self._create_invoice()
        invoice_id = res.data['id']
        self.api.post(f'/api/v1/billing/invoices/{invoice_id}/send/')
        res2 = self.api.post(f'/api/v1/billing/invoices/{invoice_id}/send/')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res2.data['code'], 'ERR_NOT_DRAFT')

    def test_delete_paid_invoice_blocked(self):
        res = self._create_invoice()
        invoice = Invoice.objects.get(id=res.data['id'])
        invoice.status = Invoice.Status.PAID
        invoice.save()
        del_res = self.api.delete(f'/api/v1/billing/invoices/{invoice.id}/')
        self.assertEqual(del_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(del_res.data['code'], 'ERR_INVOICE_PAID')

    def test_list_invoices_filter_by_status(self):
        self._create_invoice()
        self._create_invoice()
        Invoice.objects.filter(firm=self.firm).first().delete()
        res = self.api.get('/api/v1/billing/invoices/?status=draft')
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class MpesaTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)
        self.invoice = Invoice.objects.create(
            firm=self.firm, matter=self.matter,
            amount_kes=5000000, vat_kes=800000,
            issued_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status=Invoice.Status.SENT,
            created_by=self.user,
        )

    def test_stk_push_initiated(self):
        res = self.api.post('/api/v1/billing/mpesa/stk-push/', {
            'invoice_id':   self.invoice.id,
            'phone_number': '254712345678',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('checkout_request_id', res.data)
        self.assertEqual(MpesaPayment.objects.count(), 1)

    def test_invalid_phone_number_rejected(self):
        res = self.api.post('/api/v1/billing/mpesa/stk-push/', {
            'invoice_id':   self.invoice.id,
            'phone_number': '0712345678',   # wrong format
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_paid_invoice_stk_push_rejected(self):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.save()
        res = self.api.post('/api/v1/billing/mpesa/stk-push/', {
            'invoice_id':   self.invoice.id,
            'phone_number': '254712345678',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mpesa_callback_success(self):
        payment = MpesaPayment.objects.create(
            invoice=self.invoice, phone_number='254712345678',
            amount_kes=5800000, checkout_request_id='ws_CO_TEST_12345',
        )
        callback_data = {
            'Body': {
                'stkCallback': {
                    'CheckoutRequestID': 'ws_CO_TEST_12345',
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'MpesaReceiptNumber', 'Value': 'QKJ89XLMNO'},
                            {'Name': 'Amount', 'Value': 58000},
                        ]
                    }
                }
            }
        }
        res = self.api.post(
    '/api/v1/billing/mpesa/callback/',
    data=callback_data,
    format='json'
)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, MpesaPayment.Status.SUCCESS)
        self.assertEqual(payment.mpesa_receipt_number, 'QKJ89XLMNO')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)


class TrustAccountTestCase(TestCase):
    def setUp(self):
        self.firm, self.user = make_firm_and_user()
        self.api    = auth_client(self.user)
        self.matter = make_matter(self.firm, self.user)

    def test_create_deposit(self):
        res = self.api.post('/api/v1/billing/trust/', {
            'matter_id':  self.matter.id,
            'entry_type': 'deposit',
            'amount_kes': 10000000,   # KES 100,000.00
            'description': 'Client retainer received',
            'date':       date.today().isoformat(),
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['entry_type'], 'deposit')

    def test_withdrawal_exceeding_balance_rejected(self):
        # Deposit KES 1,000
        self.api.post('/api/v1/billing/trust/', {
            'matter_id': self.matter.id, 'entry_type': 'deposit',
            'amount_kes': 100000, 'description': 'Deposit',
            'date': date.today().isoformat(),
        }, format='json')
        # Try to withdraw KES 2,000 — should fail
        res = self.api.post('/api/v1/billing/trust/', {
            'matter_id': self.matter.id, 'entry_type': 'withdrawal',
            'amount_kes': 200000, 'description': 'Withdrawal',
            'date': date.today().isoformat(),
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient trust balance', str(res.data))

    def test_trust_balance_in_list_response(self):
        self.api.post('/api/v1/billing/trust/', {
            'matter_id': self.matter.id, 'entry_type': 'deposit',
            'amount_kes': 500000, 'description': 'Deposit',
            'date': date.today().isoformat(),
        }, format='json')
        self.api.post('/api/v1/billing/trust/', {
            'matter_id': self.matter.id, 'entry_type': 'withdrawal',
            'amount_kes': 200000, 'description': 'Withdrawal',
            'date': date.today().isoformat(),
        }, format='json')
        res = self.api.get('/api/v1/billing/trust/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['balance_kes'], 300000)   # KES 3,000.00

    def test_billing_summary(self):
        res = self.api.get('/api/v1/billing/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('unbilled', res.data)
        self.assertIn('invoices', res.data)
        self.assertIn('trust_balance_kes', res.data)

# Create your tests here.
