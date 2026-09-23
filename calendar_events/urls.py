from django.urls import path
from . import views

urlpatterns = [
    path('events/',           views.event_list,       name='event-list'),
    path('events/<int:pk>/',  views.event_detail,     name='event-detail'),
    path('sync/jicms/',       views.jicms_sync,       name='jicms-sync'),
    path('upcoming/',         views.upcoming_summary, name='upcoming-summary'),
]