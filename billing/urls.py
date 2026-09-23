from django.urls import path
from . import views

urlpatterns = [
    # Time entries
    path('time-entries/',           views.time_entry_list,   name='time-entry-list'),
    path('time-entries/<int:pk>/',  views.time_entry_detail, name='time-entry-detail'),

    # Invoices
    path('invoices/',               views.invoice_list,   name='invoice-list'),
    path('invoices/<int:pk>/',      views.invoice_detail, name='invoice-detail'),
    path('invoices/<int:pk>/send/', views.invoice_send,   name='invoice-send'),

    # M-Pesa
    path('mpesa/stk-push/',         views.mpesa_stk_push, name='mpesa-stk-push'),
    path('mpesa/callback/',         views.mpesa_callback, name='mpesa-callback'),

    # Trust accounting
    path('trust/',                  views.trust_list,   name='trust-list'),
    path('trust/<int:pk>/',         views.trust_detail, name='trust-detail'),

    # Dashboard summary
    path('summary/',                views.billing_summary, name='billing-summary'),
]