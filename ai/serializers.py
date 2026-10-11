from rest_framework import serializers


class LegalResearchSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=5000,
        allow_blank=False,
    )

    matter_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    def validate_question(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Research question cannot be blank."
            )

        return value