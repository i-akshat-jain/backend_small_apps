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
    list_display = ['id', 'shloka', 'quality_score', 'improvement_version', 'ai_model_used', 'created_at']
    list_filter = ['quality_score', 'ai_model_used', 'created_at', 'quality_checked_at']
    search_fields = ['summary', 'detailed_meaning', 'detailed_explanation', 'context', 'shloka__book_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'quality_checked_at']
    fieldsets = (
        ('Shloka', {
            'fields': ('shloka',)
        }),
        ('Structured Content', {
            'fields': ('summary', 'detailed_meaning', 'detailed_explanation', 'context', 
                      'why_this_matters', 'modern_examples', 'themes', 'reflection_prompt')
        }),
        ('Quality Tracking', {
            'fields': ('quality_score', 'quality_checked_at', 'improvement_version')
        }),
        ('Metadata', {
            'fields': ('ai_model_used', 'generation_prompt')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


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

