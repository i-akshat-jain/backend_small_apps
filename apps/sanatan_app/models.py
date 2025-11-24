"""Django models for Sanatan App."""
from django.db import models
from django.core.validators import MinValueValidator
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
    password = models.TextField()  # Should be hashed

    class Meta:
        db_table = 'users'

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

