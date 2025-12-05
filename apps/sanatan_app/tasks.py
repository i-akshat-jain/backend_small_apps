"""
Celery tasks for Sanatan App.
"""
from celery import shared_task
from celery.exceptions import Retry
from django.utils import timezone
import logging
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)


@shared_task(name='sanatan_app.test_task')
def test_task(message='Hello from Celery!'):
    """
    Simple test task to verify Celery is working.
    
    Usage:
        from apps.sanatan_app.tasks import test_task
        result = test_task.delay('Test message')
    """
    logger.info(f"Test task received: {message}")
    return f"Task completed: {message}"


@shared_task(
    name='sanatan_app.improve_shloka_explanation',
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Start with 60 seconds
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes
    retry_jitter=True,
)
def improve_shloka_explanation(self, shloka_id: str, max_iterations: int = 3, min_score_threshold: int = 95) -> Dict:
    """
    Celery task to improve a shloka explanation quality.
    
    Flow:
    1. Load explanation from database
    2. Check current quality
    3. If quality is below threshold, improve it
    4. Re-check quality after improvement
    5. Save updated explanation
    
    Args:
        shloka_id: UUID of the Shloka to improve explanation for
        max_iterations: Maximum number of improvement iterations (default: 3)
        min_score_threshold: Minimum quality score threshold (default: 95)
        
    Returns:
        Dictionary with task results:
        - success: bool
        - shloka_id: str
        - initial_score: float
        - final_score: float
        - improvement_delta: float
        - iterations: int
        - improvements_made: list
        - message: str
        
    Raises:
        Retry: If task should be retried (handled by Celery)
        Exception: If task fails after all retries
    """
    task_id = self.request.id
    logger.info(
        f"[Task {task_id}] Starting improvement task for shloka_id: {shloka_id}, "
        f"max_iterations: {max_iterations}, threshold: {min_score_threshold}"
    )
    
    try:
        # Import here to avoid circular imports
        from apps.sanatan_app.models import Shloka, ShlokaExplanation
        from apps.sanatan_app.services.improvement_service import ImprovementService
        from apps.sanatan_app.services.quality_checker import QualityCheckerService
        
        # Load shloka
        try:
            shloka = Shloka.objects.get(id=shloka_id)
        except Shloka.DoesNotExist:
            error_msg = f"Shloka with id {shloka_id} not found"
            logger.error(f"[Task {task_id}] {error_msg}")
            return {
                'success': False,
                'shloka_id': shloka_id,
                'error': error_msg,
                'message': error_msg
            }
        
        # Load or create explanation
        explanation, created = ShlokaExplanation.objects.get_or_create(
            shloka=shloka,
            defaults={
                'summary': '',
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
        
        if created:
            logger.info(f"[Task {task_id}] Created new explanation for shloka {shloka_id}")
        
        # Check initial quality
        logger.info(f"[Task {task_id}] Checking initial quality...")
        quality_checker = QualityCheckerService()
        initial_quality = quality_checker.check_quality(explanation)
        initial_score = initial_quality['overall_score']
        
        logger.info(
            f"[Task {task_id}] Initial quality score: {initial_score}/100 "
            f"(Completeness: {initial_quality['completeness_score']}/25, "
            f"Clarity: {initial_quality['clarity_score']}/25, "
            f"Accuracy: {initial_quality['accuracy_score']}/25, "
            f"Relevance: {initial_quality['relevance_score']}/15, "
            f"Structure: {initial_quality['structure_score']}/10)"
        )
        
        # Update initial quality score if not set
        if explanation.quality_score == 0 or explanation.quality_checked_at is None:
            explanation.quality_score = int(initial_score)
            explanation.quality_checked_at = timezone.now()
            explanation.save(update_fields=['quality_score', 'quality_checked_at'])
        
        # If already above threshold, return early
        if initial_score >= min_score_threshold:
            logger.info(
                f"[Task {task_id}] Explanation already meets quality threshold "
                f"({initial_score}/100 >= {min_score_threshold}). Skipping improvement."
            )
            return {
                'success': True,
                'shloka_id': str(shloka_id),
                'initial_score': initial_score,
                'final_score': initial_score,
                'improvement_delta': 0.0,
                'iterations': 0,
                'improvements_made': [],
                'message': f'Explanation already meets quality threshold ({initial_score}/100)'
            }
        
        # Improve explanation
        logger.info(f"[Task {task_id}] Starting improvement process...")
        improvement_service = ImprovementService()
        
        improvement_result = improvement_service.improve_explanation(
            explanation,
            max_iterations=max_iterations,
            min_score_threshold=min_score_threshold
        )
        
        # Refresh explanation from database to get latest values
        explanation.refresh_from_db()
        
        # Final quality check
        logger.info(f"[Task {task_id}] Performing final quality check...")
        final_quality = quality_checker.check_quality(explanation)
        final_score = final_quality['overall_score']
        
        logger.info(
            f"[Task {task_id}] Final quality score: {final_score}/100 "
            f"(Completeness: {final_quality['completeness_score']}/25, "
            f"Clarity: {final_quality['clarity_score']}/25, "
            f"Accuracy: {final_quality['accuracy_score']}/25, "
            f"Relevance: {final_quality['relevance_score']}/15, "
            f"Structure: {final_quality['structure_score']}/10)"
        )
        
        # Build result
        result = {
            'success': improvement_result['success'],
            'shloka_id': str(shloka_id),
            'initial_score': initial_score,
            'final_score': final_score,
            'improvement_delta': final_score - initial_score,
            'iterations': improvement_result['iterations'],
            'improvements_made': improvement_result['improvements_made'],
            'message': improvement_result['message']
        }
        
        logger.info(
            f"[Task {task_id}] Task completed successfully. "
            f"Score improved from {initial_score} to {final_score} "
            f"(Δ{result['improvement_delta']:+.1f}) in {improvement_result['iterations']} iteration(s)"
        )
        
        return result
        
    except Exception as exc:
        # Log the error
        logger.error(
            f"[Task {task_id}] Error improving explanation for shloka_id {shloka_id}: {str(exc)}",
            exc_info=True
        )
        
        # Check if we should retry
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            # Calculate retry delay with exponential backoff
            retry_delay = min(
                self.default_retry_delay * (2 ** retry_count),
                self.retry_backoff_max
            )
            
            logger.warning(
                f"[Task {task_id}] Retrying task (attempt {retry_count + 1}/{self.max_retries}) "
                f"after {retry_delay} seconds. Error: {str(exc)}"
            )
            
            # Raise Retry exception to trigger Celery retry
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            # Max retries reached, return error result
            logger.error(
                f"[Task {task_id}] Task failed after {retry_count} retries. "
                f"Giving up on shloka_id {shloka_id}"
            )
            return {
                'success': False,
                'shloka_id': str(shloka_id),
                'error': str(exc),
                'retries': retry_count,
                'message': f'Task failed after {retry_count} retries: {str(exc)}'
            }


@shared_task(
    name='sanatan_app.check_shloka_quality',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def check_shloka_quality(self, shloka_id: str) -> Dict:
    """
    Celery task to check and update quality score for a shloka explanation.
    
    This task only checks quality without improving the explanation.
    Useful for monitoring, auditing, or scheduled quality checks.
    
    Flow:
    1. Load explanation from database
    2. Check current quality
    3. Update quality_score and quality_checked_at
    4. Return quality metrics
    
    Args:
        shloka_id: UUID of the Shloka to check quality for
        
    Returns:
        Dictionary with quality check results:
        - success: bool
        - shloka_id: str
        - quality_score: float (0-100)
        - completeness_score: float (0-25)
        - clarity_score: float (0-25)
        - accuracy_score: float (0-25)
        - relevance_score: float (0-15)
        - structure_score: float (0-10)
        - feedback: dict with feedback for each metric
        - message: str
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting quality check for shloka_id: {shloka_id}")
    
    try:
        # Import here to avoid circular imports
        from apps.sanatan_app.models import Shloka, ShlokaExplanation
        from apps.sanatan_app.services.quality_checker import QualityCheckerService
        
        # Load shloka
        try:
            shloka = Shloka.objects.get(id=shloka_id)
        except Shloka.DoesNotExist:
            error_msg = f"Shloka with id {shloka_id} not found"
            logger.error(f"[Task {task_id}] {error_msg}")
            return {
                'success': False,
                'shloka_id': shloka_id,
                'error': error_msg,
                'message': error_msg
            }
        
        # Load explanation
        try:
            explanation = ShlokaExplanation.objects.get(shloka=shloka)
        except ShlokaExplanation.DoesNotExist:
            error_msg = f"Explanation not found for shloka_id {shloka_id}"
            logger.error(f"[Task {task_id}] {error_msg}")
            return {
                'success': False,
                'shloka_id': shloka_id,
                'error': error_msg,
                'message': error_msg
            }
        
        # Check quality
        logger.info(f"[Task {task_id}] Checking quality...")
        quality_checker = QualityCheckerService()
        quality_result = quality_checker.check_quality(explanation)
        
        # Update quality tracking fields
        explanation.quality_score = int(quality_result['overall_score'])
        explanation.quality_checked_at = timezone.now()
        explanation.save(update_fields=['quality_score', 'quality_checked_at'])
        
        logger.info(
            f"[Task {task_id}] Quality check complete. Score: {quality_result['overall_score']}/100"
        )
        
        return {
            'success': True,
            'shloka_id': str(shloka_id),
            'quality_score': quality_result['overall_score'],
            'completeness_score': quality_result['completeness_score'],
            'clarity_score': quality_result['clarity_score'],
            'accuracy_score': quality_result['accuracy_score'],
            'relevance_score': quality_result['relevance_score'],
            'structure_score': quality_result['structure_score'],
            'feedback': quality_result['feedback'],
            'message': f'Quality check complete. Score: {quality_result["overall_score"]}/100'
        }
        
    except Exception as exc:
        logger.error(
            f"[Task {task_id}] Error checking quality for shloka_id {shloka_id}: {str(exc)}",
            exc_info=True
        )
        
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            retry_delay = min(
                self.default_retry_delay * (2 ** retry_count),
                self.retry_backoff_max
            )
            
            logger.warning(
                f"[Task {task_id}] Retrying task (attempt {retry_count + 1}/{self.max_retries}) "
                f"after {retry_delay} seconds. Error: {str(exc)}"
            )
            
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            logger.error(
                f"[Task {task_id}] Task failed after {retry_count} retries. "
                f"Giving up on shloka_id {shloka_id}"
            )
            return {
                'success': False,
                'shloka_id': str(shloka_id),
                'error': str(exc),
                'retries': retry_count,
                'message': f'Task failed after {retry_count} retries: {str(exc)}'
            }


@shared_task(
    name='sanatan_app.batch_check_shlokas_quality',
    bind=True,
)
def batch_check_shlokas_quality(
    self,
    max_shlokas: Optional[int] = None,
    never_checked: bool = True,
    checked_before_days: Optional[int] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None
) -> Dict:
    """
    Batch task to check quality for multiple shlokas in the database.
    
    Args:
        max_shlokas: Maximum number of shlokas to process (None = all matching)
        never_checked: If True, only check shlokas that have never been checked
        checked_before_days: Only check shlokas checked before N days ago (None = ignore)
        min_score: Only check shlokas with quality_score >= min_score (None = ignore)
        max_score: Only check shlokas with quality_score <= max_score (None = ignore)
        
    Returns:
        Dictionary with batch results:
        - success: bool
        - total_processed: int
        - successful: int
        - failed: int
        - task_ids: list of individual task IDs
        - message: str
    """
    task_id = self.request.id
    logger.info(f"[Batch Task {task_id}] Starting batch quality check")
    
    try:
        from apps.sanatan_app.models import ShlokaExplanation
        from django.utils import timezone
        from datetime import timedelta
        
        # Build query
        queryset = ShlokaExplanation.objects.all()
        
        if never_checked:
            queryset = queryset.filter(quality_checked_at__isnull=True)
        
        if checked_before_days is not None:
            cutoff_date = timezone.now() - timedelta(days=checked_before_days)
            queryset = queryset.filter(quality_checked_at__lt=cutoff_date)
        
        if min_score is not None:
            queryset = queryset.filter(quality_score__gte=min_score)
        
        if max_score is not None:
            queryset = queryset.filter(quality_score__lte=max_score)
        
        # Limit results
        if max_shlokas:
            queryset = queryset[:max_shlokas]
        
        explanations = list(queryset)
        total_count = len(explanations)
        
        logger.info(f"[Batch Task {task_id}] Found {total_count} explanations to check")
        
        if total_count == 0:
            return {
                'success': True,
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'task_ids': [],
                'message': 'No explanations found matching criteria'
            }
        
        # Queue individual check tasks
        task_ids = []
        for explanation in explanations:
            task = check_shloka_quality.delay(str(explanation.shloka_id))
            task_ids.append(task.id)
        
        logger.info(
            f"[Batch Task {task_id}] Queued {len(task_ids)} quality check tasks"
        )
        
        return {
            'success': True,
            'total_processed': total_count,
            'successful': 0,  # Will be updated when tasks complete
            'failed': 0,  # Will be updated when tasks complete
            'task_ids': task_ids,
            'message': f'Queued {total_count} quality check tasks'
        }
        
    except Exception as exc:
        logger.error(
            f"[Batch Task {task_id}] Error in batch quality check: {str(exc)}",
            exc_info=True
        )
        return {
            'success': False,
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'task_ids': [],
            'error': str(exc),
            'message': f'Batch task failed: {str(exc)}'
        }


@shared_task(
    name='sanatan_app.batch_improve_shlokas',
    bind=True,
)
def batch_improve_shlokas(
    self,
    max_shlokas: Optional[int] = None,
    max_score_threshold: int = 95,
    max_iterations: int = 3,
    min_score_threshold: int = 95
) -> Dict:
    """
    Batch task to improve quality for multiple shlokas in the database.
    
    Args:
        max_shlokas: Maximum number of shlokas to process (None = all matching)
        max_score_threshold: Only improve shlokas with quality_score < this threshold
        max_iterations: Maximum improvement iterations per shloka
        min_score_threshold: Target quality score threshold
        
    Returns:
        Dictionary with batch results:
        - success: bool
        - total_processed: int
        - task_ids: list of individual task IDs
        - message: str
    """
    task_id = self.request.id
    logger.info(
        f"[Batch Task {task_id}] Starting batch improvement. "
        f"Threshold: {max_score_threshold}, Max shlokas: {max_shlokas}"
    )
    
    try:
        from apps.sanatan_app.models import ShlokaExplanation
        
        # Build query - only shlokas below threshold
        queryset = ShlokaExplanation.objects.filter(
            quality_score__lt=max_score_threshold
        )
        
        # Limit results
        if max_shlokas:
            queryset = queryset[:max_shlokas]
        
        explanations = list(queryset)
        total_count = len(explanations)
        
        logger.info(f"[Batch Task {task_id}] Found {total_count} explanations to improve")
        
        if total_count == 0:
            return {
                'success': True,
                'total_processed': 0,
                'task_ids': [],
                'message': f'No explanations found with score < {max_score_threshold}'
            }
        
        # Queue individual improvement tasks
        task_ids = []
        for explanation in explanations:
            task = improve_shloka_explanation.delay(
                str(explanation.shloka_id),
                max_iterations=max_iterations,
                min_score_threshold=min_score_threshold
            )
            task_ids.append(task.id)
        
        logger.info(
            f"[Batch Task {task_id}] Queued {len(task_ids)} improvement tasks"
        )
        
        return {
            'success': True,
            'total_processed': total_count,
            'task_ids': task_ids,
            'message': f'Queued {total_count} improvement tasks'
        }
        
    except Exception as exc:
        logger.error(
            f"[Batch Task {task_id}] Error in batch improvement: {str(exc)}",
            exc_info=True
        )
        return {
            'success': False,
            'total_processed': 0,
            'task_ids': [],
            'error': str(exc),
            'message': f'Batch task failed: {str(exc)}'
        }


@shared_task(
    name='sanatan_app.qa_and_improve_shloka',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def qa_and_improve_shloka(self, shloka_id: str, quality_threshold: int = 95) -> Dict:
    """
    Complete QA and improvement flow for a single shloka.
    
    This task implements the exact flow from the architecture diagram:
    1. QA for existing Shloka (check quality)
    2. If not good enough → Send to Groq for improvement
    3. QA for regenerated Shloka (re-check quality)
    4. Save to DB
    
    Args:
        shloka_id: UUID of the Shloka to QA and improve
        quality_threshold: Quality score threshold (default: 95)
        
    Returns:
        Dictionary with results:
        - success: bool
        - shloka_id: str
        - initial_qa_score: float
        - improved: bool (whether improvement was needed)
        - final_qa_score: float
        - message: str
    """
    task_id = self.request.id
    logger.info(
        f"[QA Task {task_id}] Starting QA and improvement flow for shloka_id: {shloka_id}, "
        f"threshold: {quality_threshold}"
    )
    
    try:
        from apps.sanatan_app.models import Shloka, ShlokaExplanation
        from apps.sanatan_app.services.quality_checker import QualityCheckerService
        
        # Load shloka
        try:
            shloka = Shloka.objects.get(id=shloka_id)
        except Shloka.DoesNotExist:
            error_msg = f"Shloka with id {shloka_id} not found"
            logger.error(f"[QA Task {task_id}] {error_msg}")
            return {
                'success': False,
                'shloka_id': shloka_id,
                'error': error_msg,
                'message': error_msg
            }
        
        # Load explanation
        try:
            explanation = ShlokaExplanation.objects.get(shloka=shloka)
        except ShlokaExplanation.DoesNotExist:
            error_msg = f"Explanation not found for shloka_id {shloka_id}"
            logger.error(f"[QA Task {task_id}] {error_msg}")
            return {
                'success': False,
                'shloka_id': shloka_id,
                'error': error_msg,
                'message': error_msg
            }
        
        # Step 1: QA for existing Shloka
        logger.info(f"[QA Task {task_id}] Step 1: QA for existing Shloka...")
        quality_checker = QualityCheckerService()
        initial_qa = quality_checker.check_quality(explanation)
        initial_score = initial_qa['overall_score']
        
        # Update quality tracking
        explanation.quality_score = int(initial_score)
        explanation.quality_checked_at = timezone.now()
        explanation.save(update_fields=['quality_score', 'quality_checked_at'])
        
        logger.info(
            f"[QA Task {task_id}] Initial QA score: {initial_score}/100 "
            f"(threshold: {quality_threshold})"
        )
        
        improved = False
        final_score = initial_score
        
        # Step 2: If not good enough → Send to Groq for improvement
        if initial_score < quality_threshold:
            logger.info(
                f"[QA Task {task_id}] Step 2: Quality below threshold. "
                f"Sending to Groq for improvement..."
            )
            
            # Use the improvement service directly (not the task, to keep flow synchronous)
            from apps.sanatan_app.services.improvement_service import ImprovementService
            improvement_service = ImprovementService()
            
            improvement_result = improvement_service.improve_explanation(
                explanation,
                max_iterations=5,  # Increased to allow more attempts to reach quality threshold
                min_score_threshold=quality_threshold
            )
            
            if improvement_result.get('success'):
                improved = True
                
                # Refresh explanation to get latest values
                explanation.refresh_from_db()
                
                # Step 3: QA for regenerated Shloka
                logger.info(f"[QA Task {task_id}] Step 3: QA for regenerated Shloka...")
                final_qa = quality_checker.check_quality(explanation)
                final_score = final_qa['overall_score']
                
                # Update quality tracking again
                explanation.quality_score = int(final_score)
                explanation.quality_checked_at = timezone.now()
                explanation.save(update_fields=['quality_score', 'quality_checked_at'])
                
                logger.info(
                    f"[QA Task {task_id}] Final QA score after improvement: {final_score}/100"
                )
            else:
                logger.warning(
                    f"[QA Task {task_id}] Improvement failed: {improvement_result.get('message', 'Unknown error')}"
                )
                final_score = initial_score
        else:
            logger.info(
                f"[QA Task {task_id}] Quality already meets threshold. "
                f"Skipping improvement."
            )
        
        # Step 4: Save to DB (already done above)
        logger.info(f"[QA Task {task_id}] Step 4: Saved to DB")
        
        return {
            'success': True,
            'shloka_id': str(shloka_id),
            'initial_qa_score': initial_score,
            'improved': improved,
            'final_qa_score': final_score,
            'improvement_delta': final_score - initial_score,
            'message': f'QA complete. Score: {initial_score} → {final_score}'
        }
        
    except Exception as exc:
        logger.error(
            f"[QA Task {task_id}] Error in QA and improvement flow for shloka_id {shloka_id}: {str(exc)}",
            exc_info=True
        )
        
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            retry_delay = min(
                self.default_retry_delay * (2 ** retry_count),
                self.retry_backoff_max
            )
            
            logger.warning(
                f"[QA Task {task_id}] Retrying task (attempt {retry_count + 1}/{self.max_retries}) "
                f"after {retry_delay} seconds. Error: {str(exc)}"
            )
            
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            logger.error(
                f"[QA Task {task_id}] Task failed after {retry_count} retries. "
                f"Giving up on shloka_id {shloka_id}"
            )
            return {
                'success': False,
                'shloka_id': str(shloka_id),
                'error': str(exc),
                'retries': retry_count,
                'message': f'Task failed after {retry_count} retries: {str(exc)}'
            }


@shared_task(
    name='sanatan_app.batch_qa_existing_shlokas',
    bind=True,
)
def batch_qa_existing_shlokas(
    self,
    max_shlokas: Optional[int] = None,
    quality_threshold: int = 95
) -> Dict:
    """
    Batch task for daily QA of existing shlokas.
    
    This implements the "QA for existing Shlokas" flow from the architecture:
    - Runs daily (scheduled via Celery Beat)
    - Checks quality of existing shlokas
    - If not good enough → improves via Groq
    - Re-checks quality after improvement
    - Saves to DB
    
    Args:
        max_shlokas: Maximum number of shlokas to process (None = all)
        quality_threshold: Quality score threshold (default: 95)
        
    Returns:
        Dictionary with batch results:
        - success: bool
        - total_processed: int
        - task_ids: list of individual task IDs
        - message: str
    """
    task_id = self.request.id
    logger.info(
        f"[Batch QA Task {task_id}] Starting batch QA for existing shlokas. "
        f"Max: {max_shlokas}, Threshold: {quality_threshold}"
    )
    
    try:
        from apps.sanatan_app.models import ShlokaExplanation
        
        # Get all explanations (or limit if specified)
        queryset = ShlokaExplanation.objects.all()
        
        if max_shlokas:
            queryset = queryset[:max_shlokas]
        
        explanations = list(queryset)
        total_count = len(explanations)
        
        logger.info(f"[Batch QA Task {task_id}] Found {total_count} explanations to QA")
        
        if total_count == 0:
            return {
                'success': True,
                'total_processed': 0,
                'task_ids': [],
                'message': 'No explanations found'
            }
        
        # Queue individual QA tasks
        task_ids = []
        for explanation in explanations:
            task = qa_and_improve_shloka.delay(
                str(explanation.shloka_id),
                quality_threshold=quality_threshold
            )
            task_ids.append(task.id)
        
        logger.info(
            f"[Batch QA Task {task_id}] Queued {len(task_ids)} QA tasks"
        )
        
        return {
            'success': True,
            'total_processed': total_count,
            'task_ids': task_ids,
            'message': f'Queued {total_count} QA tasks'
        }
        
    except Exception as exc:
        logger.error(
            f"[Batch QA Task {task_id}] Error in batch QA: {str(exc)}",
            exc_info=True
        )
        return {
            'success': False,
            'total_processed': 0,
            'task_ids': [],
            'error': str(exc),
            'message': f'Batch QA task failed: {str(exc)}'
        }


@shared_task(
    name='sanatan_app.create_missing_shlokas_with_explanations',
    bind=True,
    max_retries=3,
    default_retry_delay=120,  # 2 minutes
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,  # Max 30 minutes
    retry_jitter=True,
)
def create_missing_shlokas_with_explanations(
    self,
    book_name: str = "Bhagavad Gita",
    chapter_number: Optional[int] = None,
    chapters: Optional[list] = None,
    batch_size: int = 50,
    max_verses_per_chapter: Optional[int] = None
) -> Dict:
    """
    Celery task to check for missing shlokas and create them with explanations.
    
    This task:
    1. Processes all chapters (1-18 for Bhagavad Gita) or specified chapters
    2. Extracts all shlokas from each chapter using AI
    3. Identifies which shlokas are missing from the database
    4. Creates missing shlokas in batches of 50
    5. Creates explanations for newly created shlokas
    6. Runs quality checks on the explanations
    
    Args:
        book_name: Name of the book (default: "Bhagavad Gita")
        chapter_number: Single chapter number to process (if specified, only this chapter)
        chapters: List of chapter numbers to process (if specified, only these chapters)
                 If both chapter_number and chapters are None, processes all chapters (1-18)
        batch_size: Number of verses to process at a time (default: 50)
        max_verses_per_chapter: Maximum number of verses to process per chapter (None = all missing)
        
    Returns:
        Dictionary with task results:
        - success: bool
        - chapters_processed: list of chapter numbers processed
        - total_missing: int (across all chapters)
        - created_shlokas: int (across all chapters)
        - created_explanations: int (across all chapters)
        - quality_checked: int (across all chapters)
        - errors: int (across all chapters)
        - chapter_results: dict with results per chapter
        - message: str
    """
    task_id = self.request.id
    
    # Determine which chapters to process
    if chapter_number is not None:
        chapters_to_process = [chapter_number]
    elif chapters is not None:
        chapters_to_process = chapters
    else:
        # Default: process all chapters (1-18 for Bhagavad Gita)
        chapters_to_process = list(range(1, 19))
    
    logger.info(
        f"[Create Shlokas Task {task_id}] Starting task for {book_name}. "
        f"Chapters: {chapters_to_process}, Batch size: {batch_size}, "
        f"Max verses per chapter: {max_verses_per_chapter or 'all'}"
    )
    
    try:
        from apps.sanatan_app.models import Shloka, ShlokaExplanation
        from apps.sanatan_app.services.shloka_service import ShlokaService
        from apps.sanatan_app.services.book_context_service import BookContextService
        from django.db import transaction
        import time
        
        shloka_service = ShlokaService()
        book_context_service = BookContextService()
        
        # Step 1: Load PDF
        logger.info(f"[Task {task_id}] Step 1: Loading PDF...")
        
        if not book_context_service.english_book_path.exists():
            error_msg = f"PDF not found: {book_context_service.english_book_path}"
            logger.error(f"[Task {task_id}] {error_msg}")
            return {
                'success': False,
                'chapters_processed': [],
                'error': error_msg,
                'message': error_msg
            }
        
        pdf_reader = book_context_service._load_pdf(book_context_service.english_book_path)
        if not pdf_reader:
            error_msg = "Failed to load PDF"
            logger.error(f"[Task {task_id}] {error_msg}")
            return {
                'success': False,
                'chapters_processed': [],
                'error': error_msg,
                'message': error_msg
            }
        
        total_pages = len(pdf_reader.pages)
        
        # Aggregate results across all chapters
        total_missing_all = 0
        total_created_shlokas = 0
        total_created_explanations = 0
        total_quality_checked = 0
        total_errors = 0
        all_quality_task_ids = []
        chapter_results = {}
        
        # Process each chapter
        for chapter_number in chapters_to_process:
            logger.info(f"[Task {task_id}] ========================================")
            logger.info(f"[Task {task_id}] Processing Chapter {chapter_number}")
            logger.info(f"[Task {task_id}] ========================================")
            
            try:
                # Find chapter start page
                chapter_start_page = None
                
                # Search for chapter marker
                for page_num in range(max(0, (chapter_number - 1) * 15 - 10), min((chapter_number - 1) * 15 + 30, total_pages)):
                    try:
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text()
                        if page_text and (f'Chapter {chapter_number}' in page_text or f'CHAPTER {chapter_number}' in page_text):
                            # Check if it's actual content (has Devanagari or VERSE)
                            has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in page_text)
                            has_verse = 'VERSE' in page_text or 'verse' in page_text.lower()
                            if has_devanagari or has_verse:
                                chapter_start_page = page_num
                                logger.info(f"[Task {task_id}] Found Chapter {chapter_number} at page {page_num}")
                                break
                    except:
                        continue
                
                if chapter_start_page is None:
                    chapter_start_page = (chapter_number - 1) * 15
                    logger.warning(f"[Task {task_id}] Could not find chapter start page, using estimated page {chapter_start_page}")
                
                # Extract chapter text
                start_page = chapter_start_page
                end_page = min(chapter_start_page + 25, total_pages)
                raw_chapter_text = book_context_service._extract_text_from_pdf(
                    pdf_reader, (start_page, end_page)
                )
                
                if not raw_chapter_text:
                    logger.warning(f"[Task {task_id}] No text extracted from Chapter {chapter_number}, skipping")
                    chapter_results[chapter_number] = {
                        'success': False,
                        'error': 'No text extracted',
                        'created_shlokas': 0,
                        'created_explanations': 0
                    }
                    continue
                
                chapter_text = shloka_service._clean_pdf_text(raw_chapter_text)
                logger.info(f"[Task {task_id}] Extracted {len(chapter_text)} characters from Chapter {chapter_number}")
                
                # Extract all shlokas from chapter using AI
                logger.info(f"[Task {task_id}] Extracting shlokas from Chapter {chapter_number} using AI...")
                all_shlokas_data = shloka_service._extract_shlokas_with_ai(
                    chapter_text, chapter_number, max_shlokas=200  # Large number to get all
                )
                
                if not all_shlokas_data:
                    logger.warning(f"[Task {task_id}] No shlokas extracted from Chapter {chapter_number}, skipping")
                    chapter_results[chapter_number] = {
                        'success': False,
                        'error': 'No shlokas extracted',
                        'created_shlokas': 0,
                        'created_explanations': 0
                    }
                    continue
                
                logger.info(f"[Task {task_id}] Extracted {len(all_shlokas_data)} shlokas from Chapter {chapter_number}")
                
                # Identify missing shlokas
                existing_shlokas = set(
                    Shloka.objects.filter(
                        book_name=book_name,
                        chapter_number=chapter_number
                    ).values_list('verse_number', flat=True)
                )
                
                missing_shlokas = []
                for shloka_data in all_shlokas_data:
                    verse_num = shloka_data.get('verse_number')
                    if verse_num and verse_num not in existing_shlokas:
                        missing_shlokas.append(shloka_data)
                
                chapter_missing = len(missing_shlokas)
                total_missing_all += chapter_missing
                logger.info(f"[Task {task_id}] Found {chapter_missing} missing shlokas out of {len(all_shlokas_data)} total in Chapter {chapter_number}")
                
                if chapter_missing == 0:
                    logger.info(f"[Task {task_id}] All shlokas already exist for Chapter {chapter_number}")
                    chapter_results[chapter_number] = {
                        'success': True,
                        'total_missing': 0,
                        'created_shlokas': 0,
                        'created_explanations': 0,
                        'quality_checked': 0,
                        'errors': 0
                    }
                    continue
                
                # Limit to max_verses_per_chapter if specified
                if max_verses_per_chapter:
                    missing_shlokas = missing_shlokas[:max_verses_per_chapter]
                    logger.info(f"[Task {task_id}] Limited to {len(missing_shlokas)} shlokas (max_verses_per_chapter={max_verses_per_chapter})")
                
                # Process in batches
                chapter_created_shlokas = 0
                chapter_created_explanations = 0
                chapter_quality_checked = 0
                chapter_errors = 0
                chapter_quality_task_ids = []
                
                for batch_start in range(0, len(missing_shlokas), batch_size):
                    batch_end = min(batch_start + batch_size, len(missing_shlokas))
                    batch = missing_shlokas[batch_start:batch_end]
                    
                    logger.info(
                        f"[Task {task_id}] Chapter {chapter_number}, batch {batch_start // batch_size + 1}: "
                        f"verses {batch_start + 1}-{batch_end} ({len(batch)} shlokas)"
                    )
                    
                    for shloka_data in batch:
                        try:
                            verse_num = shloka_data.get('verse_number')
                            chapter_num_extracted = shloka_data.get('chapter_number', chapter_number)
                            
                            # Ensure integers
                            try:
                                if chapter_num_extracted is not None:
                                    chapter_num_extracted = int(chapter_num_extracted)
                                if verse_num is not None:
                                    verse_num = int(verse_num)
                            except (ValueError, TypeError):
                                logger.warning(f"[Task {task_id}] Invalid verse/chapter number, skipping")
                                chapter_errors += 1
                                continue
                            
                            # Clean text
                            raw_sanskrit = shloka_data.get('sanskrit_text', '')
                            raw_transliteration = shloka_data.get('transliteration', '')
                            
                            cleaned_sanskrit = shloka_service._clean_pdf_text(raw_sanskrit) if raw_sanskrit else ''
                            cleaned_transliteration = shloka_service._clean_pdf_text(raw_transliteration) if raw_transliteration else ''
                            
                            # Validate Sanskrit text
                            has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in cleaned_sanskrit) if cleaned_sanskrit else False
                            has_corrupted = any(0xE000 <= ord(c) <= 0xF8FF for c in cleaned_sanskrit) if cleaned_sanskrit else False
                            
                            if has_corrupted or not cleaned_sanskrit or not has_devanagari:
                                logger.warning(f"[Task {task_id}] Invalid Sanskrit text for Chapter {chapter_number}, Verse {verse_num}, skipping")
                                chapter_errors += 1
                                continue
                            
                            if not verse_num or verse_num < 1 or not chapter_num_extracted or chapter_num_extracted < 1:
                                logger.warning(f"[Task {task_id}] Invalid verse/chapter number, skipping")
                                chapter_errors += 1
                                continue
                            
                            transliteration_value = None
                            if cleaned_transliteration and cleaned_transliteration.strip():
                                transliteration_value = cleaned_transliteration.strip()
                            
                            # Create shloka
                            with transaction.atomic():
                                shloka, created = Shloka.objects.get_or_create(
                                    book_name=book_name,
                                    chapter_number=chapter_num_extracted,
                                    verse_number=verse_num,
                                    defaults={
                                        'sanskrit_text': cleaned_sanskrit.strip(),
                                        'transliteration': transliteration_value,
                                    }
                                )
                                
                                if created:
                                    chapter_created_shlokas += 1
                                    logger.info(f"[Task {task_id}] Created shloka: Chapter {chapter_num_extracted}, Verse {verse_num}")
                                    
                                    # Create explanation
                                    try:
                                        explanation = shloka_service.generate_and_store_explanation(shloka)
                                        if explanation:
                                            chapter_created_explanations += 1
                                            logger.info(f"[Task {task_id}] Created explanation for Chapter {chapter_num_extracted}, Verse {verse_num}")
                                            
                                            # Queue quality check task
                                            quality_task = check_shloka_quality.delay(str(shloka.id))
                                            chapter_quality_task_ids.append(quality_task.id)
                                            chapter_quality_checked += 1
                                        else:
                                            logger.warning(f"[Task {task_id}] Failed to create explanation for Chapter {chapter_number}, Verse {verse_num}")
                                            chapter_errors += 1
                                    except Exception as e:
                                        logger.error(f"[Task {task_id}] Error creating explanation: {str(e)}")
                                        chapter_errors += 1
                                else:
                                    logger.debug(f"[Task {task_id}] Shloka already exists: Chapter {chapter_num_extracted}, Verse {verse_num}")
                            
                            # Small delay to avoid rate limiting
                            time.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"[Task {task_id}] Error processing shloka: {str(e)}", exc_info=True)
                            chapter_errors += 1
                            continue
                    
                    # Delay between batches
                    if batch_end < len(missing_shlokas):
                        logger.info(f"[Task {task_id}] Waiting 5 seconds before next batch...")
                        time.sleep(5)
                
                # Update totals
                total_created_shlokas += chapter_created_shlokas
                total_created_explanations += chapter_created_explanations
                total_quality_checked += chapter_quality_checked
                total_errors += chapter_errors
                all_quality_task_ids.extend(chapter_quality_task_ids)
                
                chapter_results[chapter_number] = {
                    'success': True,
                    'total_missing': chapter_missing,
                    'created_shlokas': chapter_created_shlokas,
                    'created_explanations': chapter_created_explanations,
                    'quality_checked': chapter_quality_checked,
                    'errors': chapter_errors
                }
                
                logger.info(
                    f"[Task {task_id}] Chapter {chapter_number} completed: "
                    f"Created {chapter_created_shlokas} shlokas, {chapter_created_explanations} explanations"
                )
                
                # Delay between chapters
                if chapter_number != chapters_to_process[-1]:
                    logger.info(f"[Task {task_id}] Waiting 10 seconds before next chapter...")
                    time.sleep(10)
                
            except Exception as e:
                logger.error(f"[Task {task_id}] Error processing Chapter {chapter_number}: {str(e)}", exc_info=True)
                chapter_results[chapter_number] = {
                    'success': False,
                    'error': str(e),
                    'created_shlokas': 0,
                    'created_explanations': 0
                }
                total_errors += 1
                continue
        
        logger.info(
            f"[Task {task_id}] All chapters completed. Total: {total_created_shlokas} shlokas, "
            f"{total_created_explanations} explanations, {total_quality_checked} quality checks queued"
        )
        
        return {
            'success': True,
            'chapters_processed': chapters_to_process,
            'total_missing': total_missing_all,
            'created_shlokas': total_created_shlokas,
            'created_explanations': total_created_explanations,
            'quality_checked': total_quality_checked,
            'quality_task_ids': all_quality_task_ids,
            'errors': total_errors,
            'chapter_results': chapter_results,
            'message': f'Processed {len(chapters_to_process)} chapters. Created {total_created_shlokas} shlokas with {total_created_explanations} explanations'
        }
        
    except Exception as exc:
        logger.error(
            f"[Task {task_id}] Error creating missing shlokas: {str(exc)}",
            exc_info=True
        )
        
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            retry_delay = min(
                self.default_retry_delay * (2 ** retry_count),
                self.retry_backoff_max
            )
            
            logger.warning(
                f"[Task {task_id}] Retrying task (attempt {retry_count + 1}/{self.max_retries}) "
                f"after {retry_delay} seconds. Error: {str(exc)}"
            )
            
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            logger.error(
                f"[Task {task_id}] Task failed after {retry_count} retries"
            )
            return {
                'success': False,
                'chapters_processed': chapters_to_process if 'chapters_to_process' in locals() else [],
                'error': str(exc),
                'retries': retry_count,
                'message': f'Task failed after {retry_count} retries: {str(exc)}'
            }

