
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Client, Matter, MatterNote

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    class Meta:
        model  = User
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email', 'role']
    def get_full_name(self, obj):
        return obj.get_full_name()


# ─── Client ───────────────────────────────────────────────────────────────────

class ClientSerializer(serializers.ModelSerializer):
    matter_count = serializers.SerializerMethodField()
    created_by   = UserMinimalSerializer(read_only=True)

    class Meta:
        model  = Client
        fields = [
            'id', 'name', 'email', 'phone', 'id_number',
            'address', 'is_company', 'matter_count',
            'created_by', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'created_by', 'matter_count']

    def get_matter_count(self, obj):
        return obj.matters.count()


class ClientWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Client
        fields = ['name', 'email', 'phone', 'id_number', 'address', 'is_company']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Client name cannot be blank.')
        return value.strip()


# ─── Matter ───────────────────────────────────────────────────────────────────

class MatterListSerializer(serializers.ModelSerializer):
    """Lightweight — used in list views and nested references."""
    client        = ClientSerializer(read_only=True)
    lead_attorney = UserMinimalSerializer(read_only=True)

    class Meta:
        model  = Matter
        fields = [
            'id', 'reference', 'title', 'cause_number',
            'status', 'practice_area', 'client', 'lead_attorney',
            'court', 'opened_date', 'updated_at',
        ]


class MatterDetailSerializer(serializers.ModelSerializer):
    """Full detail — used in retrieve, create, update responses."""
    client        = ClientSerializer(read_only=True)
    lead_attorney = UserMinimalSerializer(read_only=True)
    team          = UserMinimalSerializer(many=True, read_only=True)
    created_by    = UserMinimalSerializer(read_only=True)
    notes         = serializers.SerializerMethodField()
    opened_date   = serializers.DateField()          # ← add this line
    closed_date   = serializers.DateField(allow_null=True)  # ← add this line

    class Meta:
        model  = Matter
        fields = [
            'id', 'reference', 'title', 'cause_number',
            'status', 'practice_area', 'description',
            'client', 'lead_attorney', 'team',
            'court', 'judge', 'opened_date', 'closed_date',
            'created_by', 'created_at', 'updated_at',
            'notes',
        ]

    def get_notes(self, obj):
        recent = obj.notes.select_related('author')[:5]
        return MatterNoteSerializer(recent, many=True).data


class MatterWriteSerializer(serializers.ModelSerializer):
    client_id       = serializers.PrimaryKeyRelatedField(
                        queryset=Client.objects.all(), source='client'
                      )
    lead_attorney_id = serializers.PrimaryKeyRelatedField(
                         queryset=User.objects.all(), source='lead_attorney',
                         required=False, allow_null=True
                       )
    team_ids        = serializers.PrimaryKeyRelatedField(
                        queryset=User.objects.all(), source='team',
                        many=True, required=False
                      )

    class Meta:
        model  = Matter
        fields = [
            'title', 'cause_number', 'client_id', 'lead_attorney_id',
            'team_ids', 'practice_area', 'status', 'court',
            'judge', 'description', 'opened_date', 'closed_date',
        ]

    def validate(self, data):
        firm = self.context['request'].user.firm
        # Client must belong to the same firm
        client = data.get('client')
        if client and client.firm != firm:
            raise serializers.ValidationError(
                {'client_id': 'Client does not belong to your firm.'}
            )
        # Lead attorney must belong to the same firm
        lead = data.get('lead_attorney')
        if lead and lead.firm != firm:
            raise serializers.ValidationError(
                {'lead_attorney_id': 'Attorney does not belong to your firm.'}
            )
        # Team members must belong to the same firm
        for member in data.get('team', []):
            if member.firm != firm:
                raise serializers.ValidationError(
                    {'team_ids': f'User {member.email} does not belong to your firm.'}
                )
        return data

    def create(self, validated_data):
        team = validated_data.pop('team', [])
        matter = Matter.objects.create(**validated_data)
        if team:
            matter.team.set(team)
        return matter

    def update(self, instance, validated_data):
        team = validated_data.pop('team', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if team is not None:
            instance.team.set(team)
        return instance


# ─── Matter note ──────────────────────────────────────────────────────────────

class MatterNoteSerializer(serializers.ModelSerializer):
    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model  = MatterNote
        fields = ['id', 'body', 'author', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError('Note body cannot be blank.')
        return value.strip()