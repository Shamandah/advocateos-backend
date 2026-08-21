from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Firm, User


class FirmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Firm
        fields = ['id', 'name', 'lsk_number']


class RegisterSerializer(serializers.Serializer):
    firm_name = serializers.CharField(max_length=255)
    lsk_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        email = value.lower().strip()

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        firm_name = validated_data.pop('firm_name')
        lsk_number = validated_data.pop('lsk_number', '')
        password = validated_data.pop('password')

        firm = Firm.objects.create(
            name=firm_name,
            lsk_number=lsk_number,
            phone=validated_data.get('phone', ''),
        )

        user = User.objects.create_user(
            password=password,
            firm=firm,
            role=User.Role.MANAGING_PARTNER,
            **validated_data,
        )

        return user


class RegisterUserSerializer(serializers.ModelSerializer):
    firm = FirmSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'firm',
        ]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        password = attrs['password']

        user = authenticate(
            request=self.context.get('request'),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        attrs['user'] = user
        return attrs


class MeSerializer(serializers.ModelSerializer):
    firm = FirmSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'lsk_number',
            'phone',
            'firm',
        ]