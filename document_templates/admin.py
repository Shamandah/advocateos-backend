from django.contrib import admin
from django.contrib import admin

from .models import (
    DocumentGeneration,
    Template,
    TemplateClause,
    TemplateVariable,
    TemplateVersion,
)


class TemplateVersionInline(admin.TabularInline):
    model = TemplateVersion
    extra = 0
    fields = (
        "version_number",
        "status",
        "renderer",
        "effective_from",
        "effective_to",
        "approved_by",
        "approved_at",
    )
    readonly_fields = ("approved_at",)


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "document_type",
        "category",
        "practice_area",
        "owner_firm",
        "is_system_template",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "category",
        "is_system_template",
        "is_active",
    )

    search_fields = (
        "name",
        "document_type",
        "slug",
        "practice_area",
        "description",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    inlines = [
        TemplateVersionInline,
    ]


@admin.register(TemplateVersion)
class TemplateVersionAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "version_number",
        "status",
        "renderer",
        "effective_from",
        "effective_to",
        "approved_by",
        "created_at",
    )

    list_filter = (
        "status",
        "renderer",
    )

    search_fields = (
        "template__name",
        "change_summary",
    )

    readonly_fields = (
        "approved_at",
        "created_at",
        "updated_at",
    )


@admin.register(TemplateVariable)
class TemplateVariableAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "label",
        "template_version",
        "data_type",
        "source_type",
        "source_path",
        "required",
        "display_order",
    )

    list_filter = (
        "data_type",
        "source_type",
        "required",
    )

    search_fields = (
        "key",
        "label",
        "template_version__template__name",
    )


@admin.register(TemplateClause)
class TemplateClauseAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "title",
        "template_version",
        "clause_type",
        "required",
        "display_order",
    )

    list_filter = (
        "clause_type",
        "required",
    )

    search_fields = (
        "key",
        "title",
        "content",
        "template_version__template__name",
    )


@admin.register(DocumentGeneration)
class DocumentGenerationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "template_version",
        "matter",
        "firm",
        "requested_by",
        "status",
        "review_status",
        "output_document",
        "created_at",
    )

    list_filter = (
        "status",
        "review_status",
    )

    search_fields = (
        "template_version__template__name",
        "matter__reference",
        "matter__title",
        "requested_by__email",
    )

    readonly_fields = (
        "created_at",
        "started_at",
        "completed_at",
    )
# Register your models here.
