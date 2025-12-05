#!/usr/bin/env python
"""
Test script to check quality and improve explanations for Chapter 1 shlokas.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.models import Shloka, ShlokaExplanation
from apps.sanatan_app.tasks import qa_and_improve_shloka
import json

def test_quality_check(shloka_id=None):
    """Test quality check on a specific shloka or first shloka from Chapter 1."""
    
    # Get shloka
    if shloka_id:
        try:
            shloka = Shloka.objects.get(id=shloka_id)
        except Shloka.DoesNotExist:
            print(f"❌ Shloka with ID {shloka_id} not found")
            return
    else:
        # Get first shloka from Chapter 1
        shloka = Shloka.objects.filter(
            book_name="Bhagavad Gita",
            chapter_number=1
        ).order_by('verse_number').first()
        
        if not shloka:
            print("❌ No shlokas found for Chapter 1")
            return
    
    print("=" * 70)
    print("Testing Quality Check and Improvement")
    print("=" * 70)
    print(f"\nShloka: {shloka.book_name} Chapter {shloka.chapter_number}, Verse {shloka.verse_number}")
    print(f"Shloka ID: {shloka.id}")
    print(f"Sanskrit: {shloka.sanskrit_text[:100]}...")
    
    # Check if explanation exists
    try:
        explanation = ShlokaExplanation.objects.get(shloka=shloka)
        print(f"\n✓ Explanation found (ID: {explanation.id})")
        print(f"  Current quality_score: {explanation.quality_score}")
        print(f"  Quality checked at: {explanation.quality_checked_at}")
        print(f"  AI Model: {explanation.ai_model_used}")
    except ShlokaExplanation.DoesNotExist:
        print("\n❌ No explanation found for this shloka")
        return
    
    # Show explanation preview
    print(f"\nExplanation Preview:")
    print(f"  Summary: {explanation.explanation_text[:200] if explanation.explanation_text else 'N/A'}...")
    print(f"  Context: {explanation.context[:200] if explanation.context else 'N/A'}...")
    
    # Run quality check task
    print("\n" + "=" * 70)
    print("Running QA and Improvement Task...")
    print("=" * 70)
    
    # Run synchronously first to see immediate results
    print("\nRunning task synchronously (this may take a minute)...")
    result = qa_and_improve_shloka(str(shloka.id), quality_threshold=70)
    
    print("\n" + "=" * 70)
    print("Task Results:")
    print("=" * 70)
    print(json.dumps(result, indent=2))
    
    # Refresh explanation to see updated values
    explanation.refresh_from_db()
    
    print("\n" + "=" * 70)
    print("Updated Explanation:")
    print("=" * 70)
    print(f"  Quality Score: {explanation.quality_score} (was: {result.get('initial_qa_score', 'N/A')})")
    print(f"  Quality Checked At: {explanation.quality_checked_at}")
    print(f"  Improvement Version: {explanation.improvement_version}")
    print(f"  Improved: {result.get('improved', False)}")
    
    if result.get('improved'):
        print(f"\n✓ Explanation was improved!")
        print(f"  Score improvement: {result.get('initial_qa_score', 0):.1f} → {result.get('final_qa_score', 0):.1f}")
        print(f"  Delta: +{result.get('improvement_delta', 0):.1f} points")
    else:
        if result.get('initial_qa_score', 0) >= 70:
            print(f"\n✓ Quality already meets threshold (≥70)")
        else:
            print(f"\n⚠ Quality below threshold but improvement may have failed")
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)

if __name__ == "__main__":
    # Test with first shloka from Chapter 1, or use specific ID
    # You can pass a shloka ID as command line argument
    shloka_id = sys.argv[1] if len(sys.argv) > 1 else None
    test_quality_check(shloka_id)

