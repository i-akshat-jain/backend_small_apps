"""Django admin configuration for Sanatan App."""
from django.contrib import admin
from .models import Shloka, ShlokaExplanation, User, ReadingLog


@admin.register(Shloka)
class ShlokaAdmin(admin.ModelAdmin):
    """Admin interface for Shloka model."""
    list_display = ['id', 'book_name', 'chapter_number', 'verse_number', 'created_at']
    list_filter = ['book_name', 'created_at']
    search_fields = ['book_name', 'sanskrit_text', 'transliteration']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(ShlokaExplanation)
class ShlokaExplanationAdmin(admin.ModelAdmin):
    """Admin interface for ShlokaExplanation model."""
    list_display = ['id', 'shloka', 'explanation_type', 'ai_model_used', 'created_at']
    list_filter = ['explanation_type', 'ai_model_used', 'created_at']
    search_fields = ['explanation_text', 'shloka__book_name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""
    list_display = ['id', 'name', 'email', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(ReadingLog)
class ReadingLogAdmin(admin.ModelAdmin):
    """Admin interface for ReadingLog model."""
    list_display = ['id', 'user', 'shloka', 'reading_type', 'read_at']
    list_filter = ['reading_type', 'read_at']
    search_fields = ['user__email', 'shloka__book_name']
    readonly_fields = ['id', 'read_at']

