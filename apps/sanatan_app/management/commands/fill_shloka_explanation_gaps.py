"""
Django management command to ensure shlokas have explanations and check/improve quality.

This command:
1. Creates missing explanations for shlokas that don't have any
2. Uses Celery tasks to check and improve quality of existing explanations

Run: python manage.py fill_shloka_explanation_gaps
"""
from django.core.management.base import BaseCommand
from apps.sanatan_app.models import Shloka, ShlokaExplanation
from apps.sanatan_app.services.shloka_service import ShlokaService
from apps.sanatan_app.tasks import qa_and_improve_shloka, batch_qa_existing_shlokas
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ensure shlokas have explanations and check/improve quality using Celery tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually creating/updating explanations',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Delay in seconds between API calls when creating explanations (default: 0.5)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each shloka',
        )
        parser.add_argument(
            '--shloka-id',
            type=str,
            default=None,
            help='Process a specific shloka ID (UUID format). If provided, only this shloka will be processed.',
        )
        parser.add_argument(
            '--use-celery',
            action='store_true',
            default=True,
            help='Use Celery tasks for quality checking and improvement (default: True)',
        )
        parser.add_argument(
            '--quality-threshold',
            type=int,
            default=95,
            help='Quality score threshold for improvement (default: 95)',
        )
        parser.add_argument(
            '--create-only',
            action='store_true',
            help='Only create missing explanations, skip quality checking',
        )

    def handle(self, *args, **options):
        """Ensure shlokas have explanations and check/improve quality."""
        dry_run = options['dry_run']
        delay = options['delay']
        verbose = options['verbose']
        shloka_id = options.get('shloka_id')
        use_celery = options.get('use_celery', True)
        quality_threshold = options.get('quality_threshold', 95)
        create_only = options.get('create_only', False)
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Shloka Explanation Management"))
        self.stdout.write("=" * 70)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No explanations will be created/updated"))
        
        # Get shlokas - filter by ID if provided
        if shloka_id:
            try:
                import uuid
                shloka_uuid = uuid.UUID(shloka_id)
                all_shlokas = Shloka.objects.filter(id=shloka_uuid)
                total_shlokas = all_shlokas.count()
                
                if total_shlokas == 0:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Shloka with ID {shloka_id} not found in database.")
                    )
                    return
                
                self.stdout.write(f"\nProcessing specific shloka ID: {shloka_id}")
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"✗ Invalid shloka ID format: {shloka_id}. Expected UUID format.")
                )
                return
        else:
            # Get all shlokas
            all_shlokas = Shloka.objects.all().order_by(
                'book_name', 'chapter_number', 'verse_number'
            )
            total_shlokas = all_shlokas.count()
        
        self.stdout.write(f"\nTotal shlokas to process: {total_shlokas}")
        
        if total_shlokas == 0:
            self.stdout.write(self.style.WARNING("No shlokas found in database."))
            return
        
        # Step 1: Check for shlokas without explanations and create them
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("Step 1: Creating Missing Explanations")
        self.stdout.write("=" * 70)
        
        shlokas_without_explanations = []
        shlokas_with_explanations = []
        
        for shloka in all_shlokas:
            has_explanation = ShlokaExplanation.objects.filter(shloka=shloka).exists()
            if has_explanation:
                shlokas_with_explanations.append(shloka)
            else:
                shlokas_without_explanations.append(shloka)
        
        self.stdout.write(f"Shlokas with explanations: {len(shlokas_with_explanations)}")
        self.stdout.write(f"Shlokas without explanations: {len(shlokas_without_explanations)}")
        
        if shlokas_without_explanations:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nDRY RUN - Would create explanations for {len(shlokas_without_explanations)} shlokas"
                    )
                )
                if verbose:
                    for shloka in shlokas_without_explanations[:10]:
                        self.stdout.write(
                            f"  - {shloka.book_name} Ch.{shloka.chapter_number}, V.{shloka.verse_number}"
                        )
                    if len(shlokas_without_explanations) > 10:
                        self.stdout.write(f"  ... and {len(shlokas_without_explanations) - 10} more")
            else:
                self.stdout.write(f"\nCreating explanations for {len(shlokas_without_explanations)} shlokas...")
                shloka_service = ShlokaService()
                created_count = 0
                failed_count = 0
                
                for idx, shloka in enumerate(shlokas_without_explanations, 1):
                    try:
                        if verbose:
                            self.stdout.write(
                                f"  [{idx}/{len(shlokas_without_explanations)}] "
                                f"Creating explanation for {shloka.book_name} "
                                f"Ch.{shloka.chapter_number}, V.{shloka.verse_number}...",
                                ending=' '
                            )
                        
                        explanation = shloka_service.generate_and_store_explanation(shloka)
                        
                        if explanation:
                            created_count += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS("✓"))
                        else:
                            failed_count += 1
                            if verbose:
                                self.stdout.write(self.style.WARNING("⚠ (Generation failed)"))
                        
                        # Delay to avoid rate limiting
                        time.sleep(delay)
                        
                    except Exception as e:
                        failed_count += 1
                        if verbose:
                            self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"✗ Error creating explanation for "
                                    f"{shloka.book_name} Ch.{shloka.chapter_number}, "
                                    f"V.{shloka.verse_number}: {str(e)}"
                                )
                            )
                        logger.exception(e)
                        continue
                
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Created {created_count} explanation(s)")
                )
                if failed_count > 0:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ Failed to create {failed_count} explanation(s)")
                    )
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ All shlokas already have explanations"))
        
        # Step 2: Quality checking and improvement (if not create-only)
        if not create_only:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("Step 2: Quality Checking and Improvement")
            self.stdout.write("=" * 70)
            
            if use_celery:
                self.stdout.write(f"\nUsing Celery tasks for quality checking and improvement...")
                self.stdout.write(f"Quality threshold: {quality_threshold}/100")
                
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"DRY RUN - Would queue Celery tasks for {len(shlokas_with_explanations)} shlokas"
                        )
                    )
                else:
                    # Queue Celery tasks for quality checking and improvement
                    task_ids = []
                    shlokas_to_process = shlokas_with_explanations
                    
                    if shloka_id:
                        # For single shloka, queue individual task
                        try:
                            import uuid
                            shloka_uuid = uuid.UUID(shloka_id)
                            task = qa_and_improve_shloka.delay(str(shloka_uuid), quality_threshold=quality_threshold)
                            task_ids.append(task.id)
                            self.stdout.write(f"Queued QA task for shloka {shloka_id}: {task.id}")
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f"Error queueing task: {str(e)}")
                            )
                    else:
                        # Use batch task
                        self.stdout.write(f"Queueing batch QA tasks for {len(shlokas_to_process)} shlokas...")
                        batch_result = batch_qa_existing_shlokas.delay(
                            max_shlokas=None,
                            quality_threshold=quality_threshold
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Queued batch QA task: {batch_result.id}\n"
                                f"  Total shlokas to process: {batch_result.get().get('total_processed', 0)}\n"
                                f"  Check Celery worker logs for progress"
                            )
                        )
            else:
                # Synchronous processing (not recommended for large datasets)
                self.stdout.write(
                    self.style.WARNING(
                        "\nSynchronous processing (not using Celery) - this may take a long time..."
                    )
                )
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"DRY RUN - Would process {len(shlokas_with_explanations)} shlokas synchronously"
                        )
                    )
                else:
                    processed_count = 0
                    for idx, shloka in enumerate(shlokas_with_explanations, 1):
                        try:
                            if verbose:
                                self.stdout.write(
                                    f"  [{idx}/{len(shlokas_with_explanations)}] "
                                    f"Processing {shloka.book_name} "
                                    f"Ch.{shloka.chapter_number}, V.{shloka.verse_number}...",
                                    ending=' '
                                )
                            
                            # Call task synchronously
                            result = qa_and_improve_shloka(str(shloka.id), quality_threshold=quality_threshold)
                            
                            if result.get('success'):
                                processed_count += 1
                                if verbose:
                                    initial = result.get('initial_qa_score', 0)
                                    final = result.get('final_qa_score', 0)
                                    improved = result.get('improved', False)
                                    status = f"✓ Score: {initial} → {final}" + (" (improved)" if improved else "")
                                    self.stdout.write(self.style.SUCCESS(status))
                            else:
                                if verbose:
                                    self.stdout.write(self.style.WARNING("⚠ Failed"))
                            
                        except Exception as e:
                            if verbose:
                                self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
                            logger.exception(e)
                            continue
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"\n✓ Processed {processed_count} shloka(s)")
                    )
        
        # Final summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("FINAL SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total shlokas: {total_shlokas}")
        self.stdout.write(f"Shlokas with explanations: {len(shlokas_with_explanations)}")
        self.stdout.write(f"Shlokas without explanations: {len(shlokas_without_explanations)}")
        if not create_only and use_celery and not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ Quality checking tasks have been queued. "
                    "Monitor Celery worker logs for progress."
                )
            )
        self.stdout.write("=" * 70)
