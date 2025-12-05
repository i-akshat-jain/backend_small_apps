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
    """
    Shloka explanation model with structured fields.
    
    Single explanation per shloka (no summary/detailed distinction).
    All content stored in structured fields for easy querying and filtering.
    Full explanation text is generated on-demand via explanation_text property.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shloka = models.ForeignKey(
        Shloka,
        on_delete=models.CASCADE,
        related_name='explanations'
    )
    
    # Structured fields (source of truth)
    summary = models.TextField(
        blank=True, 
        null=True, 
        help_text="Brief overview of the shloka"
    )
    detailed_meaning = models.TextField(
        blank=True, 
        null=True, 
        help_text="Core meaning and philosophical significance"
    )
    detailed_explanation = models.TextField(
        blank=True, 
        null=True, 
        help_text="Deeper understanding and interpretation"
    )
    context = models.TextField(
        blank=True, 
        null=True, 
        help_text="Context of when/why it was said, context in the dialogue/story"
    )
    why_this_matters = models.TextField(
        blank=True, 
        null=True, 
        help_text="Modern relevance and practical importance"
    )
    modern_examples = models.JSONField(
        blank=True, 
        null=True, 
        help_text="Modern applications as JSON array of {category, description}"
    )
    themes = models.JSONField(
        blank=True, 
        null=True, 
        help_text="Key themes/tags as JSON array of strings"
    )
    reflection_prompt = models.TextField(
        blank=True, 
        null=True, 
        help_text="Question for contemplation"
    )
    
    # Quality tracking
    quality_score = models.IntegerField(
        default=0,
        help_text="Overall quality score (0-100)"
    )
    quality_checked_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp of last quality check"
    )
    improvement_version = models.IntegerField(
        default=0,
        help_text="Number of improvement iterations performed"
    )
    
    # Metadata
    ai_model_used = models.TextField(blank=True, null=True)
    generation_prompt = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'shloka_explanations'
        unique_together = [['shloka']]  # Only one explanation per shloka now
        indexes = [
            models.Index(fields=['shloka']),
            models.Index(fields=['quality_score']),
            models.Index(fields=['quality_checked_at']),
        ]

    def get_explanation_text(self):
        """
        Generate full explanation text from structured fields.
        This method provides the full explanation text for display/export purposes.
        """
        sections = []
        
        if self.summary:
            sections.append(f"SUMMARY:\n{self.summary}")
        
        if self.detailed_meaning:
            sections.append(f"DETAILED MEANING:\n{self.detailed_meaning}")
        
        if self.detailed_explanation:
            sections.append(f"DETAILED EXPLANATION:\n{self.detailed_explanation}")
        
        if self.context:
            sections.append(f"CONTEXT:\n{self.context}")
        
        if self.why_this_matters:
            sections.append(f"WHY THIS MATTERS:\n{self.why_this_matters}")
        
        if self.modern_examples:
            sections.append("MODERN EXAMPLES:")
            for example in self.modern_examples:
                if isinstance(example, dict):
                    category = example.get('category', 'Example')
                    description = example.get('description', '')
                    sections.append(f"- {category}: {description}")
                else:
                    sections.append(f"- {example}")
        
        if self.themes:
            themes_str = ', '.join(self.themes) if isinstance(self.themes, list) else str(self.themes)
            sections.append(f"KEY THEMES: {themes_str}")
        
        if self.reflection_prompt:
            sections.append(f"REFLECTION PROMPT:\n{self.reflection_prompt}")
        
        return "\n\n".join(sections) if sections else ""
    
    # Property for backward compatibility (accesses method)
    @property
    def explanation_text(self):
        """Property accessor for explanation text (backward compatibility)."""
        return self.get_explanation_text()

    def __str__(self):
        return f"{self.shloka} - Explanation"


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


class UserStreak(TimestampedModel):
    """Model to track user's reading streak and streak-related data."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='streak_data',
        db_index=True
    )
    current_streak = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current consecutive days streak"
    )
    longest_streak = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="All-time best streak"
    )
    streak_freeze_used_this_month = models.BooleanField(
        default=False,
        help_text="Whether streak freeze has been used this month"
    )
    last_streak_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last date when streak was maintained"
    )
    total_streak_days = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Lifetime total days with streaks"
    )
    streak_freeze_reset_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when streak freeze will reset (first day of next month)"
    )
    awarded_milestones = models.JSONField(
        default=list,
        blank=True,
        help_text="List of streak milestone days that have been awarded (e.g., [7, 30, 100, 365])"
    )

    class Meta:
        db_table = 'user_streaks'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['current_streak']),
            models.Index(fields=['longest_streak']),
        ]

    def __str__(self):
        return f"{self.user.email} - Streak: {self.current_streak} days (Best: {self.longest_streak})"


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

