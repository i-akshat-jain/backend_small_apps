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
            # generate_explanation returns (explanation_text, prompt, structured_data)
            explanation_text, prompt, structured_data = self.groq_service.generate_explanation(
                shloka_dict, explanation_type
            )
            
            # Save word_by_word to Shloka model if present
            # Word-by-word is stored only in the Shloka model, not in explanations
            word_by_word = structured_data.get('word_by_word') if structured_data else None
            if word_by_word:
                shloka.word_by_word = word_by_word
                shloka.save(update_fields=['word_by_word', 'updated_at'])
            
            # Remove WORD-BY-WORD section from explanation_text before saving
            # Word-by-word is stored only in the Shloka model, not in explanations
            explanation_text_cleaned = self._remove_word_by_word_section(explanation_text)
            
            # Create new explanation
            explanation = ShlokaExplanation.objects.create(
                shloka=shloka,
                explanation_type=explanation_type,
                explanation_text=explanation_text_cleaned,
                ai_model_used=self.groq_service.model,
                generation_prompt=prompt,
            )
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating and storing explanation: {str(e)}")
            raise
    
    def _remove_word_by_word_section(self, explanation_text):
        """
        Remove the WORD-BY-WORD section from explanation text.
        
        Word-by-word breakdown is stored only in the Shloka model, not in explanations.
        This method removes the WORD-BY-WORD section from the explanation text before saving.
        
        Args:
            explanation_text: The full explanation text that may contain WORD-BY-WORD section
            
        Returns:
            Explanation text with WORD-BY-WORD section removed
        """
        if not explanation_text:
            return explanation_text
        
        import re
        
        # Use the same section extraction logic as groq_service to find and remove WORD-BY-WORD section
        lines = explanation_text.split('\n')
        cleaned_lines = []
        skip_until_next_section = False
        
        for line in lines:
            # Check if this line starts a WORD-BY-WORD section
            # Match patterns like "2. WORD-BY-WORD:", "WORD-BY-WORD:", "2. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN:", etc.
            line_upper = line.upper().strip()
            is_word_by_word_header = (
                re.match(r'^\d+\.\s*WORD[-‑\s]*BY[-‑\s]*WORD', line_upper) or
                re.match(r'^WORD[-‑\s]*BY[-‑\s]*WORD', line_upper) or
                'WORD-BY-WORD' in line_upper or
                'WORD BY WORD' in line_upper or
                'STATEMENT-BY-STATEMENT' in line_upper
            )
            
            if is_word_by_word_header:
                # Start of WORD-BY-WORD section - skip it and all following lines until next section
                skip_until_next_section = True
                continue
            
            # If we're skipping (in WORD-BY-WORD section), check if we've reached the next section
            if skip_until_next_section:
                # Check if this is a new section header (starts with number and colon, or just uppercase text with colon)
                # But make sure it's not another WORD-BY-WORD variant
                line_upper_check = line.upper().strip()
                is_another_word_by_word = (
                    'WORD-BY-WORD' in line_upper_check or
                    'WORD BY WORD' in line_upper_check or
                    'STATEMENT-BY-STATEMENT' in line_upper_check
                )
                
                if not is_another_word_by_word:
                    # Check if this looks like a section header
                    is_new_section = (
                        re.match(r'^\d+\.\s+[A-Z][A-Z\s/-—\-‑]+:', line) or
                        re.match(r'^[A-Z][A-Z\s/-—\-‑]+:', line)
                    )
                    if is_new_section:
                        # We've reached the next section, stop skipping and include this line
                        skip_until_next_section = False
                        cleaned_lines.append(line)
                # Otherwise, continue skipping lines in the WORD-BY-WORD section
                continue
            
            # Not in WORD-BY-WORD section, keep the line
            cleaned_lines.append(line)
        
        # Join lines back together
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Clean up any double newlines that might have been created
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        
        # Remove trailing whitespace from each line
        cleaned_lines_final = [line.rstrip() for line in cleaned_text.split('\n')]
        cleaned_text = '\n'.join(cleaned_lines_final)
        
        return cleaned_text.strip()

