"""Shloka Service for managing shlokas and their explanations."""
from django.db.models import Count, F, Q
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import timedelta
from ..models import Shloka, ShlokaExplanation, ReadingType, ShlokaReadStatus
from ..groq_service import GroqService
from .book_context_service import BookContextService
from pathlib import Path
import logging
import random
import json
import re
import unicodedata

logger = logging.getLogger(__name__)


class ShlokaService:
    """Service for managing shlokas and their explanations."""
    
    def __init__(self):
        # GroqService and BookContextService are only used for PDF extraction of new shlokas
        # Explanations are now pre-generated and stored in the database, not generated on-demand
        self.groq_service = GroqService()
        self.book_context_service = BookContextService()
    
    def get_random_shloka(self, user=None):
        """
        Get a random shloka with both summary and detailed explanations.
        
        If user is provided:
        - Excludes shlokas that user has marked as read
        - Shows unread shlokas that were last shown more than 3 days ago
        - Automatically extracts new shlokas from PDFs if fewer than 5 unread shlokas available
        
        Args:
            user: Optional User object to filter based on read status
        
        Returns:
            dict: ShlokaResponse with shloka, summary, and detailed explanations
        """
        try:
            # If user is provided, check if we need to extract more shlokas dynamically
            if user:
                # Get shlokas that user has marked as read
                read_shloka_ids = ShlokaReadStatus.objects.filter(
                    user=user
                ).values_list('shloka_id', flat=True)
                
                # Count how many shlokas user has read
                read_count = len(read_shloka_ids)
                
                # Count unread shlokas
                unread_count = Shloka.objects.exclude(id__in=read_shloka_ids).count()
                
                # Dynamic extraction: For every 5 shlokas read, ensure we have at least 5 unread shlokas available
                # This keeps the content fresh and incremental
                if read_count > 0:
                    # Calculate how many unread shlokas we should have based on read count
                    # For every 5 read, we want at least 5 unread available
                    target_unread = max(5, (read_count // 5) * 5)
                    
                    # If we have fewer unread than target, extract more
                    if unread_count < target_unread:
                        shlokas_to_extract = target_unread - unread_count
                        logger.info(
                            f"User {user.id} has read {read_count} shlokas. "
                            f"Current unread: {unread_count}, target: {target_unread}. "
                            f"Extracting {shlokas_to_extract} new shlokas from PDFs..."
                        )
                        try:
                            self._extract_new_shlokas_from_pdfs(user, num_shlokas=shlokas_to_extract)
                        except Exception as e:
                            logger.warning(f"Failed to extract new shlokas: {str(e)}")
                            # Continue anyway - we'll use existing shlokas
                elif unread_count < 5:
                    # Initial case: if no shlokas read yet but we have very few unread, extract some
                    logger.info(f"User {user.id} has {unread_count} unread shlokas. Extracting initial batch...")
                    try:
                        self._extract_new_shlokas_from_pdfs(user, num_shlokas=10)
                    except Exception as e:
                        logger.warning(f"Failed to extract new shlokas: {str(e)}")
                        # Continue anyway - we'll use existing shlokas
            
            # Get total count
            total_count = Shloka.objects.count()
            
            if total_count == 0:
                # Try to extract initial shlokas
                logger.info("No shlokas in database. Extracting initial shlokas from PDFs...")
                try:
                    self._extract_new_shlokas_from_pdfs(user)
                    total_count = Shloka.objects.count()
                except Exception as e:
                    logger.error(f"Failed to extract initial shlokas: {str(e)}")
                    raise Exception("No shlokas found in database and failed to extract from PDFs.")
            
            # If user is provided, filter out read shlokas
            if user:
                # Get shlokas that user has marked as read
                read_shloka_ids = ShlokaReadStatus.objects.filter(
                    user=user
                ).values_list('shloka_id', flat=True)
                
                # Get unread shlokas or shlokas shown more than 3 days ago
                three_days_ago = timezone.now() - timedelta(days=3)
                
                # Query for unread shlokas
                unread_shlokas = Shloka.objects.exclude(id__in=read_shloka_ids)
                
                # Also include shlokas that were last shown more than 3 days ago
                old_shown_shlokas = Shloka.objects.filter(
                    read_by_users__user=user,
                    read_by_users__last_shown_at__lt=three_days_ago
                )
                
                # Combine both queries
                available_shlokas = (unread_shlokas | old_shown_shlokas).distinct()
                
                if available_shlokas.exists():
                    # Get random from available shlokas
                    shloka = available_shlokas.order_by('?').first()
                else:
                    # All shlokas are read and recently shown, return random anyway
                    shloka = Shloka.objects.order_by('?').first()
            else:
                # No user provided, return completely random
                shloka = Shloka.objects.order_by('?').first()
            
            if shloka is None:
                raise Exception("Failed to fetch random shloka")
            
            # Update last_shown_at if user is provided
            if user:
                ShlokaReadStatus.objects.update_or_create(
                    user=user,
                    shloka=shloka,
                    defaults={'last_shown_at': timezone.now()}
                )
            
            # Get explanations directly from database (pre-generated)
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
            
            # Get explanations directly from database (pre-generated)
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
        Get explanation for a shloka from database.
        
        Explanations are now pre-generated and stored in the database.
        This method only fetches existing explanations, it does not generate them.
        
        Args:
            shloka_id: UUID of the shloka
            explanation_type: Either ReadingType.SUMMARY or ReadingType.DETAILED
            
        Returns:
            ShlokaExplanation object or None if explanation doesn't exist
        """
        return self._get_explanation(shloka_id, explanation_type)
    
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
    
    def generate_and_store_explanation(self, shloka, explanation_type):
        """
        Generate explanation using Groq and store in database.
        
        Args:
            shloka: Shloka model instance
            explanation_type: Either ReadingType.SUMMARY or ReadingType.DETAILED
            
        Returns:
            ShlokaExplanation object or None if generation failed
        """
        try:
            # Convert explanation_type to string format expected by GroqService
            explanation_type_str = explanation_type.lower() if hasattr(explanation_type, 'lower') else str(explanation_type).lower()
            
            # Convert shloka to dict for Groq service
            shloka_dict = {
                "book_name": shloka.book_name,
                "chapter_number": shloka.chapter_number,
                "verse_number": shloka.verse_number,
                "sanskrit_text": shloka.sanskrit_text,
                "transliteration": shloka.transliteration or "",
            }
            
            # Get book context from PDFs (English and Hindi translations)
            book_context = None
            try:
                if shloka.chapter_number and shloka.verse_number:
                    book_context = self.book_context_service.get_context_for_shloka(
                        book_name=shloka.book_name,
                        chapter_number=shloka.chapter_number,
                        verse_number=shloka.verse_number,
                        include_hindi=True,
                        include_english=True
                    )
                    if not book_context.get('english_context') and not book_context.get('hindi_context'):
                        book_context = None
            except Exception as e:
                logger.warning(f"Failed to extract book context for shloka {shloka.id}: {str(e)}")
                book_context = None
            
            # Generate explanation with book context
            try:
                explanation_text, prompt, structured_data = self.groq_service.generate_explanation(
                    shloka_dict, explanation_type_str, book_context=book_context
                )
            except Exception as e:
                logger.error(
                    f"Failed to generate explanation for shloka {shloka.id} "
                    f"(type: {explanation_type}): {str(e)}"
                )
                # Don't raise - return None so the process can continue with other shlokas
                return None
            
            # Validate that we got a non-empty explanation
            if not explanation_text or len(explanation_text.strip()) < 50:
                logger.warning(
                    f"Generated explanation is empty or too short for shloka {shloka.id} "
                    f"(type: {explanation_type}). Length: {len(explanation_text) if explanation_text else 0}. "
                    f"Skipping this explanation."
                )
                return None
            
            # Save word_by_word to Shloka model (only once, prefer detailed if available)
            word_by_word = structured_data.get('word_by_word')
            if word_by_word:
                # Prefer detailed explanation's word_by_word, but update if shloka doesn't have it yet
                # or if this is a detailed explanation (more comprehensive)
                if explanation_type == ReadingType.DETAILED or not shloka.word_by_word:
                    shloka.word_by_word = word_by_word
                    shloka.save(update_fields=['word_by_word', 'updated_at'])
                    logger.debug(f"Saved word_by_word to shloka {shloka.id} from {explanation_type} explanation")
            
            # Remove WORD-BY-WORD section from explanation_text before saving
            # Word-by-word is stored only in the Shloka model, not in explanations
            explanation_text_cleaned = self._remove_word_by_word_section(explanation_text)
            
            # Use update_or_create to handle both new and existing explanations
            # This allows the command to regenerate explanations without deleting first
            explanation, created = ShlokaExplanation.objects.update_or_create(
                shloka=shloka,
                explanation_type=explanation_type,
                defaults={
                    'explanation_text': explanation_text_cleaned,
                    'ai_model_used': self.groq_service.model,
                    'generation_prompt': prompt,
                    'why_this_matters': structured_data.get('why_this_matters'),
                    'context': structured_data.get('context'),
                    'modern_examples': structured_data.get('modern_examples'),
                    'themes': structured_data.get('themes'),
                    'reflection_prompt': structured_data.get('reflection_prompt'),
                }
            )
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating and storing explanation for shloka {shloka.id}: {str(e)}")
            logger.exception(e)
            return None
    
    def mark_shloka_as_read(self, user, shloka_id):
        """
        Mark a shloka as read for a user.
        
        Args:
            user: User object
            shloka_id: UUID of the shloka to mark as read
            
        Returns:
            ShlokaReadStatus object
        """
        try:
            shloka = Shloka.objects.get(id=shloka_id)
            
            # Create or update read status
            read_status, created = ShlokaReadStatus.objects.update_or_create(
                user=user,
                shloka=shloka,
                defaults={
                    'marked_read_at': timezone.now(),
                    'last_shown_at': timezone.now()
                }
            )
            
            return read_status
        except Shloka.DoesNotExist:
            raise Exception(f"Shloka with ID {shloka_id} not found")
        except Exception as e:
            logger.error(f"Error marking shloka as read: {str(e)}")
            raise
    
    def unmark_shloka_as_read(self, user, shloka_id):
        """
        Unmark a shloka as read (remove from read list).
        
        Args:
            user: User object
            shloka_id: UUID of the shloka to unmark
            
        Returns:
            True if removed, False if not found
        """
        try:
            deleted_count, _ = ShlokaReadStatus.objects.filter(
                user=user,
                shloka_id=shloka_id
            ).delete()
            
            return deleted_count > 0
        except Exception as e:
            logger.error(f"Error unmarking shloka as read: {str(e)}")
            raise
    
    def _extract_new_shlokas_from_pdfs(self, user=None, num_shlokas=10):
        """
        Extract new shlokas from PDF books using AI and save to database.
        
        This method is called automatically when a user needs more shlokas.
        It extracts shlokas from the English PDF book and saves them.
        Uses multiple chapters to ensure variety.
        
        Args:
            user: Optional user object (for logging)
            num_shlokas: Number of shlokas to extract (default: 10)
        """
        try:
            # Get existing shlokas to avoid duplicates
            existing_shlokas = set(
                Shloka.objects.values_list('chapter_number', 'verse_number')
            )
            
            # Load English PDF (primary source)
            book_path = self.book_context_service.english_book_path
            if not book_path.exists():
                logger.warning(f"PDF book not found: {book_path}")
                return
            
            pdf_reader = self.book_context_service._load_pdf(book_path)
            if not pdf_reader:
                logger.warning("Failed to load PDF")
                return
            
            # Get all chapters (1-18 for Bhagavad Gita)
            all_chapters = list(range(1, 19))
            
            # Find chapters with fewest shlokas to ensure variety
            chapter_counts = {}
            for ch in all_chapters:
                chapter_counts[ch] = Shloka.objects.filter(chapter_number=ch).count()
            
            # Sort chapters by count (ascending) to prioritize chapters with fewer shlokas
            sorted_chapters = sorted(chapter_counts.items(), key=lambda x: x[1])
            
            # Try to extract from multiple chapters for variety
            # Extract from 2-3 chapters to get diverse content
            chapters_to_try = [ch for ch, count in sorted_chapters[:3]]
            
            added_count = 0
            shlokas_per_chapter = max(3, num_shlokas // len(chapters_to_try))
            
            for target_chapter in chapters_to_try:
                if added_count >= num_shlokas:
                    break
                
                # Extract chapter text - try to find actual chapter content
                # Search for pages with "Chapter X" or "VERSE" patterns
                estimated_start_page = (target_chapter - 1) * 15
                estimated_end_page = target_chapter * 15 + 5
                
                # First, try to find the actual chapter start page
                chapter_start_page = None
                for page_num in range(max(0, estimated_start_page - 5), min(estimated_end_page + 5, len(pdf_reader.pages))):
                    try:
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text()
                        if page_text and (f'Chapter {target_chapter}' in page_text or f'CHAPTER {target_chapter}' in page_text):
                            chapter_start_page = page_num
                            logger.info(f"Found Chapter {target_chapter} starting at page {page_num}")
                            break
                    except:
                        continue
                
                # Use found page or fallback to estimated
                if chapter_start_page is not None:
                    start_page = chapter_start_page
                    end_page = min(chapter_start_page + 20, len(pdf_reader.pages))
                else:
                    start_page = estimated_start_page
                    end_page = estimated_end_page
                
                raw_chapter_text = self.book_context_service._extract_text_from_pdf(
                    pdf_reader, (start_page, end_page)
                )
                
                if not raw_chapter_text:
                    logger.warning(f"No text extracted for chapter {target_chapter}")
                    continue
                
                # Clean the extracted text
                logger.info(f"Extracting from Chapter {target_chapter} (pages {start_page}-{end_page}) - Raw text length: {len(raw_chapter_text)} chars")
                chapter_text = self._clean_pdf_text(raw_chapter_text)
                logger.info(f"After cleaning - Text length: {len(chapter_text)} chars")
                
                # Check if we have actual shloka content (look for Devanagari or VERSE patterns)
                has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in chapter_text)
                has_verse = 'VERSE' in chapter_text or 'verse' in chapter_text.lower()
                
                if not has_devanagari and not has_verse:
                    logger.warning(f"Chapter {target_chapter} text doesn't appear to contain shloka content (no Devanagari or VERSE markers)")
                    # Log sample to help debug
                    sample_text = chapter_text[:500] if len(chapter_text) > 500 else chapter_text
                    logger.info(f"Text sample: {sample_text}")
                    continue
                
                # Log a sample of the text (first 300 chars) to verify extraction
                sample_text = chapter_text[:300] if len(chapter_text) > 300 else chapter_text
                logger.info(f"Text sample (first 300 chars): {sample_text}")
                
                # Calculate how many more shlokas we need
                remaining_needed = num_shlokas - added_count
                shlokas_to_extract = min(shlokas_per_chapter, remaining_needed)
                
                # Use AI to extract shlokas from this chapter
                logger.info(f"Calling AI to extract {shlokas_to_extract} shlokas from Chapter {target_chapter}")
                shlokas_data = self._extract_shlokas_with_ai(
                    chapter_text, target_chapter, shlokas_to_extract
                )
                logger.info(f"AI returned {len(shlokas_data)} shlokas from Chapter {target_chapter}")
                
                # Save new shlokas to database
                for idx, shloka_data in enumerate(shlokas_data, 1):
                    if added_count >= num_shlokas:
                        break
                    
                    chapter_num = shloka_data.get('chapter_number')
                    verse_num = shloka_data.get('verse_number')
                    raw_sanskrit = shloka_data.get('sanskrit_text', '')
                    raw_transliteration = shloka_data.get('transliteration', '')
                    
                    # Skip if already exists
                    if (chapter_num, verse_num) in existing_shlokas:
                        logger.info(f"  Shloka {idx}: Chapter {chapter_num}, Verse {verse_num} - Already exists, skipping")
                        continue
                    
                    # Clean the text before saving
                    cleaned_sanskrit = self._clean_pdf_text(raw_sanskrit) if raw_sanskrit else ''
                    cleaned_transliteration = self._clean_pdf_text(raw_transliteration) if raw_transliteration else ''
                    
                    # Validate: Check for corrupted characters and proper Devanagari
                    has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in cleaned_sanskrit) if cleaned_sanskrit else False
                    has_corrupted = any(0xE000 <= ord(c) <= 0xF8FF for c in cleaned_sanskrit) if cleaned_sanskrit else False
                    
                    # Skip if corrupted or no valid Devanagari
                    if has_corrupted:
                        logger.warning(f"  Shloka {idx}: Chapter {chapter_num}, Verse {verse_num} - SKIPPED (has corrupted characters)")
                        logger.warning(f"    Sanskrit preview: {cleaned_sanskrit[:80]}...")
                        continue
                    
                    if cleaned_sanskrit and not has_devanagari:
                        logger.warning(f"  Shloka {idx}: Chapter {chapter_num}, Verse {verse_num} - SKIPPED (no Devanagari characters)")
                        continue
                    
                    # Log the cleaned text for verification
                    logger.info(f"  Shloka {idx}: Chapter {chapter_num}, Verse {verse_num}")
                    logger.info(f"    Sanskrit (raw): {len(raw_sanskrit)} chars, cleaned: {len(cleaned_sanskrit)} chars")
                    logger.info(f"    Valid Devanagari: {has_devanagari}, Corrupted: {has_corrupted}")
                    if cleaned_sanskrit:
                        logger.info(f"    Sanskrit preview: {cleaned_sanskrit[:100]}...")
                    logger.info(f"    Transliteration (raw): {len(raw_transliteration)} chars, cleaned: {len(cleaned_transliteration)} chars")
                    if cleaned_transliteration:
                        logger.info(f"    Transliteration preview: {cleaned_transliteration[:100]}...")
                    
                    try:
                        shloka = Shloka.objects.create(
                            book_name=shloka_data.get('book_name', 'Bhagavad Gita'),
                            chapter_number=chapter_num,
                            verse_number=verse_num,
                            sanskrit_text=cleaned_sanskrit,
                            transliteration=cleaned_transliteration
                        )
                        added_count += 1
                        existing_shlokas.add((chapter_num, verse_num))
                        logger.info(f"    ✓ Saved successfully (ID: {shloka.id})")
                    except Exception as e:
                        logger.error(f"    ✗ Failed to save: {str(e)}")
                        logger.exception(e)
            
            logger.info(f"Extracted and saved {added_count} new shlokas from PDFs (requested: {num_shlokas})")
            
        except Exception as e:
            logger.error(f"Error extracting shlokas from PDFs: {str(e)}")
            # Don't raise - allow the system to continue with existing shlokas
    
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
    
    def _clean_pdf_text(self, text):
        """
        Clean text extracted from PDF, preserving Sanskrit/Devanagari characters.
        
        Args:
            text: Raw text from PDF
            
        Returns:
            Cleaned text string
        """
        if not text:
            return ""
        
        # First, try to fix encoding issues
        # Sometimes PDFs have encoding problems, try to decode properly
        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8', errors='ignore')
            except:
                try:
                    text = text.decode('latin-1', errors='ignore')
                except:
                    text = text.decode('utf-8', errors='replace')
        
        # Normalize unicode characters (important for Sanskrit/Devanagari)
        # Use NFC (Canonical Composition) to better preserve Devanagari
        text = unicodedata.normalize('NFC', text)
        
        # Remove null bytes and control characters (but preserve Devanagari)
        text = re.sub(r'\x00', '', text)  # Remove null bytes
        
        # Remove corrupted characters (private use area) and control characters
        # Preserve:
        # - Printable ASCII (0x20-0x7E)
        # - Newlines, tabs, carriage returns (0x09, 0x0A, 0x0D)
        # - Devanagari range (0x0900-0x097F)
        # - Extended Latin and other valid Unicode (0x00A0-0xDFFF, excluding control chars)
        # Remove:
        # - Private Use Area (0xE000-0xF8FF) - these are corrupted characters
        # - Control characters (except newlines/tabs)
        cleaned_chars = []
        for char in text:
            code = ord(char)
            # Keep printable ASCII
            if 0x20 <= code <= 0x7E:
                cleaned_chars.append(char)
            # Keep newlines, tabs, carriage returns
            elif code in [0x09, 0x0A, 0x0D]:
                cleaned_chars.append(char)
            # Keep Devanagari range (Sanskrit)
            elif 0x0900 <= code <= 0x097F:
                cleaned_chars.append(char)
            # Keep extended Latin and other valid Unicode (but skip control chars)
            elif 0x00A0 <= code < 0xE000 and code not in range(0x2000, 0x200B):  # Exclude some problematic ranges
                # Additional check: skip if it's a control character
                if unicodedata.category(char)[0] != 'C':  # Not a control character
                    cleaned_chars.append(char)
            # Skip private use area (corrupted characters) - don't add anything
            elif 0xE000 <= code <= 0xF8FF:
                pass  # Skip corrupted characters completely
            # Skip other problematic Unicode ranges
            elif 0xF900 <= code <= 0xFAFF:  # CJK Compatibility Ideographs
                pass
            elif 0xFFF0 <= code <= 0xFFFF:  # Specials
                pass
            # For other characters, be conservative and skip
            else:
                pass
        
        text = ''.join(cleaned_chars)
        
        # Fix common PDF extraction issues with hyphenated words
        # But be careful not to break Sanskrit text
        # Only fix for ASCII/Latin characters, not Devanagari
        text = re.sub(r'([a-zA-Z])-\s+([a-zA-Z])', r'\1\2', text)  # Fix hyphenated words split across lines
        text = re.sub(r'([a-zA-Z])\s+-\s+([a-zA-Z])', r'\1-\2', text)  # Fix spaced hyphens
        
        # Clean up excessive whitespace (multiple spaces/tabs)
        # But preserve single newlines which might be intentional in Sanskrit text
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r'\n{3,}', '\n\n', text)  # Multiple newlines to double newline
        
        # Remove leading/trailing whitespace from each line
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]  # Remove empty lines
        text = '\n'.join(cleaned_lines)
        
        # Final cleanup - remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _extract_shlokas_with_ai(self, chapter_text, chapter_num, max_shlokas=10):
        """
        Use AI to extract shlokas from chapter text.
        
        Optimized strategy for performance and cost:
        1. Batch 3-5 verses together to reduce API calls (cost optimization)
        2. Use concise prompts with focused context
        3. Handle truncated responses by retrying with smaller batches
        4. Validate chapter correctness before processing
        """
        try:
            # Split chapter text into verse sections
            verse_sections = self._split_into_verse_sections(chapter_text, chapter_num)
            
            if not verse_sections:
                logger.warning(f"No verse sections found in chapter {chapter_num} text")
                return self._extract_shlokas_fallback(chapter_text, chapter_num, max_shlokas)
            
            logger.info(f"Found {len(verse_sections)} verse sections in chapter {chapter_num}")
            
            # Filter out verses from wrong chapters
            valid_verse_sections = []
            for verse_section in verse_sections:
                verse_text = verse_section.get('text', '')
                if not verse_text:
                    continue
                
                # Quick validation - check if verse text contains wrong chapter markers
                verse_lower = verse_text[:500].lower()  # Check first 500 chars
                has_wrong_chapter = False
                for other_chapter in range(1, 19):
                    if other_chapter != chapter_num:
                        if f'chapter {other_chapter}' in verse_lower:
                            # Check if our chapter also appears
                            if f'chapter {chapter_num}' not in verse_lower:
                                has_wrong_chapter = True
                                break
                
                if not has_wrong_chapter:
                    valid_verse_sections.append(verse_section)
            
            if not valid_verse_sections:
                logger.warning(f"No valid verse sections found for chapter {chapter_num}")
                return []
            
            logger.info(f"Processing {len(valid_verse_sections[:max_shlokas])} valid verses in batches")
            
            # Process verses in batches of 2-3 for cost optimization and to avoid token limits
            batch_size = 3  # Extract 3 verses per API call (reduced to avoid token limits)
            extracted_shlokas = []
            
            for i in range(0, min(len(valid_verse_sections), max_shlokas), batch_size):
                batch = valid_verse_sections[i:i+batch_size]
                if not batch:
                    break
                
                # Extract batch of verses
                batch_shlokas = self._extract_verse_batch_with_ai(
                    verse_sections=batch,
                    chapter_num=chapter_num
                )
                
                if batch_shlokas:
                    extracted_shlokas.extend(batch_shlokas)
                    logger.info(f"Extracted {len(batch_shlokas)} shlokas from batch {i//batch_size + 1}")
                else:
                    # If batch fails, try individual verses as fallback
                    logger.warning(f"Batch extraction failed, trying individual verses...")
                    for verse_section in batch:
                        shloka = self._extract_single_verse_with_ai(
                            verse_text=verse_section.get('text', ''),
                            verse_num=verse_section.get('verse_number'),
                            chapter_num=chapter_num,
                            context_before=verse_section.get('context_before', ''),
                            context_after=verse_section.get('context_after', '')
                        )
                        if shloka:
                            extracted_shlokas.append(shloka)
            
            logger.info(f"Successfully extracted {len(extracted_shlokas)} shlokas from chapter {chapter_num}")
            return extracted_shlokas
                
        except Exception as e:
            logger.error(f"Error extracting shlokas with AI: {str(e)}")
            logger.exception(e)
            return []
    
    def _split_into_verse_sections(self, chapter_text, chapter_num):
        """
        Split chapter text into individual verse sections with context.
        
        Returns list of dicts with:
        - verse_number: int
        - text: str (the verse text)
        - context_before: str (previous verse for context)
        - context_after: str (next verse for context)
        """
        verse_sections = []
        
        # Pattern to find verse markers: "VERSE 1", "Verse 1", "1.", "1.1", etc.
        verse_patterns = [
            rf'VERSE\s+(\d+)',
            rf'Verse\s+(\d+)',
            rf'^\s*(\d+)\.\s+',  # "1. " at start of line
            rf'^\s*{chapter_num}\.(\d+)\s+',  # "1.1 " format
        ]
        
        lines = chapter_text.split('\n')
        current_verse = None
        current_text = []
        verse_start_idx = 0
        
        for i, line in enumerate(lines):
            # Check if this line starts a new verse
            verse_found = None
            for pattern in verse_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    verse_found = int(match.group(1))
                    break
            
            if verse_found is not None:
                # Save previous verse if exists
                if current_verse is not None and current_text:
                    verse_text = '\n'.join(current_text).strip()
                    if verse_text:
                        # Get context (previous and next verses)
                        context_before = self._get_context_before(lines, verse_start_idx)
                        context_after = self._get_context_after(lines, i)
                        
                        verse_sections.append({
                            'verse_number': current_verse,
                            'text': verse_text,
                            'context_before': context_before,
                            'context_after': context_after,
                        })
                
                # Start new verse
                current_verse = verse_found
                current_text = [line]
                verse_start_idx = i
            elif current_verse is not None:
                # Continue current verse
                current_text.append(line)
        
        # Save last verse
        if current_verse is not None and current_text:
            verse_text = '\n'.join(current_text).strip()
            if verse_text:
                context_before = self._get_context_before(lines, verse_start_idx)
                context_after = ""
                
                verse_sections.append({
                    'verse_number': current_verse,
                    'text': verse_text,
                    'context_before': context_before,
                    'context_after': context_after,
                })
        
        return verse_sections
    
    def _get_context_before(self, lines, current_idx, num_lines=5):
        """Get context from previous lines (previous verse)."""
        start = max(0, current_idx - num_lines)
        return '\n'.join(lines[start:current_idx]).strip()
    
    def _get_context_after(self, lines, current_idx, num_lines=5):
        """Get context from next lines (next verse)."""
        end = min(len(lines), current_idx + num_lines)
        return '\n'.join(lines[current_idx:end]).strip()
    
    def _extract_verse_batch_with_ai(self, verse_sections, chapter_num):
        """
        Extract multiple verses in a single API call for cost optimization.
        
        Args:
            verse_sections: List of verse section dicts
            chapter_num: Chapter number
            
        Returns:
            List of shloka dicts
        """
        try:
            # Build concise batch prompt
            verse_texts = []
            verse_numbers = []
            
            for section in verse_sections:
                verse_num = section.get('verse_number')
                verse_text = section.get('text', '')[:800]  # Reduced to 800 chars per verse
                if verse_text and verse_num:
                    # Extract only the essential parts: Sanskrit and transliteration
                    # Remove English translations and extra text
                    lines = verse_text.split('\n')
                    essential_lines = []
                    for line in lines:
                        # Keep lines with Devanagari, transliteration, or verse markers
                        has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in line)
                        has_translit = any(c.isalpha() and ord(c) < 128 for c in line[:50]) and not line.strip().startswith('Addressing') and not line.strip().startswith('After')
                        if has_devanagari or has_translit or 'VERSE' in line.upper():
                            essential_lines.append(line)
                            if len('\n'.join(essential_lines)) > 800:
                                break
                    
                    clean_text = '\n'.join(essential_lines[:10])  # Max 10 lines
                    verse_texts.append(f"V{verse_num}:\n{clean_text}")
                    verse_numbers.append(verse_num)
            
            if not verse_texts:
                return []
            
            combined_text = "\n---\n".join(verse_texts)  # Use shorter separator
            
            # Ultra-concise prompt
            prompt = f"""Extract {len(verse_numbers)} verses from BG Ch{chapter_num}. Verses: {','.join(map(str, verse_numbers))}

{combined_text[:4000]}

Return JSON array:
[{{"chapter_number":{chapter_num},"verse_number":1,"sanskrit_text":"...","transliteration":"..."}}]

Rules:
- Extract Devanagari Sanskrit (U+0900-U+097F only)
- Reconstruct if corrupted using transliteration
- Return all {len(verse_numbers)} verses
- JSON only, no other text"""

            response = self.groq_service.client.chat.completions.create(
                model=self.groq_service.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Extract Sanskrit shlokas. Return ONLY JSON array."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=8000,  # Increased significantly to handle responses
            )
            
            choice = response.choices[0]
            response_text = choice.message.content.strip() if choice.message.content else ""
            finish_reason = choice.finish_reason
            
            if not response_text:
                logger.warning(f"Empty response for batch of {len(verse_numbers)} verses (finish_reason={finish_reason})")
                return []
            
            if finish_reason == 'length':
                logger.warning(f"Batch response truncated (hit token limit). Consider smaller batch size.")
            
            # Extract JSON
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            try:
                shlokas = json.loads(response_text)
                if isinstance(shlokas, list):
                    # Clean and validate each shloka
                    cleaned_shlokas = []
                    for shloka in shlokas:
                        if isinstance(shloka, dict):
                            shloka['book_name'] = 'Bhagavad Gita'
                            if shloka.get('sanskrit_text'):
                                shloka['sanskrit_text'] = self._clean_pdf_text(shloka['sanskrit_text'])
                            # Validate we have Sanskrit text
                            if shloka.get('sanskrit_text'):
                                cleaned_shlokas.append(shloka)
                    return cleaned_shlokas
                else:
                    logger.warning(f"Expected JSON array, got {type(shlokas)}")
                    return []
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse batch response as JSON: {str(e)}")
                logger.debug(f"Response text (first 1000 chars): {response_text[:1000]}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting verse batch: {str(e)}")
            return []
    
    def _extract_single_verse_with_ai(self, verse_text, verse_num, chapter_num, context_before="", context_after=""):
        """
        Extract a single verse with AI using focused context.
        
        This method processes one verse at a time with rich but concise context.
        """
        try:
            # Log what we're trying to extract
            logger.debug(f"Extracting verse {verse_num} from chapter {chapter_num}")
            logger.debug(f"Verse text length: {len(verse_text)} chars")
            logger.debug(f"Verse text preview (first 200 chars): {verse_text[:200]}")
            
            # Build focused prompt with verse and minimal context
            context_parts = []
            if context_before:
                context_parts.append(f"Previous context:\n{context_before[:500]}\n")
            if context_after:
                context_parts.append(f"Following context:\n{context_after[:500]}\n")
            
            context_str = '\n'.join(context_parts)
            
            # Limit verse text to reasonable size (focus on the verse itself)
            verse_sample = verse_text[:2000] if len(verse_text) > 2000 else verse_text
            
            # Check if verse text actually contains the verse number we're looking for
            # Sometimes verse splitting might match wrong verses
            if f'VERSE {verse_num}' not in verse_sample and f'Verse {verse_num}' not in verse_sample:
                # Check if it has any verse marker at all
                has_verse_marker = 'VERSE' in verse_sample or 'Verse' in verse_sample
                if has_verse_marker:
                    logger.warning(f"Verse text for verse {verse_num} doesn't contain 'VERSE {verse_num}' marker. Text might be from wrong verse.")
                    logger.debug(f"Verse text contains: {verse_sample[:300]}")
                else:
                    logger.debug(f"Verse text doesn't have verse marker, might be continuation of previous verse")
            
            # Build concise prompt (reduced context to save tokens)
            context_str_short = ""
            if context_before:
                context_str_short = f"Previous: {context_before[:200]}\n"
            if context_after:
                context_str_short += f"Next: {context_after[:200]}\n"
            
            # Ultra-concise prompt for single verse
            # Extract only essential parts (Sanskrit and transliteration)
            lines = verse_sample.split('\n')
            essential_lines = []
            for line in lines[:15]:  # Max 15 lines
                has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in line)
                has_translit = any(c.isalpha() and ord(c) < 128 for c in line[:50]) and not line.strip().startswith('Addressing')
                if has_devanagari or has_translit or 'VERSE' in line.upper():
                    essential_lines.append(line)
            
            clean_verse = '\n'.join(essential_lines[:10])
            
            prompt = f"""Extract verse {verse_num} from BG Ch{chapter_num}.

{clean_verse[:1000]}

Return JSON:
{{"chapter_number":{chapter_num},"verse_number":{verse_num},"sanskrit_text":"...","transliteration":"..."}}

Extract Devanagari Sanskrit (U+0900-U+097F). Reconstruct if corrupted. JSON only."""

            # Call Groq API with higher token limit for reasoning models
            try:
                response = self.groq_service.client.chat.completions.create(
                    model=self.groq_service.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Extract Sanskrit verse. Return ONLY JSON object."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,  # Lower temperature for more consistent extraction
                    max_tokens=6000,  # Increased significantly to handle full responses
                )
                
                choice = response.choices[0]
                response_text = choice.message.content.strip() if choice.message.content else ""
                finish_reason = choice.finish_reason
                
                # Check for alternative response formats (some models use reasoning field)
                if not response_text and hasattr(choice.message, 'reasoning'):
                    reasoning = choice.message.reasoning
                    if reasoning:
                        logger.debug(f"Found reasoning field with {len(reasoning)} chars for verse {verse_num}")
                        # Sometimes the actual response is in reasoning, try to extract JSON from it
                        if 'sanskrit_text' in reasoning or 'verse_number' in reasoning:
                            # Try to extract JSON from reasoning
                            import re
                            json_match = re.search(r'\{[^{}]*"sanskrit_text"[^{}]*\}', reasoning)
                            if json_match:
                                response_text = json_match.group(0)
                                logger.info(f"Extracted JSON from reasoning field for verse {verse_num}")
                
                # Log detailed response info for debugging
                logger.info(f"AI response for verse {verse_num}: finish_reason={finish_reason}, content_length={len(response_text)}")
                
                # Check if response was cut off or empty
                if not response_text:
                    # Check finish reason to understand why
                    if finish_reason == 'length':
                        logger.warning(f"AI response for verse {verse_num} was cut off (hit token limit). Consider reducing prompt size.")
                    elif finish_reason == 'stop':
                        logger.warning(f"AI returned empty response for verse {verse_num} (finish_reason=stop) - model stopped without generating content")
                    else:
                        logger.warning(f"AI returned empty response for verse {verse_num} (finish_reason={finish_reason})")
                    
                    # Log prompt info to help debug
                    logger.debug(f"Prompt length: {len(prompt)} chars")
                    logger.debug(f"Prompt preview (first 500 chars): {prompt[:500]}")
                    
                    # Log the actual response object for debugging
                    logger.debug(f"Full response object: {response}")
                    logger.debug(f"Response choice: {choice}")
                    logger.debug(f"Message object: {choice.message}")
                    
                    # Check if there's any error in the response
                    if hasattr(response, 'error'):
                        logger.error(f"API error: {response.error}")
                    
                    return None
                
                # Check if response was truncated
                if finish_reason == 'length':
                    logger.warning(f"AI response for verse {verse_num} may be truncated (hit token limit)")
                
                # Extract JSON from response
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0]
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0]
                
                # Parse JSON
                try:
                    shloka = json.loads(response_text)
                    if isinstance(shloka, dict):
                        shloka['book_name'] = 'Bhagavad Gita'
                        # Clean Sanskrit text
                        if shloka.get('sanskrit_text'):
                            shloka['sanskrit_text'] = self._clean_pdf_text(shloka['sanskrit_text'])
                        # Validate we have Sanskrit text
                        if not shloka.get('sanskrit_text'):
                            logger.warning(f"Verse {verse_num} has no Sanskrit text")
                            return None
                        return shloka
                    else:
                        logger.warning(f"AI returned non-dict response for verse {verse_num}: {type(shloka)}")
                        return None
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response as JSON for verse {verse_num}: {str(e)}")
                    logger.error(f"Response text (first 500 chars): {response_text[:500]}")
                    return None
            except Exception as e:
                logger.error(f"Error calling Groq API for verse {verse_num}: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting single verse {verse_num}: {str(e)}")
            return None
    
    def _extract_shlokas_fallback(self, chapter_text, chapter_num, max_shlokas=10):
        """
        Fallback method: Extract shlokas from full chapter text in smaller chunks.
        Used when verse splitting fails.
        """
        try:
            # Split into smaller chunks (about 3-4 verses per chunk)
            chunk_size = 3000  # characters per chunk
            chunks = []
            for i in range(0, len(chapter_text), chunk_size):
                chunk = chapter_text[i:i+chunk_size]
                chunks.append(chunk)
            
            logger.info(f"Using fallback: splitting chapter into {len(chunks)} chunks")
            
            extracted_shlokas = []
            for chunk_idx, chunk in enumerate(chunks[:max_shlokas]):
                if len(extracted_shlokas) >= max_shlokas:
                    break
                
                prompt = f"""Extract shlokas from this Bhagavad Gita chapter text chunk.

Chapter: {chapter_num}
Text chunk:
{chunk[:2000]}

Extract up to 3 shlokas and return as JSON array. Each shloka must have:
- chapter_number: {chapter_num}
- verse_number: (the verse number)
- sanskrit_text: (Sanskrit text in Devanagari script - clean Devanagari Unicode only)
- transliteration: (Roman transliteration, or empty string)

Return ONLY valid JSON array."""

                try:
                    response = self.groq_service.client.chat.completions.create(
                        model=self.groq_service.model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert in Sanskrit. Extract shlokas accurately. Return ONLY valid JSON array."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=2000,
                    )
                    
                    response_text = response.choices[0].message.content.strip()
                    if not response_text:
                        continue
                    
                    # Extract JSON
                    if '```json' in response_text:
                        response_text = response_text.split('```json')[1].split('```')[0]
                    elif '```' in response_text:
                        response_text = response_text.split('```')[1].split('```')[0]
                    
                    shlokas = json.loads(response_text)
                    if isinstance(shlokas, list):
                        for shloka in shlokas:
                            shloka['book_name'] = 'Bhagavad Gita'
                            if shloka.get('sanskrit_text'):
                                shloka['sanskrit_text'] = self._clean_pdf_text(shloka['sanskrit_text'])
                            if shloka.get('sanskrit_text'):
                                extracted_shlokas.append(shloka)
                                if len(extracted_shlokas) >= max_shlokas:
                                    break
                except Exception as e:
                    logger.warning(f"Error processing chunk {chunk_idx}: {str(e)}")
                    continue
            
            return extracted_shlokas
        except Exception as e:
            logger.error(f"Error in fallback extraction: {str(e)}")
            return []
