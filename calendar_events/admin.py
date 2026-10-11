from django.contrib import admin
from .models import CourtEvent


@admin.register(CourtEvent)
class CourtEventAdmin(admin.ModelAdmin):
    list_display  = ['title', 'event_type', 'date', 'start_time', 'matter', 'firm', 'status', 'source']
    list_filter   = ['event_type', 'status', 'source', 'firm']
    search_fields = ['title', 'court', 'judge', 'jicms_id']
    date_hierarchy= 'date'
    ordering      = ['date', 'start_time']

# Register your models here.
