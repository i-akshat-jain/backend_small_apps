#!/usr/bin/env python
"""
Ensure all Chapter 1 shlokas meet high quality standards (threshold: 95).
This script will:
1. Check quality of all explanations
2. Improve any that don't meet the 95 threshold
3. Verify all required fields are present
4. Report on final quality status

Usage:
    python ensure_high_quality_standards.py              # Synchronous (default)
    python ensure_high_quality_standards.py --async      # Use Celery async tasks
    python ensure_high_quality_standards.py --batch      # Use batch Celery task
"""
import os
import sys
import django
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.models import Shloka, ShlokaExplanation, ReadingType
from apps.sanatan_app.tasks import qa_and_improve_shloka, batch_qa_existing_shlokas
from apps.sanatan_app.services.quality_checker import QualityCheckerService
from apps.sanatan_app.services.shloka_service import ShlokaService
from django.utils import timezone
import json

QUALITY_THRESHOLD = 95

def check_missing_fields(explanation):
    """Check if explanation has all required fields."""
    required_fields = [
        'explanation_text',
        'context',
        'why_this_matters',
        'modern_examples',
        'themes',
        'reflection_prompt',
    ]
    
    missing = []
    empty = []
    
    for field in required_fields:
        value = getattr(explanation, field, None)
        if value is None:
            missing.append(field)
        elif isinstance(value, (list, dict)) and len(value) == 0:
            empty.append(field)
        elif isinstance(value, str) and not value.strip():
            empty.append(field)
    
    return missing, empty

def ensure_high_quality_standards(use_async=False, use_batch=False):
    """
    Ensure all Chapter 1 shlokas meet quality threshold of 95.
    
    Args:
        use_async: If True, use Celery async tasks (non-blocking)
        use_batch: If True, use batch Celery task (queues all at once)
    """
    
    print("=" * 70)
    print("Ensuring High Quality Standards (Threshold: 95)")
    print("=" * 70)
    
    # Get all Chapter 1 shlokas
    shlokas = Shloka.objects.filter(
        book_name="Bhagavad Gita",
        chapter_number=1
    ).order_by('verse_number')
    
    total_shlokas = shlokas.count()
    print(f"\nTotal shlokas in Chapter 1: {total_shlokas}")
    
    if total_shlokas == 0:
        print("❌ No shlokas found for Chapter 1")
        return
    
    # If using batch mode, queue all tasks at once
    if use_batch:
        print("\n" + "=" * 70)
        print("Queueing batch QA tasks via Celery...")
        print("=" * 70)
        
        # Queue individual tasks for Chapter 1 shlokas
        task_ids = []
        for shloka in shlokas:
            try:
                # Check if explanation exists first
                explanation = ShlokaExplanation.objects.get(shloka=shloka)
                task = qa_and_improve_shloka.delay(str(shloka.id), quality_threshold=QUALITY_THRESHOLD)
                task_ids.append(task.id)
            except ShlokaExplanation.DoesNotExist:
                print(f"  ⚠ Verse {shloka.verse_number}: No explanation found, skipping...")
                continue
        
        print(f"\n✓ Queued {len(task_ids)} QA tasks")
        print(f"  Total shlokas to process: {len(task_ids)}")
        print(f"  Quality threshold: {QUALITY_THRESHOLD}")
        print(f"\nTask IDs: {task_ids[:5]}{'...' if len(task_ids) > 5 else ''}")
        print(f"\nMonitor progress via Celery or check individual task results.")
        print(f"Tasks are running asynchronously in the background.")
        return
    
    # Statistics
    stats = {
        'total': total_shlokas,
        'with_explanations': 0,
        'missing_explanations': 0,
        'meets_threshold': 0,
        'below_threshold': 0,
        'improved': 0,
        'failed_improvements': 0,
        'missing_fields': 0,
        'fixed_fields': 0,
    }
    
    quality_checker = QualityCheckerService()
    shloka_service = ShlokaService()
    
    print("\n" + "=" * 70)
    print("Processing Shlokas...")
    print("=" * 70)
    
    for idx, shloka in enumerate(shlokas, 1):
        print(f"\n[{idx}/{total_shlokas}] Processing Verse {shloka.verse_number}...")
        
        # Check if explanation exists
        try:
            explanation = ShlokaExplanation.objects.get(shloka=shloka)
            stats['with_explanations'] += 1
        except ShlokaExplanation.DoesNotExist:
            print(f"  ⚠ Missing explanation - creating...")
            stats['missing_explanations'] += 1
            # Create explanation
            explanation = shloka_service.generate_and_store_explanation(shloka, ReadingType.DETAILED)
            if explanation:
                stats['with_explanations'] += 1
                print(f"  ✓ Explanation created")
            else:
                print(f"  ✗ Failed to create explanation")
                continue
        
        # Check for missing fields
        missing, empty = check_missing_fields(explanation)
        if missing or empty:
            print(f"  ⚠ Missing/empty fields: {missing + empty}")
            stats['missing_fields'] += 1
            
            # Try to regenerate if critical fields are missing
            if 'explanation_text' in missing or 'context' in missing:
                print(f"  → Regenerating explanation to fill missing fields...")
                try:
                    # Delete and regenerate
                    explanation.delete()
                    new_explanation = shloka_service.generate_and_store_explanation(shloka, ReadingType.DETAILED)
                    if new_explanation:
                        explanation = new_explanation
                        stats['fixed_fields'] += 1
                        print(f"  ✓ Explanation regenerated")
                except Exception as e:
                    print(f"  ✗ Failed to regenerate: {e}")
        
        # Check quality
        print(f"  Checking quality...")
        quality_result = quality_checker.check_quality(explanation)
        current_score = quality_result['overall_score']
        
        # Update quality score in DB
        explanation.quality_score = int(current_score)
        explanation.quality_checked_at = timezone.now()
        explanation.save(update_fields=['quality_score', 'quality_checked_at'])
        
        print(f"  Current quality score: {current_score:.2f}/100")
        
        # Check if meets threshold
        if current_score >= QUALITY_THRESHOLD:
            stats['meets_threshold'] += 1
            print(f"  ✓ Meets quality threshold (≥{QUALITY_THRESHOLD})")
        else:
            stats['below_threshold'] += 1
            print(f"  ⚠ Below threshold ({current_score:.2f} < {QUALITY_THRESHOLD}) - improving...")
            
            # Run improvement task (sync or async)
            try:
                if use_async:
                    # Queue async task
                    task = qa_and_improve_shloka.delay(str(shloka.id), quality_threshold=QUALITY_THRESHOLD)
                    print(f"  → Queued async task: {task.id}")
                    # Wait for result (or you could collect tasks and wait later)
                    result = task.get(timeout=300)  # 5 minute timeout
                else:
                    # Run synchronously (direct call)
                    result = qa_and_improve_shloka(str(shloka.id), quality_threshold=QUALITY_THRESHOLD)
                
                if result.get('success'):
                    explanation.refresh_from_db()
                    final_score = explanation.quality_score
                    initial_score_from_result = result.get('initial_qa_score', current_score)
                    
                    # Only report as improved if score actually increased
                    score_delta = final_score - initial_score_from_result
                    if result.get('improved') and score_delta > 0:
                        stats['improved'] += 1
                        print(f"  ✓ Improved: {initial_score_from_result:.2f} → {final_score:.2f} (Δ{score_delta:+.2f})")
                    elif result.get('improved') and score_delta <= 0:
                        # Improvement was attempted but score didn't increase (or decreased)
                        print(f"  ⚠ Improvement attempted but score didn't improve: {initial_score_from_result:.2f} → {final_score:.2f} (Δ{score_delta:+.2f})")
                        if final_score < QUALITY_THRESHOLD:
                            stats['failed_improvements'] += 1
                    else:
                        print(f"  ⚠ Improvement attempted but score: {final_score:.2f}")
                        if final_score < QUALITY_THRESHOLD:
                            stats['failed_improvements'] += 1
                else:
                    stats['failed_improvements'] += 1
                    print(f"  ✗ Improvement failed: {result.get('message', 'Unknown error')}")
            except Exception as e:
                stats['failed_improvements'] += 1
                print(f"  ✗ Error during improvement: {e}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Final report
    print("\n" + "=" * 70)
    print("Final Report")
    print("=" * 70)
    print(f"Total shlokas: {stats['total']}")
    print(f"With explanations: {stats['with_explanations']}")
    print(f"Missing explanations: {stats['missing_explanations']}")
    print(f"Meets threshold (≥{QUALITY_THRESHOLD}): {stats['meets_threshold']}")
    print(f"Below threshold: {stats['below_threshold']}")
    print(f"Successfully improved: {stats['improved']}")
    print(f"Failed improvements: {stats['failed_improvements']}")
    print(f"Missing fields found: {stats['missing_fields']}")
    print(f"Fields fixed: {stats['fixed_fields']}")
    
    # Quality distribution
    explanations = ShlokaExplanation.objects.filter(shloka__in=shlokas)
    if explanations.exists():
        scores = list(explanations.values_list('quality_score', flat=True))
        if scores:
            print(f"\nQuality Score Distribution:")
            print(f"  Average: {sum(scores) / len(scores):.2f}")
            print(f"  Min: {min(scores)}")
            print(f"  Max: {max(scores)}")
            print(f"  ≥{QUALITY_THRESHOLD}: {sum(1 for s in scores if s >= QUALITY_THRESHOLD)}")
            print(f"  <{QUALITY_THRESHOLD}: {sum(1 for s in scores if s < QUALITY_THRESHOLD)}")
    
    print("\n" + "=" * 70)
    print("Process Complete!")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ensure high quality standards for Chapter 1 shlokas')
    parser.add_argument('--async', dest='use_async', action='store_true',
                        help='Use Celery async tasks (non-blocking)')
    parser.add_argument('--batch', dest='use_batch', action='store_true',
                        help='Use batch Celery task (queues all at once, fastest)')
    args = parser.parse_args()
    
    ensure_high_quality_standards(use_async=args.use_async, use_batch=args.use_batch)

