"""Django models for Sanatan App."""
from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.hashers import make_password, check_password
import uuid


class TimestampedModel(models.Model):
    """Abstract base model with timestamp fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ReadingType(models.TextChoices):
    """Reading type choices."""
    SUMMARY = 'summary', 'Summary'
    DETAILED = 'detailed', 'Detailed'


class Shloka(TimestampedModel):
    """Shloka model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book_name = models.TextField()
    chapter_number = models.IntegerField(validators=[MinValueValidator(1)])
    verse_number = models.IntegerField(validators=[MinValueValidator(1)])
    sanskrit_text = models.TextField()
    transliteration = models.TextField(blank=True, null=True)
    word_by_word = models.JSONField(blank=True, null=True, help_text="Word-by-word breakdown as JSON array")

    class Meta:
        db_table = 'shlokas'
        ordering = ['book_name', 'chapter_number', 'verse_number']
        indexes = [
            models.Index(fields=['book_name', 'chapter_number', 'verse_number']),
        ]

    def __str__(self):
        return f"{self.book_name} - Chapter {self.chapter_number}, Verse {self.verse_number}"


class ShlokaExplanation(TimestampedModel):
    """Shloka explanation model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shloka = models.ForeignKey(
        Shloka,
        on_delete=models.CASCADE,
        related_name='explanations'
    )
    explanation_type = models.CharField(
        max_length=20,
        choices=ReadingType.choices
    )
    explanation_text = models.TextField()
    ai_model_used = models.TextField(blank=True, null=True)
    generation_prompt = models.TextField(blank=True, null=True)
    
    # New structured fields for enhanced UI
    why_this_matters = models.TextField(blank=True, null=True, help_text="Modern relevance explanation")
    context = models.TextField(blank=True, null=True, help_text="Context in the dialogue/story")
    modern_examples = models.JSONField(blank=True, null=True, help_text="Modern applications as JSON array")
    themes = models.JSONField(blank=True, null=True, help_text="Key themes as JSON array of strings")
    reflection_prompt = models.TextField(blank=True, null=True, help_text="Question for contemplation")

    class Meta:
        db_table = 'shloka_explanations'
        unique_together = [['shloka', 'explanation_type']]
        indexes = [
            models.Index(fields=['shloka', 'explanation_type']),
        ]

    def __str__(self):
        return f"{self.shloka} - {self.get_explanation_type_display()}"


class User(TimestampedModel):
    """User model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    email = models.EmailField(unique=True, db_index=True)
    password = models.TextField()  # Stored as hashed password
    access_token = models.TextField(blank=True, null=True)  # JWT access token
    refresh_token = models.TextField(blank=True, null=True)  # JWT refresh token
    access_token_expires_at = models.DateTimeField(blank=True, null=True)  # Access token expiration
    refresh_token_expires_at = models.DateTimeField(blank=True, null=True, db_index=True)  # Refresh token expiration

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['refresh_token_expires_at']),
        ]

    def set_password(self, raw_password):
        """Hash and set the password."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Check if the provided password matches the hashed password."""
        return check_password(raw_password, self.password)

    @property
    def is_authenticated(self):
        """Always return True for authenticated users. Required by DRF."""
        return True

    @property
    def is_anonymous(self):
        """Always return False for authenticated users. Required by DRF."""
        return False

    def update_tokens(self, access_token, refresh_token, access_token_expires_at, refresh_token_expires_at):
        """Update user's access and refresh tokens."""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.access_token_expires_at = access_token_expires_at
        self.refresh_token_expires_at = refresh_token_expires_at
        self.save(update_fields=['access_token', 'refresh_token', 'access_token_expires_at', 'refresh_token_expires_at', 'updated_at'])

    def clear_tokens(self):
        """Clear user's tokens (for logout)."""
        self.access_token = None
        self.refresh_token = None
        self.access_token_expires_at = None
        self.refresh_token_expires_at = None
        self.save(update_fields=['access_token', 'refresh_token', 'access_token_expires_at', 'refresh_token_expires_at', 'updated_at'])

    def __str__(self):
        return self.email


class ReadingLog(models.Model):
    """Reading log model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reading_logs'
    )
    shloka = models.ForeignKey(
        Shloka,
        on_delete=models.CASCADE,
        related_name='reading_logs'
    )
    reading_type = models.CharField(
        max_length=20,
        choices=ReadingType.choices
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reading_logs'
        indexes = [
            models.Index(fields=['user', 'read_at']),
            models.Index(fields=['shloka']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.shloka} - {self.get_reading_type_display()}"


class ShlokaReadStatus(TimestampedModel):
    """Model to track if a user has marked a shloka as read."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='read_shlokas'
    )
    shloka = models.ForeignKey(
        Shloka,
        on_delete=models.CASCADE,
        related_name='read_by_users'
    )
    marked_read_at = models.DateTimeField(auto_now_add=True)
    # Track when user last saw this shloka (for showing unread ones after few days)
    last_shown_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shloka_read_status'
        unique_together = [['user', 'shloka']]
        indexes = [
            models.Index(fields=['user', 'marked_read_at']),
            models.Index(fields=['shloka']),
            models.Index(fields=['user', 'last_shown_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.shloka} - Read"


class Favorite(TimestampedModel):
    """Favorite/bookmark model for saving shlokas."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    shloka = models.ForeignKey(
        Shloka,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )

    class Meta:
        db_table = 'favorites'
        unique_together = [['user', 'shloka']]
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['shloka']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.shloka}"


class Achievement(TimestampedModel):
    """Achievement model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.TextField()
    description = models.TextField()
    icon = models.TextField(default='🏆')
    condition_type = models.CharField(max_length=50)  # e.g., 'shlokas_read', 'streak', 'level'
    condition_value = models.IntegerField()
    xp_reward = models.IntegerField(default=0)

    class Meta:
        db_table = 'achievements'
        ordering = ['condition_value']

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserAchievement(TimestampedModel):
    """User achievement tracking model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_achievements'
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='user_achievements'
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_achievements'
        unique_together = [['user', 'achievement']]
        indexes = [
            models.Index(fields=['user', 'unlocked_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.achievement.name}"


class ChatConversation(TimestampedModel):
    """Chat conversation model for chatbot."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_conversations'
    )
    title = models.TextField(blank=True, null=True)  # Optional title for the conversation

    class Meta:
        db_table = 'chat_conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title or 'Untitled'} ({self.created_at})"


class ChatMessage(TimestampedModel):
    """Chat message model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20)  # 'user' or 'assistant'
    content = models.TextField()

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

