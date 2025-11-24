"""Serializers for Sanatan App API."""
from rest_framework import serializers
from .models import Shloka, ShlokaExplanation, ReadingType


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

