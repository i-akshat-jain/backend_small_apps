#!/usr/bin/env python
"""Check quality score statistics for Chapter 1 shlokas."""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.models import Shloka, ShlokaExplanation

# Get all Chapter 1 shlokas
shlokas = Shloka.objects.filter(book_name='Bhagavad Gita', chapter_number=1)
print(f'Found {shlokas.count()} shlokas in Chapter 1')

# Check how many have explanations
with_explanations = ShlokaExplanation.objects.filter(shloka__in=shlokas)
print(f'Shlokas with explanations: {with_explanations.count()}')

# Check quality scores
checked = with_explanations.exclude(quality_score=0)
print(f'Shlokas with quality scores: {checked.count()}')

# Show quality score distribution
if checked.exists():
    scores = list(checked.values_list('quality_score', flat=True))
    print(f'\nQuality Score Statistics:')
    print(f'  Range: {min(scores)} - {max(scores)}')
    print(f'  Average: {sum(scores) / len(scores):.2f}')
    print(f'  Median: {sorted(scores)[len(scores)//2]}')
    
    # Count by quality ranges
    excellent = sum(1 for s in scores if s >= 90)
    good = sum(1 for s in scores if 70 <= s < 90)
    fair = sum(1 for s in scores if 50 <= s < 70)
    poor = sum(1 for s in scores if s < 50)
    
    print(f'\nQuality Distribution:')
    print(f'  Excellent (≥90): {excellent}')
    print(f'  Good (70-89): {good}')
    print(f'  Fair (50-69): {fair}')
    print(f'  Poor (<50): {poor}')

