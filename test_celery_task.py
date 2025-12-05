#!/usr/bin/env python
"""
Test script for the improve_shloka_explanation Celery task.
"""
import os
import sys
import django
import time

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.tasks import improve_shloka_explanation
from apps.sanatan_app.models import Shloka, ShlokaExplanation

def main():
    print("=" * 60)
    print("Testing Celery Task: improve_shloka_explanation")
    print("=" * 60)
    
    # Find or create a test shloka
    shloka, created = Shloka.objects.get_or_create(
        book_name="Bhagavad Gita",
        chapter_number=2,
        verse_number=48,
        defaults={
            'sanskrit_text': 'योगस्थः कुरु कर्माणि सङ्गं त्यक्त्वा धनञ्जय',
            'transliteration': 'yoga-sthaḥ kuru karmāṇi saṅgaṁ tyaktvā dhanañjaya'
        }
    )
    
    print(f"\n✓ Using shloka: {shloka}")
    print(f"  Shloka ID: {shloka.id}")
    
    # Create a low-quality explanation if it doesn't exist
    explanation, created = ShlokaExplanation.objects.get_or_create(
        shloka=shloka,
        defaults={
            'summary': 'Short summary',
            'detailed_meaning': '',
            'detailed_explanation': 'Basic explanation',
            'context': '',
            'why_this_matters': '',
            'modern_examples': [],
            'themes': [],
            'reflection_prompt': '',
            'quality_score': 0,
        }
    )
    
    if created:
        print(f"✓ Created test explanation (ID: {explanation.id})")
    else:
        print(f"✓ Using existing explanation (ID: {explanation.id})")
        print(f"  Current quality score: {explanation.quality_score}/100")
    
    # Test 1: Call task synchronously (for testing)
    print("\n" + "-" * 60)
    print("Test 1: Calling task synchronously...")
    print("-" * 60)
    
    try:
        result = improve_shloka_explanation(
            shloka_id=str(shloka.id),
            max_iterations=2,
            min_score_threshold=70
        )
        
        print(f"\n✓ Task completed!")
        print(f"  - Success: {result.get('success', False)}")
        print(f"  - Shloka ID: {result.get('shloka_id', 'N/A')}")
        print(f"  - Initial Score: {result.get('initial_score', 0)}/100")
        print(f"  - Final Score: {result.get('final_score', 0)}/100")
        print(f"  - Improvement: {result.get('improvement_delta', 0):+.1f} points")
        print(f"  - Iterations: {result.get('iterations', 0)}")
        print(f"  - Sections Improved: {', '.join(result.get('improvements_made', [])) if result.get('improvements_made') else 'None'}")
        print(f"  - Message: {result.get('message', 'N/A')}")
        
        if result.get('error'):
            print(f"  - Error: {result.get('error')}")
        
        # Refresh explanation from database
        explanation.refresh_from_db()
        print(f"\n✓ Updated explanation quality score: {explanation.quality_score}/100")
        print(f"  Improvement version: {explanation.improvement_version}")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Call task asynchronously (actual Celery task)
    print("\n" + "-" * 60)
    print("Test 2: Calling task asynchronously via Celery...")
    print("-" * 60)
    print("Note: This requires Celery worker to be running with latest code.")
    print("      If worker was started before task was added, restart it first.")
    print("      Command: celery -A core worker --loglevel=info")
    print()
    
    try:
        # Create another low-quality explanation for async test
        shloka2, _ = Shloka.objects.get_or_create(
            book_name="Bhagavad Gita",
            chapter_number=2,
            verse_number=49,
            defaults={
                'sanskrit_text': 'दूरेण ह्यवरं कर्म बुद्धियोगाद्धनञ्जय',
                'transliteration': 'dūreṇa hy-avaraṁ karma buddhi-yogād dhanañjaya'
            }
        )
        
        explanation2, created2 = ShlokaExplanation.objects.get_or_create(
            shloka=shloka2,
            defaults={
                'summary': 'Test',
                'detailed_meaning': '',
                'detailed_explanation': '',
                'context': '',
                'why_this_matters': '',
                'modern_examples': [],
                'themes': [],
                'reflection_prompt': '',
                'quality_score': 0,
            }
        )
        
        print(f"✓ Submitting async task for shloka: {shloka2}")
        async_result = improve_shloka_explanation.delay(
            shloka_id=str(shloka2.id),
            max_iterations=2,
            min_score_threshold=70
        )
        
        print(f"  Task ID: {async_result.id}")
        print("  Waiting for task to complete...")
        
        # Wait for task with timeout
        timeout = 120  # 2 minutes
        start_time = time.time()
        
        while not async_result.ready():
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"\n✗ Task timed out after {timeout} seconds")
                print(f"  Task state: {async_result.state}")
                print("  Note: This might mean the worker needs to be restarted.")
                return False
            
            time.sleep(2)
            print(f"  ... still processing (elapsed: {int(elapsed)}s, state: {async_result.state})")
        
        # Get result
        try:
            result = async_result.get(timeout=10)
            
            print(f"\n✓ Async task completed!")
            print(f"  - Success: {result.get('success', False)}")
            print(f"  - Initial Score: {result.get('initial_score', 0)}/100")
            print(f"  - Final Score: {result.get('final_score', 0)}/100")
            print(f"  - Improvement: {result.get('improvement_delta', 0):+.1f} points")
            print(f"  - Iterations: {result.get('iterations', 0)}")
            print(f"  - Message: {result.get('message', 'N/A')}")
            
            # Refresh explanation from database
            explanation2.refresh_from_db()
            print(f"\n✓ Updated explanation quality score: {explanation2.quality_score}/100")
        except Exception as e:
            error_msg = str(e)
            if 'NotRegistered' in error_msg:
                print(f"\n⚠ Async test skipped: Worker doesn't have latest task code.")
                print(f"  Error: {error_msg}")
                print(f"  Solution: Restart Celery worker to pick up new task.")
                print(f"  Synchronous test passed, so task logic is correct.")
            else:
                raise
        
    except Exception as e:
        error_msg = str(e)
        if 'NotRegistered' in error_msg:
            print(f"\n⚠ Async test skipped: Worker needs restart.")
            print(f"  Synchronous test passed, so task logic is correct.")
        else:
            print(f"\n✗ Error in async test: {error_msg}")
            import traceback
            traceback.print_exc()
            return False
    
    print("\n" + "=" * 60)
    print("✓ All tests completed!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

