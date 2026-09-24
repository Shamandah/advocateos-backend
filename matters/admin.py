from django.contrib import admin
from .models import Client, Matter, MatterNote


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ['name', 'firm', 'email', 'phone', 'is_company', 'created_at']
    list_filter   = ['is_company', 'firm']
    search_fields = ['name', 'email', 'phone', 'id_number']


class MatterNoteInline(admin.TabularInline):
    model  = MatterNote
    extra  = 0
    fields = ['author', 'body', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Matter)
class MatterAdmin(admin.ModelAdmin):
    list_display   = ['reference', 'title', 'firm', 'client', 'status', 'practice_area', 'lead_attorney', 'opened_date']
    list_filter    = ['status', 'practice_area', 'firm']
    search_fields  = ['reference', 'title', 'cause_number']
    readonly_fields= ['reference', 'created_at', 'updated_at']
    inlines        = [MatterNoteInline]

# Register your models here.
