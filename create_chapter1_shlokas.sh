#!/bin/bash
# Script to create missing shlokas for all chapters and ensure explanations are generated
# Uses Celery task to process in batches of 50

set -e  # Exit on error

echo "=========================================="
echo "Creating Missing Shlokas for All Chapters"
echo "=========================================="
echo ""

# Step 1: Queue Celery task to create missing shlokas with explanations
echo "Step 1: Queueing Celery task to create missing shlokas..."
echo "  - Book: Bhagavad Gita"
echo "  - Chapters: All (1-18)"
echo "  - Batch size: 50 verses per batch"
echo "  - Only creates missing shlokas and explanations"
echo ""

python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.tasks import create_missing_shlokas_with_explanations

# Queue the task - process all chapters (1-18) by default
task = create_missing_shlokas_with_explanations.delay(
    book_name='Bhagavad Gita',
    chapter_number=None,  # None means process all chapters
    chapters=None,  # None means process all chapters (1-18)
    batch_size=50,
    max_verses_per_chapter=None  # Process all missing verses per chapter
)

print(f'✓ Task queued with ID: {task.id}')
print(f'  Check Celery worker logs for progress')
print(f'  You can check task status with:')
print(f'    from apps.sanatan_app.tasks import create_missing_shlokas_with_explanations')
print(f'    result = create_missing_shlokas_with_explanations.AsyncResult(\"{task.id}\")')
print(f'    print(result.get())')
"

echo ""
echo "Step 1 completed! Task is running in background."
echo ""

# Step 2: Wait a bit and then check status
echo "Step 2: Waiting 10 seconds, then checking initial status..."
sleep 10

python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.models import Shloka, ShlokaExplanation

# Check all chapters
all_shlokas = Shloka.objects.filter(book_name='Bhagavad Gita').order_by('chapter_number', 'verse_number')

total = all_shlokas.count()
with_explanations = 0
without_explanations = []
chapter_stats = {}

for shloka in all_shlokas:
    has_explanation = ShlokaExplanation.objects.filter(shloka=shloka).exists()
    chapter = shloka.chapter_number
    
    if chapter not in chapter_stats:
        chapter_stats[chapter] = {'total': 0, 'with_expl': 0, 'without_expl': 0}
    
    chapter_stats[chapter]['total'] += 1
    
    if has_explanation:
        with_explanations += 1
        chapter_stats[chapter]['with_expl'] += 1
    else:
        without_explanations.append(shloka)
        chapter_stats[chapter]['without_expl'] += 1

print(f'Current status across all chapters:')
print(f'  Total shlokas: {total}')
print(f'  Shlokas with explanations: {with_explanations}')
print(f'  Shlokas without explanations: {len(without_explanations)}')
print(f'\n  Per-chapter breakdown:')
for chapter in sorted(chapter_stats.keys()):
    stats = chapter_stats[chapter]
    print(f'    Chapter {chapter}: {stats[\"total\"]} total, {stats[\"with_expl\"]} with explanations, {stats[\"without_expl\"]} missing')

if without_explanations:
    print(f'\n  Sample shlokas still missing explanations (first 10):')
    for shloka in without_explanations[:10]:
        print(f'    - Chapter {shloka.chapter_number}, Verse {shloka.verse_number}')
    if len(without_explanations) > 10:
        print(f'    ... and {len(without_explanations) - 10} more')
else:
    print('\n  ✓ All shlokas have explanations!')
"

echo ""
echo "=========================================="
echo "Task queued! Monitor Celery worker for progress."
echo "=========================================="
echo ""
echo "To check task status, run:"
echo "  python manage.py shell"
echo "  >>> from apps.sanatan_app.tasks import create_missing_shlokas_with_explanations"
echo "  >>> result = create_missing_shlokas_with_explanations.AsyncResult('<task_id>')"
echo "  >>> print(result.get())"
echo ""

