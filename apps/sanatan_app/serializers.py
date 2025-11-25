"""Serializers for Sanatan App API."""
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import Shloka, ShlokaExplanation, ReadingType, User


class ShlokaSerializer(serializers.ModelSerializer):
    """Serializer for Shloka model."""
    
    class Meta:
        model = Shloka
        fields = [
            'id',
            'book_name',
            'chapter_number',
            'verse_number',
            'sanskrit_text',
            'transliteration',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExplanationSerializer(serializers.ModelSerializer):
    """Serializer for ShlokaExplanation model."""
    
    class Meta:
        model = ShlokaExplanation
        fields = [
            'id',
            'shloka_id',
            'explanation_type',
            'explanation_text',
            'ai_model_used',
            'generation_prompt',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'shloka_id', 'created_at', 'updated_at']


class ShlokaResponseSerializer(serializers.Serializer):
    """Serializer for complete Shloka response with explanations."""
    shloka = ShlokaSerializer()
    summary = ExplanationSerializer(allow_null=True, required=False)
    detailed = ExplanationSerializer(allow_null=True, required=False)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (read-only, excludes password)."""
    
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SignupSerializer(serializers.ModelSerializer):
    """Serializer for user signup."""
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message="A user with this email already exists.")]
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Password must be at least 8 characters long."
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Enter the same password as above, for verification."
    )

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'password', 'password_confirm', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'name': {'required': True},
        }

    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "Password fields didn't match."
            })
        return attrs

    def create(self, validated_data):
        """Create a new user with hashed password."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

