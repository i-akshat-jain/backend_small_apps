"""Services for Sanatan App."""
from django.db.models import Count, F
from django.core.exceptions import ObjectDoesNotExist
from .models import Shloka, ShlokaExplanation, ReadingType
from .groq_service import GroqService
import logging
import random

logger = logging.getLogger(__name__)


class ShlokaService:
    """Service for managing shlokas and their explanations."""
    
    def __init__(self):
        self.groq_service = GroqService()
    
    def get_random_shloka(self):
        """
        Get a random shloka with both summary and detailed explanations.
        
        Returns:
            dict: ShlokaResponse with shloka, summary, and detailed explanations
        """
        try:
            # Get total count
            total_count = Shloka.objects.count()
            
            if total_count == 0:
                raise Exception(
                    "No shlokas found in database. Please add shlokas using the command: "
                    "python manage.py add_sample_shlokas"
                )
            
            # Get random shloka
            shloka = Shloka.objects.order_by('?').first()
            
            if shloka is None:
                raise Exception("Failed to fetch random shloka")
            
            # Get or generate both summary and detailed explanations
            # These may return None if generation fails due to connection errors
            summary = self.get_explanation(shloka.id, ReadingType.SUMMARY)
            detailed = self.get_explanation(shloka.id, ReadingType.DETAILED)
            
            return {
                'shloka': shloka,
                'summary': summary,
                'detailed': detailed,
            }
            
        except Exception as e:
            logger.error(f"Error getting random shloka: {str(e)}")
            raise
    
    def get_shloka_by_id(self, shloka_id):
        """
        Get shloka by ID with both summary and detailed explanations.
        
        Args:
            shloka_id: UUID of the shloka
            
        Returns:
            dict: ShlokaResponse with shloka, summary, and detailed explanations
        """
        try:
            shloka = Shloka.objects.get(id=shloka_id)
            
            # Get or generate both summary and detailed explanations
            # These may return None if generation fails due to connection errors
            summary = self.get_explanation(shloka_id, ReadingType.SUMMARY)
            detailed = self.get_explanation(shloka_id, ReadingType.DETAILED)
            
            return {
                'shloka': shloka,
                'summary': summary,
                'detailed': detailed,
            }
        except Shloka.DoesNotExist:
            raise Exception(f"Shloka with ID {shloka_id} not found")
        except Exception as e:
            logger.error(f"Error getting shloka by ID: {str(e)}")
            raise
    
    def get_explanation(self, shloka_id, explanation_type=ReadingType.SUMMARY):
        """
        Get explanation for a shloka, generating if it doesn't exist.
        
        Args:
            shloka_id: UUID of the shloka
            explanation_type: Either ReadingType.SUMMARY or ReadingType.DETAILED
            
        Returns:
            ShlokaExplanation object or None (None if generation fails due to connection errors)
        """
        # Try to get existing explanation
        explanation = self._get_explanation(shloka_id, explanation_type)
        
        if explanation is None:
            # Get shloka data
            try:
                shloka = Shloka.objects.get(id=shloka_id)
            except Shloka.DoesNotExist:
                raise Exception(f"Shloka with ID {shloka_id} not found")
            
            # Generate and store explanation
            # If generation fails due to connection errors, return None instead of raising
            try:
                explanation = self._generate_and_store_explanation(shloka, explanation_type)
            except Exception as e:
                error_msg = str(e).lower()
                # If it's a connection error, log it but don't fail the entire request
                if "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                    logger.warning(f"Failed to generate explanation due to connection issue: {str(e)}. Returning None.")
                    return None
                # For other errors, re-raise them
                raise
        
        return explanation
    
    def _get_explanation(self, shloka_id, explanation_type):
        """Get existing explanation from database."""
        try:
            # Use filter().first() to handle potential duplicates gracefully
            explanation = ShlokaExplanation.objects.filter(
                shloka_id=shloka_id,
                explanation_type=explanation_type
            ).first()
            return explanation
        except Exception as e:
            logger.error(f"Error getting explanation: {str(e)}")
            return None
    
    def _generate_and_store_explanation(self, shloka, explanation_type):
        """Generate explanation using Groq and store in database."""
        try:
            # Convert shloka to dict for Groq service
            shloka_dict = {
                "book_name": shloka.book_name,
                "chapter_number": shloka.chapter_number,
                "verse_number": shloka.verse_number,
                "sanskrit_text": shloka.sanskrit_text,
                "transliteration": shloka.transliteration or "",
            }
            
            # Generate explanation
            explanation_text, prompt = self.groq_service.generate_explanation(
                shloka_dict, explanation_type
            )
            
            # Create new explanation
            explanation = ShlokaExplanation.objects.create(
                shloka=shloka,
                explanation_type=explanation_type,
                explanation_text=explanation_text,
                ai_model_used=self.groq_service.model,
                generation_prompt=prompt,
            )
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating and storing explanation: {str(e)}")
            raise

