from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Document, DocumentVersion

User = get_user_model()

ALLOWED_MIME_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'image/jpeg',
    'image/png',
]

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


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


class DocumentVersionSerializer(serializers.ModelSerializer):
    uploaded_by  = UserMinimalSerializer(read_only=True)
    file_size_kb = serializers.SerializerMethodField()

    class Meta:
        model  = DocumentVersion
        fields = [
            'id', 'version_number', 'file_name', 'file_size',
            'file_size_kb', 'mime_type', 'change_note',
            'uploaded_by', 'uploaded_at',
        ]

    def get_file_size_kb(self, obj):
        return round(obj.file_size / 1024, 1)


class DocumentSerializer(serializers.ModelSerializer):
    matter         = MatterMinimalSerializer(read_only=True)
    uploaded_by    = UserMinimalSerializer(read_only=True)
    latest_version = DocumentVersionSerializer(read_only=True)
    version_count  = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Document
        fields = [
            'id', 'title', 'doc_type', 'description', 'tags',
            'matter', 'uploaded_by', 'latest_version',
            'version_count', 'created_at', 'updated_at',
        ]


class DocumentCreateSerializer(serializers.Serializer):
    """
    Handles the initial document upload —
    creates both Document and first DocumentVersion.
    """
    matter_id   = serializers.IntegerField()
    title       = serializers.CharField(max_length=500)
    doc_type    = serializers.ChoiceField(
                    choices=Document.DocType.choices,
                    default=Document.DocType.OTHER
                  )
    description = serializers.CharField(required=False, allow_blank=True)
    tags        = serializers.CharField(required=False, allow_blank=True)
    file        = serializers.FileField()
    change_note = serializers.CharField(
                    required=False, allow_blank=True,
                    default='Initial upload'
                  )

    def validate_matter_id(self, value):
        from matters.models import Matter
        firm = self.context['request'].user.firm
        try:
            return Matter.objects.get(pk=value, firm=firm)
        except Matter.DoesNotExist:
            raise serializers.ValidationError(
                'Matter not found in your firm.'
            )

    def validate_file(self, file):
        if file.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB.'
            )
        mime = getattr(file, 'content_type', '')
        if mime and mime not in ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(
                f'File type not allowed. Allowed types: PDF, Word, TXT, JPEG, PNG.'
            )
        return file

    def create(self, validated_data):
        matter      = validated_data.pop('matter_id')
        file        = validated_data.pop('file')
        change_note = validated_data.pop('change_note', 'Initial upload')
        user        = self.context['request'].user

        document = Document.objects.create(
            firm=user.firm,
            matter=matter,
            uploaded_by=user,
            **validated_data
        )

        DocumentVersion.objects.create(
            document=document,
            version_number=1,
            file=file,
            file_name=file.name,
            file_size=file.size,
            mime_type=getattr(file, 'content_type', ''),
            change_note=change_note,
            uploaded_by=user,
        )

        return document


class DocumentUpdateSerializer(serializers.ModelSerializer):
    """PATCH metadata only — title, type, description, tags."""
    class Meta:
        model  = Document
        fields = ['title', 'doc_type', 'description', 'tags']


class DocumentVersionUploadSerializer(serializers.Serializer):
    """Upload a new version of an existing document."""
    file        = serializers.FileField()
    change_note = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, file):
        if file.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB.'
            )
        return file

    def create(self, validated_data):
        document    = self.context['document']
        user        = self.context['request'].user
        file        = validated_data['file']
        change_note = validated_data.get('change_note', '')

        next_version = (document.versions.count() or 0) + 1

        return DocumentVersion.objects.create(
            document=document,
            version_number=next_version,
            file=file,
            file_name=file.name,
            file_size=file.size,
            mime_type=getattr(file, 'content_type', ''),
            change_note=change_note,
            uploaded_by=user,
        )
