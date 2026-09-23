from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CourtEvent

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email']

    def get_full_name(self, obj):
        return obj.get_full_name()


class MatterMinimalSerializer(serializers.Serializer):
    """Minimal matter shape — avoids circular import with matters app."""
    id        = serializers.IntegerField()
    reference = serializers.CharField()
    title     = serializers.CharField()


class CourtEventReadSerializer(serializers.ModelSerializer):
    """Full detail — returned on GET, POST, PATCH responses."""
    assigned_to = UserMinimalSerializer(many=True, read_only=True)
    created_by  = UserMinimalSerializer(read_only=True)
    matter      = MatterMinimalSerializer(read_only=True)
    date        = serializers.DateField()
    start_time  = serializers.TimeField(allow_null=True)
    end_time    = serializers.TimeField(allow_null=True)

    class Meta:
        model  = CourtEvent
        fields = [
            'id', 'title', 'event_type', 'date', 'start_time', 'end_time',
            'all_day', 'court', 'judge', 'location', 'status', 'source',
            'jicms_id', 'notes', 'outcome', 'matter', 'assigned_to',
            'created_by', 'created_at', 'updated_at',
        ]


class CourtEventWriteSerializer(serializers.ModelSerializer):
    """Write serializer — takes IDs, validates firm ownership."""
    matter_id       = serializers.IntegerField()
    assigned_to_ids = serializers.ListField(
                        child=serializers.IntegerField(),
                        required=False, default=list
                      )
    date            = serializers.DateField()
    start_time      = serializers.TimeField(required=False, allow_null=True)
    end_time        = serializers.TimeField(required=False, allow_null=True)

    class Meta:
        model  = CourtEvent
        fields = [
            'matter_id', 'title', 'event_type', 'date', 'start_time',
            'end_time', 'all_day', 'court', 'judge', 'location',
            'status', 'notes', 'outcome', 'assigned_to_ids',
        ]

    def validate_matter_id(self, value):
        from matters.models import Matter
        firm = self.context['request'].user.firm
        try:
            matter = Matter.objects.get(pk=value, firm=firm)
        except Matter.DoesNotExist:
            raise serializers.ValidationError(
                'Matter not found or does not belong to your firm.'
            )
        return matter

    def validate_assigned_to_ids(self, value):
        if not value:
            return []
        firm  = self.context['request'].user.firm
        users = User.objects.filter(pk__in=value, firm=firm)
        if users.count() != len(value):
            raise serializers.ValidationError(
                'One or more assigned users do not belong to your firm.'
            )
        return list(users)

    def validate(self, data):
        start = data.get('start_time')
        end   = data.get('end_time')
        if start and end and end <= start:
            raise serializers.ValidationError(
                {'end_time': 'End time must be after start time.'}
            )
        if data.get('all_day'):
            data['start_time'] = None
            data['end_time']   = None
        return data

    def create(self, validated_data):
        matter      = validated_data.pop('matter_id')
        assigned_to = validated_data.pop('assigned_to_ids', [])
        event = CourtEvent.objects.create(
            matter=matter,
            firm=self.context['request'].user.firm,
            **validated_data
        )
        if assigned_to:
            event.assigned_to.set(assigned_to)
        return event

    def update(self, instance, validated_data):
        matter      = validated_data.pop('matter_id', None)
        assigned_to = validated_data.pop('assigned_to_ids', None)
        if matter:
            instance.matter = matter
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if assigned_to is not None:
            instance.assigned_to.set(assigned_to)
        return instance