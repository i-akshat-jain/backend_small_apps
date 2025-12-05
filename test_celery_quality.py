#!/usr/bin/env python
"""
Test Celery quality check task asynchronously and monitor results.
"""
import os
import sys
import django
import time

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.models import Shloka, ShlokaExplanation
from apps.sanatan_app.tasks import qa_and_improve_shloka
import json

def test_celery_quality_check(shloka_id=None, quality_threshold=50):
    """Test quality check using Celery async task."""
    
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
    print("Testing Celery Quality Check (Async)")
    print("=" * 70)
    print(f"\nShloka: {shloka.book_name} Chapter {shloka.chapter_number}, Verse {shloka.verse_number}")
    print(f"Shloka ID: {shloka.id}")
    print(f"Quality Threshold: {quality_threshold}")
    
    # Check explanation
    try:
        explanation = ShlokaExplanation.objects.get(shloka=shloka)
        print(f"\n✓ Explanation found")
        print(f"  Current quality_score: {explanation.quality_score}")
        print(f"  Quality checked at: {explanation.quality_checked_at}")
    except ShlokaExplanation.DoesNotExist:
        print("\n❌ No explanation found")
        return
    
    # Queue Celery task
    print("\n" + "=" * 70)
    print("Queueing Celery Task...")
    print("=" * 70)
    
    task = qa_and_improve_shloka.delay(str(shloka.id), quality_threshold=quality_threshold)
    print(f"\n✓ Task queued: {task.id}")
    print(f"  Task state: {task.state}")
    print(f"\nWaiting for task to complete...")
    
    # Monitor task
    max_wait = 300  # 5 minutes max
    start_time = time.time()
    last_state = None
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"\n⏱ Timeout after {max_wait} seconds")
            break
        
        # Check task state
        state = task.state
        if state != last_state:
            print(f"  [{elapsed:.1f}s] Task state: {state}")
            last_state = state
        
        if state == 'SUCCESS':
            result = task.get()
            print("\n" + "=" * 70)
            print("Task Completed Successfully!")
            print("=" * 70)
            print(json.dumps(result, indent=2))
            
            # Refresh explanation
            explanation.refresh_from_db()
            
            print("\n" + "=" * 70)
            print("Updated Explanation:")
            print("=" * 70)
            print(f"  Quality Score: {explanation.quality_score}")
            print(f"  Quality Checked At: {explanation.quality_checked_at}")
            print(f"  Improvement Version: {explanation.improvement_version}")
            print(f"  Improved: {result.get('improved', False)}")
            
            if result.get('improved'):
                print(f"\n✓ Explanation was improved!")
                print(f"  Score: {result.get('initial_qa_score', 0):.1f} → {result.get('final_qa_score', 0):.1f}")
                print(f"  Delta: +{result.get('improvement_delta', 0):.1f} points")
            
            break
        elif state == 'FAILURE':
            print(f"\n❌ Task failed!")
            try:
                error = task.get(propagate=False)
                print(f"Error: {error}")
            except Exception as e:
                print(f"Error getting result: {e}")
            break
        elif state in ['PENDING', 'STARTED', 'RETRY']:
            time.sleep(2)
        else:
            print(f"  Unknown state: {state}")
            time.sleep(2)
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)

if __name__ == "__main__":
    # Test with lower threshold to trigger improvement
    shloka_id = sys.argv[1] if len(sys.argv) > 1 else None
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    test_celery_quality_check(shloka_id, threshold)

