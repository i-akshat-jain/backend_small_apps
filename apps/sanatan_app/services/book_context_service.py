"""
Book Context Service for extracting relevant context from PDF books.

This service extracts relevant passages from the provided Bhagavad Gita PDFs
(Hindi and English) to provide contextual information for shloka explanations.
"""
import os
from pathlib import Path
from typing import Optional, Dict, List
import logging
from django.conf import settings

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None
    logging.warning("pypdf not installed. Book context extraction will be disabled.")

logger = logging.getLogger(__name__)


class BookContextService:
    """Service for extracting context from PDF books."""
    
    # Book file paths (relative to app directory)
    ENGLISH_BOOK = "books/Bhagavad-gita-Swami-BG-Narasingha.pdf"
    HINDI_BOOK = "books/Bhagavad-Gita-Hindi.pdf"
    
    # Maximum context length to include in prompts (characters)
    MAX_CONTEXT_LENGTH = 2000
    
    def __init__(self):
        """Initialize the book context service."""
        self.base_dir = Path(__file__).resolve().parent.parent
        self.english_book_path = self.base_dir / self.ENGLISH_BOOK
        self.hindi_book_path = self.base_dir / self.HINDI_BOOK
        
        # Cache for loaded PDFs
        self._english_pdf = None
        self._hindi_pdf = None
        self._english_text_cache = {}
        self._hindi_text_cache = {}
    
    def _load_pdf(self, book_path: Path) -> Optional[object]:
        """Load a PDF file and return the reader object."""
        if PdfReader is None:
            logger.warning("pypdf not available. Cannot load PDF.")
            return None
        
        if not book_path.exists():
            logger.warning(f"PDF file not found: {book_path}")
            return None
        
        try:
            return PdfReader(str(book_path))
        except Exception as e:
            logger.error(f"Error loading PDF {book_path}: {str(e)}")
            return None
    
    def _extract_text_from_pdf(self, pdf_reader, page_range: Optional[tuple] = None) -> str:
        """
        Extract text from PDF pages with better encoding handling.
        
        Args:
            pdf_reader: PdfReader object
            page_range: Optional tuple (start_page, end_page) - 0-indexed
            
        Returns:
            Extracted text as string
        """
        if pdf_reader is None:
            return ""
        
        try:
            start_page = page_range[0] if page_range else 0
            end_page = page_range[1] if page_range else len(pdf_reader.pages)
            
            text_parts = []
            for page_num in range(start_page, min(end_page, len(pdf_reader.pages))):
                try:
                    page = pdf_reader.pages[page_num]
                    # Try to extract text with better encoding
                    text = page.extract_text()
                    
                    if text:
                        # Ensure proper UTF-8 encoding
                        if isinstance(text, bytes):
                            try:
                                text = text.decode('utf-8', errors='replace')
                            except:
                                text = text.decode('latin-1', errors='replace')
                        
                        # Normalize unicode to handle encoding issues
                        import unicodedata
                        text = unicodedata.normalize('NFC', text)
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {str(e)}")
                    continue
            
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""
    
    def _search_for_chapter_verse(self, text: str, chapter: int, verse: int) -> str:
        """
        Search for relevant context around a specific chapter and verse.
        
        This method looks for patterns like "Chapter X", "Verse Y", etc.
        and extracts surrounding context.
        
        Args:
            text: Full text to search in
            chapter: Chapter number
            verse: Verse number
            
        Returns:
            Relevant context string
        """
        if not text:
            return ""
        
        # Search patterns (case-insensitive)
        patterns = [
            f"Chapter {chapter}",
            f"chapter {chapter}",
            f"CHAPTER {chapter}",
            f"Ch. {chapter}",
            f"ch. {chapter}",
            f"Verse {verse}",
            f"verse {verse}",
            f"VERSE {verse}",
            f"Verse {chapter}.{verse}",
            f"{chapter}.{verse}",
        ]
        
        text_lower = text.lower()
        context_parts = []
        
        # Try to find relevant sections
        for pattern in patterns:
            pattern_lower = pattern.lower()
            if pattern_lower in text_lower:
                # Find all occurrences
                start_idx = 0
                while True:
                    idx = text_lower.find(pattern_lower, start_idx)
                    if idx == -1:
                        break
                    
                    # Extract context around the match (500 chars before and after)
                    context_start = max(0, idx - 500)
                    context_end = min(len(text), idx + 1000)
                    context = text[context_start:context_end]
                    
                    # Clean up the context
                    context = context.strip()
                    if context and len(context) > 100:  # Only include substantial context
                        context_parts.append(context)
                    
                    start_idx = idx + 1
        
        # Combine and limit context length
        combined_context = "\n\n---\n\n".join(context_parts[:3])  # Max 3 matches
        
        # Truncate if too long
        if len(combined_context) > self.MAX_CONTEXT_LENGTH:
            combined_context = combined_context[:self.MAX_CONTEXT_LENGTH] + "..."
        
        return combined_context
    
    def get_context_for_shloka(
        self,
        book_name: str,
        chapter_number: int,
        verse_number: int,
        include_hindi: bool = True,
        include_english: bool = True
    ) -> Dict[str, str]:
        """
        Get relevant context from books for a specific shloka.
        
        Args:
            book_name: Name of the book (e.g., "Bhagavad Gita")
            chapter_number: Chapter number
            verse_number: Verse number
            include_hindi: Whether to include Hindi book context
            include_english: Whether to include English book context
            
        Returns:
            Dictionary with 'english_context' and 'hindi_context' keys
        """
        context = {
            'english_context': '',
            'hindi_context': ''
        }
        
        # Load English PDF if needed
        if include_english and self.english_book_path.exists():
            if self._english_pdf is None:
                self._english_pdf = self._load_pdf(self.english_book_path)
            
            if self._english_pdf:
                # Try to get cached text or extract it
                cache_key = f"ch{chapter_number}_v{verse_number}"
                if cache_key not in self._english_text_cache:
                    # Extract text from relevant pages (approximate)
                    # For Bhagavad Gita, chapters are roughly 10-20 pages each
                    # We'll extract a wider range to ensure we get the context
                    estimated_start_page = (chapter_number - 1) * 15
                    estimated_end_page = chapter_number * 15 + 5
                    
                    text = self._extract_text_from_pdf(
                        self._english_pdf,
                        (estimated_start_page, estimated_end_page)
                    )
                    self._english_text_cache[cache_key] = text
                
                text = self._english_text_cache[cache_key]
                context['english_context'] = self._search_for_chapter_verse(
                    text, chapter_number, verse_number
                )
        
        # Load Hindi PDF if needed
        if include_hindi and self.hindi_book_path.exists():
            if self._hindi_pdf is None:
                self._hindi_pdf = self._load_pdf(self.hindi_book_path)
            
            if self._hindi_pdf:
                # Try to get cached text or extract it
                cache_key = f"ch{chapter_number}_v{verse_number}"
                if cache_key not in self._hindi_text_cache:
                    # Extract text from relevant pages (approximate)
                    estimated_start_page = (chapter_number - 1) * 15
                    estimated_end_page = chapter_number * 15 + 5
                    
                    text = self._extract_text_from_pdf(
                        self._hindi_pdf,
                        (estimated_start_page, estimated_end_page)
                    )
                    self._hindi_text_cache[cache_key] = text
                
                text = self._hindi_text_cache[cache_key]
                context['hindi_context'] = self._search_for_chapter_verse(
                    text, chapter_number, verse_number
                )
        
        return context
    
    def get_full_chapter_context(
        self,
        chapter_number: int,
        language: str = "english"
    ) -> str:
        """
        Get full context for an entire chapter.
        
        Args:
            chapter_number: Chapter number
            language: "english" or "hindi"
            
        Returns:
            Full chapter text
        """
        book_path = self.english_book_path if language == "english" else self.hindi_book_path
        
        if not book_path.exists():
            return ""
        
        pdf_reader = self._load_pdf(book_path)
        if not pdf_reader:
            return ""
        
        # Extract text from estimated chapter pages
        estimated_start_page = (chapter_number - 1) * 15
        estimated_end_page = chapter_number * 15 + 5
        
        return self._extract_text_from_pdf(
            pdf_reader,
            (estimated_start_page, estimated_end_page)
        )

