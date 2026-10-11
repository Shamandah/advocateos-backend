from rest_framework import serializers

from .models import Template, TemplateVersion, TemplateVariable, TemplateClause


class TemplateSerializer(serializers.ModelSerializer):
    version_count = serializers.SerializerMethodField()

    class Meta:
        model = Template
        fields = [
            "id", "name", "slug", "category", "document_type",
            "practice_area", "jurisdiction", "description",
            "is_system_template", "is_active",
            "version_count", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "is_system_template", "is_active",
            "version_count", "created_at", "updated_at",
        ]

    def get_version_count(self, obj):
        return obj.versions.count()


class TemplateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = [
            "id", "name", "slug", "category", "document_type",
            "practice_area", "jurisdiction", "description",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request = self.context["request"]

        forbidden = {
            "owner_firm", "owner_firm_id", "is_system_template",
            "is_active", "created_by", "created_by_id",
        }
        supplied = forbidden.intersection(self.initial_data.keys())

        if supplied:
            raise serializers.ValidationError({
                field: "This field cannot be set through this endpoint."
                for field in sorted(supplied)
            })

        if not getattr(request.user, "firm_id", None):
            raise serializers.ValidationError(
                "Your account must belong to a firm to create templates."
            )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return Template.objects.create(
            **validated_data,
            owner_firm=request.user.firm,
            is_system_template=False,
            created_by=request.user,
        )


class TemplateVersionSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(
        source="template.name", read_only=True
    )

    class Meta:
        model = TemplateVersion
        fields = [
            "id", "template", "template_name", "version_number",
            "status", "renderer", "source_checksum",
            "effective_from", "effective_to", "change_summary",
            "approved_by", "approved_at", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class TemplateVersionCreateSerializer(serializers.Serializer):
    renderer = serializers.ChoiceField(
        choices=TemplateVersion.RENDERER_CHOICES,
        default="docx",
    )
    change_summary = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class TemplateVariableSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateVariable
        fields = [
            "id", "template_version", "key", "label", "data_type",
            "required", "default_value", "help_text", "source_type",
            "source_path", "validation_rules", "display_order",
        ]
        read_only_fields = fields


class TemplateClauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateClause
        fields = [
            "id", "template_version", "key", "title", "clause_type",
            "content", "required", "condition", "display_order", "metadata",
        ]
        read_only_fields = fields
