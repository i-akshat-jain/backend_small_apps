"""Serializers for Sanatan App API."""
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import Shloka, ShlokaExplanation, ReadingType, User, ReadingLog, Favorite, Achievement, UserAchievement, ChatConversation, ChatMessage, UserStreak


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
            'word_by_word',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ExplanationSerializer(serializers.ModelSerializer):
    """Serializer for ShlokaExplanation model with structured fields."""
    
    # Computed field for backward compatibility
    explanation_text = serializers.SerializerMethodField()
    shloka_id = serializers.UUIDField(source='shloka.id', read_only=True)
    
    class Meta:
        model = ShlokaExplanation
        fields = [
            'id',
            'shloka_id',
            # Structured fields
            'summary',
            'detailed_meaning',
            'detailed_explanation',
            'context',
            'why_this_matters',
            'modern_examples',
            'themes',
            'reflection_prompt',
            # Quality tracking
            'quality_score',
            'quality_checked_at',
            'improvement_version',
            # Metadata
            'ai_model_used',
            'generation_prompt',
            # Computed field (backward compatibility)
            'explanation_text',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 
            'shloka_id', 
            'explanation_text',
            'quality_score',
            'quality_checked_at',
            'improvement_version',
            'created_at', 
            'updated_at'
        ]
    
    def get_explanation_text(self, obj):
        """Get computed explanation_text from structured fields."""
        return obj.explanation_text


class ShlokaResponseSerializer(serializers.Serializer):
    """Serializer for complete Shloka response with explanation."""
    shloka = ShlokaSerializer()
    explanation = ExplanationSerializer(allow_null=True, required=False)


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


class ReadingLogSerializer(serializers.ModelSerializer):
    """Serializer for ReadingLog model."""
    
    class Meta:
        model = ReadingLog
        fields = ['id', 'shloka', 'reading_type', 'read_at']
        read_only_fields = ['id', 'read_at']


class ReadingLogCreateSerializer(serializers.Serializer):
    """Serializer for creating a reading log."""
    shloka_id = serializers.UUIDField(required=True)
    reading_type = serializers.ChoiceField(
        choices=ReadingType.choices,
        required=True
    )


class FavoriteSerializer(serializers.ModelSerializer):
    """Serializer for Favorite model."""
    shloka = ShlokaSerializer(read_only=True)
    shloka_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = Favorite
        fields = ['id', 'shloka', 'shloka_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class AchievementSerializer(serializers.ModelSerializer):
    """Serializer for Achievement model."""
    
    class Meta:
        model = Achievement
        fields = ['id', 'code', 'name', 'description', 'icon', 'condition_type', 'condition_value', 'xp_reward']
        read_only_fields = ['id']


class UserAchievementSerializer(serializers.ModelSerializer):
    """Serializer for UserAchievement model."""
    achievement = AchievementSerializer(read_only=True)
    
    class Meta:
        model = UserAchievement
        fields = ['id', 'achievement', 'unlocked_at']
        read_only_fields = ['id', 'unlocked_at']


class UserStreakSerializer(serializers.ModelSerializer):
    """Serializer for UserStreak model."""
    
    class Meta:
        model = UserStreak
        fields = [
            'id',
            'current_streak',
            'longest_streak',
            'streak_freeze_used_this_month',
            'last_streak_date',
            'total_streak_days',
            'streak_freeze_reset_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'current_streak',
            'longest_streak',
            'last_streak_date',
            'total_streak_days',
            'created_at',
            'updated_at',
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model."""
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChatConversationSerializer(serializers.ModelSerializer):
    """Serializer for ChatConversation model."""
    messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatConversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageCreateSerializer(serializers.Serializer):
    """Serializer for creating a chat message."""
    message = serializers.CharField(required=True, max_length=2000)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)


class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for updating user profile."""
    name = serializers.CharField(required=False, max_length=255)
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        """Validate that at least one field is provided and email is unique."""
        if not attrs:
            raise serializers.ValidationError("At least one field (name or email) must be provided.")
        
        # Check email uniqueness if email is being updated
        if 'email' in attrs:
            # Get the user instance from context (set in view)
            user = self.context.get('user')
            if user:
                # Check if email is different and already exists
                if attrs['email'] != user.email:
                    if User.objects.filter(email=attrs['email']).exists():
                        raise serializers.ValidationError({
                            'email': "A user with this email already exists."
                        })
            else:
                # Fallback: check if email exists
                if User.objects.filter(email=attrs['email']).exists():
                    raise serializers.ValidationError({
                        'email': "A user with this email already exists."
                    })
        
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""
    current_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="New password must be at least 8 characters long."
    )

    def validate_new_password(self, value):
        """Validate new password."""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value

