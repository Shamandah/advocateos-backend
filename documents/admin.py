from django.contrib import admin
from .models import Document, DocumentVersion


class DocumentVersionInline(admin.TabularInline):
    model         = DocumentVersion
    extra         = 0
    fields        = ['version_number', 'file_name', 'file_size', 'mime_type', 'change_note', 'uploaded_by', 'uploaded_at']
    readonly_fields = ['version_number', 'file_size', 'uploaded_at']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display  = ['title', 'doc_type', 'matter', 'firm', 'version_count', 'uploaded_by', 'created_at']
    list_filter   = ['doc_type', 'firm']
    search_fields = ['title', 'description', 'tags']
    readonly_fields = ['created_at', 'updated_at']
    inlines       = [DocumentVersionInline]