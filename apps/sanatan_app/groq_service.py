"""
Groq AI service for generating shloka explanations.

IMPORTANT: This service uses standardized prompts to ensure consistent response formats
across all shlokas. The prompt structure, system message, and parameters are carefully
designed to maintain format consistency. Any changes to prompts or parameters should
be made with caution to preserve this consistency.

Key standardization points:
- All prompts follow the same structure regardless of optional fields
- System message is consistent across all requests
- Word limits and token limits are standardized
- Temperature and other parameters are fixed for consistency
"""
from groq import Groq
from django.conf import settings
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)


class GroqService:
    """Service for interacting with Groq API."""
    
    # Constants for consistent prompt formatting
    SYSTEM_MESSAGE = """You are an expert in Hindu philosophy, Sanskrit literature, and the Bhagavad Gita. Provide clear, accessible explanations that help modern readers understand the deep wisdom of these ancient texts.

Your explanations should:
- Be accurate and respectful to traditional interpretations
- Use modern, accessible language
- Connect ancient wisdom to contemporary life
- Maintain consistency in tone and structure across all explanations

CRITICAL FORMATTING REQUIREMENTS:
- You MUST follow the exact format specified in each request
- Every explanation MUST include ALL required sections (Meaning, Word-by-word, Explanation, Practical Application, Example/Examples)
- Missing any section will result in rejection. Always verify you have included all sections before responding
- Use ONLY list format with bullet points (-). NEVER use tables, markdown tables, or any tabular format
- For word-by-word sections, use EXACTLY: '- **word** - meaning' (en dash - between word and meaning, NOT hyphen)
- Section headers must end with colon (e.g., '1. MEANING:')
- All bullet points must start with '- ' (dash and space)
- Use consistent punctuation throughout

FORMAT REQUIREMENT: Use ONLY list format with bullet points (-). NEVER use tables, markdown tables, or any tabular format. All content must be in plain text list format."""
    
    SUMMARY_WORD_LIMIT = "150-200 words"
    DETAILED_WORD_LIMIT = "600-800 words"  # Increased to accommodate word-by-word breakdown
    
    SUMMARY_MAX_TOKENS = 2000  # Increased to handle longer summaries and avoid truncation
    DETAILED_MAX_TOKENS = 8000  # Increased significantly to accommodate word-by-word breakdown and all sections
    
    TEMPERATURE = 0.5  # Lower temperature for more consistent format compliance
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = "openai/gpt-oss-20b"  # Updated to use active model
    
    def generate_explanation(
        self,
        shloka: dict,
        explanation_type: str = "summary",
        book_context: Optional[dict] = None
    ) -> tuple:
        """
        Generate explanation for a shloka with retry logic for token limit issues.
        
        Args:
            shloka: Dictionary containing shloka data with keys:
                - book_name (str): Name of the book
                - chapter_number (int): Chapter number
                - verse_number (int): Verse number
                - sanskrit_text (str): Sanskrit text (required)
                - transliteration (str, optional): Transliteration in Roman script
            explanation_type: Either 'summary' or 'detailed'
            book_context: Optional dictionary with 'english_context' and 'hindi_context' keys
                         containing relevant passages from the source books
            
        Returns:
            Tuple of (explanation_text, generation_prompt, structured_data)
            where structured_data is a dict with keys: why_this_matters, context, word_by_word,
            modern_examples, themes, reflection_prompt
        """
        # Validate explanation_type
        if explanation_type not in ["summary", "detailed"]:
            raise ValueError(f"Invalid explanation_type: {explanation_type}. Must be 'summary' or 'detailed'")
        
        # Retry logic: try with full context first, then without context, then with reduced prompt
        retry_attempts = [
            {"book_context": book_context, "reduce_context": False, "increase_tokens": False},
            {"book_context": None, "reduce_context": False, "increase_tokens": True},  # Retry without context but with more tokens
            {"book_context": None, "reduce_context": True, "increase_tokens": True},  # Retry with reduced prompt
        ]
        
        last_exception = None
        
        for attempt_num, retry_config in enumerate(retry_attempts, 1):
            try:
                # Build prompt with current retry configuration
                current_context = retry_config["book_context"]
                reduce_context = retry_config["reduce_context"]
                increase_tokens = retry_config["increase_tokens"]
                
                prompt = self._build_prompt(shloka, explanation_type, current_context, reduce_context=reduce_context)
                
                # Determine max_tokens based on explanation type and retry config
                base_max_tokens = self.SUMMARY_MAX_TOKENS if explanation_type == "summary" else self.DETAILED_MAX_TOKENS
                max_tokens = int(base_max_tokens * 1.5) if increase_tokens else base_max_tokens
                
                # Generate explanation with consistent parameters
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self.SYSTEM_MESSAGE
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.TEMPERATURE,
                    max_tokens=max_tokens,
                )
                
                # Extract response content and finish reason
                choice = response.choices[0]
                response_content = choice.message.content
                finish_reason = choice.finish_reason
                
                # Handle truncated responses (finish_reason: "length")
                if finish_reason == "length":
                    if response_content and len(response_content.strip()) > 50:  # Lowered threshold from 100 to 50
                        # We have content but it was truncated - log warning but use what we have
                        logger.warning(
                            f"AI response was truncated (hit token limit) for "
                            f"{shloka.get('book_name')} Chapter {shloka.get('chapter_number')}, "
                            f"Verse {shloka.get('verse_number')}. Response length: {len(response_content)} chars. "
                            f"Attempt {attempt_num}/{len(retry_attempts)}. Using partial content."
                        )
                        # Use the truncated content - it's better than nothing
                        explanation_text = response_content.strip()
                    else:
                        # Truncated but no useful content - try next retry attempt
                        if attempt_num < len(retry_attempts):
                            logger.warning(
                                f"AI response truncated with no usable content (attempt {attempt_num}/{len(retry_attempts)}). "
                                f"Retrying with different parameters..."
                            )
                            last_exception = Exception(
                                f"AI response was truncated with no usable content (finish_reason: length, "
                                f"content_length: {len(response_content) if response_content else 0})"
                            )
                            continue
                        else:
                            # Last attempt failed - raise exception
                            error_msg = f"AI response was truncated with no usable content after {len(retry_attempts)} attempts (finish_reason: length, content_length: {len(response_content) if response_content else 0})"
                            logger.error(error_msg)
                            raise Exception(error_msg)
                elif not response_content:
                    # Empty response with other finish reason - try next retry attempt
                    if attempt_num < len(retry_attempts):
                        logger.warning(
                            f"Empty response from AI (finish_reason: {finish_reason}, attempt {attempt_num}/{len(retry_attempts)}). "
                            f"Retrying with different parameters..."
                        )
                        last_exception = Exception(f"Empty response from AI (finish_reason: {finish_reason})")
                        continue
                    else:
                        # Last attempt failed - raise exception
                        error_msg = f"Empty response from AI after {len(retry_attempts)} attempts (finish_reason: {finish_reason})"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                else:
                    # Success - got a complete response
                    explanation_text = response_content.strip()
                
                # Check if explanation is too short (likely an error, but not if it was truncated)
                if finish_reason != "length" and len(explanation_text) < 50:
                    logger.warning(
                        f"AI response is very short ({len(explanation_text)} chars) for "
                        f"{shloka.get('book_name')} Chapter {shloka.get('chapter_number')}, "
                        f"Verse {shloka.get('verse_number')} (finish_reason: {finish_reason})"
                    )
                
                # Normalize formatting for consistency across all explanations
                explanation_text = self._normalize_explanation_formatting(explanation_text, explanation_type)
                
                # Parse structured data from explanation text
                structured_data = self._parse_structured_data(explanation_text, explanation_type)
                
                # Log success
                if attempt_num > 1:
                    logger.info(
                        f"Successfully generated {explanation_type} explanation on attempt {attempt_num} for "
                        f"{shloka.get('book_name')} Chapter {shloka.get('chapter_number')}, Verse {shloka.get('verse_number')}"
                    )
                else:
                    logger.debug(
                        f"Generated {explanation_type} explanation for {shloka.get('book_name')} "
                        f"Chapter {shloka.get('chapter_number')}, Verse {shloka.get('verse_number')}"
                    )
                
                return explanation_text, prompt, structured_data
                
            except Exception as e:
                last_exception = e
                # If this is not the last attempt, continue to next retry
                if attempt_num < len(retry_attempts):
                    logger.warning(
                        f"Error generating explanation (attempt {attempt_num}/{len(retry_attempts)}): {str(e)}. "
                        f"Retrying with different parameters..."
                    )
                    continue
                else:
                    # Last attempt failed - log and raise
                    logger.error(f"Error generating explanation after {len(retry_attempts)} attempts: {str(e)}")
                    raise Exception(f"Failed to generate explanation after {len(retry_attempts)} attempts: {str(e)}")
        
        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Failed to generate explanation: Unknown error")
    
    def parse_structured_data_from_text(self, explanation_text: str, explanation_type: str) -> dict:
        """
        Parse structured data from existing explanation text.
        
        This is a public method to extract structured fields from existing explanations
        without regenerating the entire explanation.
        
        Args:
            explanation_text: The existing explanation text
            explanation_type: Either 'summary' or 'detailed'
            
        Returns:
            Dictionary with structured data fields
        """
        return self._parse_structured_data(explanation_text, explanation_type)
    
    def _parse_structured_data(self, explanation_text: str, explanation_type: str) -> dict:
        """
        Parse structured data from explanation text.
        
        Extracts:
        - why_this_matters: From "PRACTICAL APPLICATION" section
        - context: From "MEANING" section (context part)
        - word_by_word: From "WORD-BY-WORD" section
        - modern_examples: From "EXAMPLES" section
        - themes: Extracted from content (common themes like Dharma, Karma, etc.)
        - reflection_prompt: Generated based on the shloka content
        
        Returns:
            Dictionary with structured data fields
        """
        structured = {
            'why_this_matters': None,
            'context': None,
            'word_by_word': None,
            'modern_examples': None,
            'themes': None,
            'reflection_prompt': None,
        }
        
        try:
            # Split explanation into sections
            sections = self._extract_sections(explanation_text)
            
            # Extract why_this_matters from PRACTICAL APPLICATION section
            if 'PRACTICAL APPLICATION' in sections:
                structured['why_this_matters'] = sections['PRACTICAL APPLICATION'].strip()
            
            # Extract context from MEANING section (context part)
            if 'MEANING' in sections:
                meaning_text = sections['MEANING']
                # Try to extract context part (mentions of "context", "dialogue", "story")
                lines = meaning_text.split('\n')
                context_lines = [line for line in lines if any(word in line.lower() for word in ['context', 'dialogue', 'story', 'situation', 'background'])]
                if context_lines:
                    structured['context'] = '\n'.join(context_lines).strip()
                # If no specific context lines found, use the full MEANING section as context
                elif meaning_text.strip():
                    structured['context'] = meaning_text.strip()
            
            # Extract word_by_word from WORD-BY-WORD section
            if 'WORD-BY-WORD' in sections:
                word_text = sections['WORD-BY-WORD']
                parsed_words = self._parse_word_by_word(word_text)
                if parsed_words:
                    structured['word_by_word'] = parsed_words
                # If parsing failed but we have text, log a warning but don't fail
                elif word_text.strip():
                    logger.debug(f"Could not parse word-by-word section, but text exists (may be truncated or malformed)")
            
            # Extract modern_examples from EXAMPLES section
            if 'EXAMPLES' in sections:
                examples_text = sections['EXAMPLES']
                parsed_examples = self._parse_modern_examples(examples_text)
                if parsed_examples:
                    structured['modern_examples'] = parsed_examples
                # If parsing failed but we have text, try to create a generic example
                elif examples_text.strip():
                    # Create a generic example from the text
                    structured['modern_examples'] = [{
                        'category': 'Modern Application',
                        'description': examples_text.strip()[:500]  # Limit to 500 chars
                    }]
            
            # Extract themes from content (look for common theme keywords)
            # This should always work even with partial content
            structured['themes'] = self._extract_themes(explanation_text)
            
            # Generate reflection prompt
            # This should always work even with partial content
            structured['reflection_prompt'] = self._generate_reflection_prompt(explanation_text)
            
        except Exception as e:
            logger.warning(f"Error parsing structured data: {str(e)}. Some fields may be missing.")
            # Continue - we'll return what we have, even if some fields are None
            # This allows partial explanations to be saved
        
        return structured
    
    def _extract_sections(self, text: str) -> dict:
        """Extract sections from explanation text based on headers."""
        sections = {}
        current_section = None
        current_content = []
        
        lines = text.split('\n')
        for line in lines:
            # Check if line is a section header
            # Match patterns like "1. MEANING:", "MEANING:", "2. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN:", etc.
            # Handle various dash types: regular hyphen (-), en dash (-), em dash (—), and Unicode dashes
            # Pattern: starts with optional number and dot, then uppercase letters, spaces, slashes, dashes, and ends with colon
            if re.match(r'^\d+\.\s+[A-Z][A-Z\s/-—\-‑]+:', line) or re.match(r'^[A-Z][A-Z\s/-—\-‑]+:', line):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                # Start new section - normalize the section name
                current_section = self._normalize_section_name(line.strip().rstrip(':'))
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _normalize_section_name(self, section_name: str) -> str:
        """
        Normalize section names to standard keys for easier lookup.
        
        Examples:
        - "2. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN" -> "WORD-BY-WORD"
        - "2. WORD-BY-WORD" -> "WORD-BY-WORD"
        - "WORD-BY-WORD" -> "WORD-BY-WORD"
        - "5. EXAMPLES" -> "EXAMPLES"
        - "5. EXAMPLE" -> "EXAMPLES" (for summary)
        """
        # Remove leading number and dot if present
        section_name = re.sub(r'^\d+\.\s+', '', section_name)
        
        # Normalize to uppercase for comparison
        # Also normalize various dash types to regular hyphen for matching
        section_upper = section_name.upper()
        # Replace various dash types with regular hyphen for matching
        section_upper_normalized = section_upper.replace('–', '-').replace('—', '-').replace('‑', '-')
        
        # Map variations to standard names
        # Check for WORD-BY-WORD with various dash types
        if 'WORD-BY-WORD' in section_upper_normalized or 'WORD BY WORD' in section_upper_normalized or 'WORD‑BY‑WORD' in section_upper:
            return 'WORD-BY-WORD'
        elif 'MEANING' in section_upper:
            return 'MEANING'
        elif 'EXPLANATION' in section_upper:
            return 'EXPLANATION'
        elif 'PRACTICAL APPLICATION' in section_upper:
            return 'PRACTICAL APPLICATION'
        elif 'EXAMPLE' in section_upper:  # Covers both "EXAMPLE" and "EXAMPLES"
            return 'EXAMPLES'
        else:
            # Return original if no match
            return section_name
    
    def _parse_word_by_word(self, text: str) -> list:
        """Parse word-by-word breakdown into structured format."""
        words = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Handle lines that start with bullet points (-, •, *)
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                # Remove leading bullet and whitespace
                line = line.lstrip('-•*').strip()
            
            # Skip if line is empty after removing bullet
            if not line:
                continue
            
            # Try to parse format like: "**word** – meaning" or "word – meaning" or "word: meaning"
            # Handle bold formatting (**word**)
            sanskrit = None
            meaning = None
            transliteration = None
            
            # Pattern 1: "**word** – meaning" or "**word (translit)** – meaning"
            bold_pattern = r'\*\*([^*]+)\*\*\s*[–\-:]\s*(.+)'
            match = re.match(bold_pattern, line)
            if match:
                sanskrit_with_translit = match.group(1).strip()
                meaning = match.group(2).strip()
                
                # Extract transliteration from parentheses/brackets
                transliteration_match = re.search(r'[\(\[]([^\)\]]+)[\)\]]', sanskrit_with_translit)
                if transliteration_match:
                    transliteration = transliteration_match.group(1).strip()
                    sanskrit = re.sub(r'[\(\[][^\)\]]+[\)\]]', '', sanskrit_with_translit).strip()
                else:
                    sanskrit = sanskrit_with_translit
            else:
                # Pattern 1b: Also handle cases where bold markers are at the end: "word** – meaning"
                bold_end_pattern = r'([^*]+)\*\*\s*[–\-:]\s*(.+)'
                match = re.match(bold_end_pattern, line)
                if match:
                    sanskrit_with_translit = match.group(1).strip()
                    meaning = match.group(2).strip()
                    
                    # Extract transliteration from parentheses/brackets
                    transliteration_match = re.search(r'[\(\[]([^\)\]]+)[\)\]]', sanskrit_with_translit)
                    if transliteration_match:
                        transliteration = transliteration_match.group(1).strip()
                        sanskrit = re.sub(r'[\(\[][^\)\]]+[\)\]]', '', sanskrit_with_translit).strip()
                    else:
                        sanskrit = sanskrit_with_translit
                else:
                    # Pattern 2: "word – meaning" or "word: meaning" (without bold)
                    # Try various separators: en dash (–), em dash (—), hyphen (-), colon (:)
                    parts = re.split(r'[–—\-:]', line, 1)
                    if len(parts) == 2:
                        sanskrit_with_translit = parts[0].strip()
                        meaning = parts[1].strip()
                        
                        # Extract transliteration from parentheses/brackets
                        transliteration_match = re.search(r'[\(\[]([^\)\]]+)[\)\]]', sanskrit_with_translit)
                        if transliteration_match:
                            transliteration = transliteration_match.group(1).strip()
                            sanskrit = re.sub(r'[\(\[][^\)\]]+[\)\]]', '', sanskrit_with_translit).strip()
                        else:
                            sanskrit = sanskrit_with_translit
            
            # Only add if we successfully parsed both sanskrit and meaning
            if sanskrit and meaning:
                # Clean up bold markers from sanskrit (remove ** at start or end)
                sanskrit = sanskrit.strip().lstrip('*').rstrip('*').strip()
                
                words.append({
                    'sanskrit': sanskrit,
                    'transliteration': transliteration or '',
                    'meaning': meaning
                })
        
        return words if words else None
    
    def _parse_modern_examples(self, text: str) -> list:
        """Parse modern examples into structured format."""
        examples = []
        lines = text.split('\n')
        current_category = None
        current_description = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line is a category header (e.g., "In Your Career:", "In Daily Life:")
            if re.match(r'^[A-Z][^:]+:', line):
                # Save previous example
                if current_category and current_description:
                    examples.append({
                        'category': current_category.rstrip(':'),
                        'description': ' '.join(current_description).strip()
                    })
                # Start new example
                current_category = line
                current_description = []
            elif current_category:
                current_description.append(line)
        
        # Save last example
        if current_category and current_description:
            examples.append({
                'category': current_category.rstrip(':'),
                'description': ' '.join(current_description).strip()
            })
        
        # If no structured examples found, create generic ones from text
        if not examples and text.strip():
            # Split by common patterns and create examples
            if 'career' in text.lower() or 'work' in text.lower():
                examples.append({
                    'category': 'In Your Career',
                    'description': text.strip()
                })
            if 'daily life' in text.lower() or 'everyday' in text.lower():
                examples.append({
                    'category': 'In Daily Life',
                    'description': text.strip()
                })
            if not examples:
                examples.append({
                    'category': 'Modern Application',
                    'description': text.strip()
                })
        
        return examples if examples else None
    
    def _extract_themes(self, text: str) -> list:
        """Extract themes from explanation text."""
        theme_keywords = {
            'Dharma': ['dharma', 'duty', 'righteousness', 'moral'],
            'Karma': ['karma', 'action', 'deed', 'consequence'],
            'Wisdom': ['wisdom', 'knowledge', 'understanding', 'insight'],
            'Detachment': ['detachment', 'non-attachment', 'equanimity', 'dispassion'],
            'Devotion': ['devotion', 'bhakti', 'worship', 'dedication'],
            'Self-Realization': ['self', 'atman', 'soul', 'consciousness', 'realization'],
            'Yoga': ['yoga', 'union', 'practice', 'discipline'],
        }
        
        text_lower = text.lower()
        found_themes = []
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                found_themes.append(theme)
        
        # Default themes if none found
        if not found_themes:
            found_themes = ['Dharma', 'Karma', 'Wisdom']
        
        return found_themes[:5]  # Limit to 5 themes
    
    def _normalize_explanation_formatting(self, text: str, explanation_type: str) -> str:
        """
        Normalize explanation formatting to ensure consistency across all shlokas.
        
        This function standardizes:
        - Section headers (always "1. MEANING:", "2. WORD-BY-WORD:", etc. with colon)
        - Word-by-word formatting (always "- **word** – meaning" with en dash)
        - Bullet points (always "- " with space)
        - Punctuation and spacing
        - Transliteration formatting
        
        Args:
            text: Raw explanation text from AI
            explanation_type: Either 'summary' or 'detailed'
            
        Returns:
            Normalized explanation text with consistent formatting
        """
        if not text:
            return text
        
        lines = text.split('\n')
        normalized_lines = []
        in_word_by_word_section = False
        
        for i, line in enumerate(lines):
            original_line = line
            line = line.rstrip()  # Remove trailing whitespace
            
            # Normalize section headers
            # Match patterns like "1. MEANING", "1. MEANING:", "MEANING:", etc.
            # Use different formats for summary vs detailed
            if explanation_type == "detailed":
                section_patterns = [
                    (r'^(\d+)\.\s*MEANING\s*:?\s*$', r'\1. MEANING:'),
                    (r'^(\d+)\.\s*WORD-BY-WORD\s*(/.*?)?\s*:?\s*$', r'\1. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN:'),
                    (r'^(\d+)\.\s*WORD\s*BY\s*WORD\s*:?\s*$', r'\1. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN:'),
                    (r'^(\d+)\.\s*EXPLANATION\s*:?\s*$', r'\1. EXPLANATION:'),
                    (r'^(\d+)\.\s*PRACTICAL\s*APPLICATION\s*:?\s*$', r'\1. PRACTICAL APPLICATION:'),
                    (r'^(\d+)\.\s*EXAMPLES\s*:?\s*$', r'\1. EXAMPLES:'),
                ]
            else:  # summary
                section_patterns = [
                    (r'^(\d+)\.\s*MEANING\s*:?\s*$', r'\1. MEANING:'),
                    (r'^(\d+)\.\s*WORD-BY-WORD\s*(/.*?)?\s*:?\s*$', r'\1. WORD-BY-WORD:'),
                    (r'^(\d+)\.\s*WORD\s*BY\s*WORD\s*:?\s*$', r'\1. WORD-BY-WORD:'),
                    (r'^(\d+)\.\s*EXPLANATION\s*:?\s*$', r'\1. EXPLANATION:'),
                    (r'^(\d+)\.\s*PRACTICAL\s*APPLICATION\s*:?\s*$', r'\1. PRACTICAL APPLICATION:'),
                    (r'^(\d+)\.\s*EXAMPLE\s*:?\s*$', r'\1. EXAMPLE:'),
                ]
            
            header_matched = False
            for pattern, replacement in section_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    normalized_line = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
                    normalized_lines.append(normalized_line)
                    header_matched = True
                    # Track if we're in word-by-word section
                    if 'WORD-BY-WORD' in normalized_line.upper() or 'WORD BY WORD' in normalized_line.upper():
                        in_word_by_word_section = True
                    else:
                        in_word_by_word_section = False
                    break
            
            if header_matched:
                continue
            
            # Normalize bullet points - ensure they start with "- " (dash and space)
            if line.strip().startswith('-') or line.strip().startswith('•') or line.strip().startswith('*'):
                # Remove leading whitespace, then ensure it starts with "- "
                line = line.lstrip(' \t•*-')
                line = '- ' + line
                
                # Special handling for word-by-word section
                if in_word_by_word_section:
                    # Normalize word-by-word format: "- **word** – meaning" or "- word – meaning"
                    # Standardize to: "- **word** – meaning" (with en dash U+2013)
                    
                    # Replace various dash types with en dash (U+2013)
                    # En dash: – (U+2013), Em dash: — (U+2014), Hyphen: - (U+002D)
                    line = re.sub(r'[—\-]', '-', line)  # Replace em dash and hyphen with en dash
                    
                    # Ensure bold formatting for Sanskrit words
                    # Pattern: "- word – meaning" or "- **word** – meaning" or "- word: meaning"
                    # Convert to: "- **word** – meaning"
                    # Try multiple patterns to catch variations
                    word_patterns = [
                        r'^-\s+\*?\*?([^*\n-:]+?)\*?\*?\s*[–-]\s*(.+)$',  # With dash separator
                        r'^-\s+\*?\*?([^*\n:]+?)\*?\*?\s*:\s*(.+)$',  # With colon separator
                    ]
                    
                    matched = False
                    for word_pattern in word_patterns:
                        match = re.match(word_pattern, line)
                        if match:
                            word = match.group(1).strip()
                            meaning = match.group(2).strip()
                            
                            # Only bold if it's not already bold and looks like a Sanskrit word
                            # (contains Devanagari or transliteration markers)
                            if not word.startswith('**') and not word.endswith('**'):
                                # Check if it looks like Sanskrit (Devanagari or transliteration)
                                has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in word)
                                has_translit_markers = any(c in word for c in ['ā', 'ī', 'ū', 'ṛ', 'ṝ', 'ḷ', 'ē', 'ō', 'ṃ', 'ḥ', 'ś', 'ṣ', 'ñ'])
                                # Also check for transliteration in parentheses/brackets
                                has_translit_in_parens = bool(re.search(r'[\(\[].*[āīūṛṝḷēōṃḥśṣñ].*[\)\]]', word))
                                
                                if has_devanagari or has_translit_markers or has_translit_in_parens or len(word) < 30:  # Likely a word, not a phrase
                                    word = f"**{word}**"
                            
                            # Always use en dash for separator
                            line = f"- {word} – {meaning}"
                            matched = True
                            break
                    
                    # If no pattern matched, just ensure en dash is used
                    if not matched:
                        line = re.sub(r'[—\-]', '–', line)
                
                normalized_lines.append(line)
                continue
            
            # Normalize regular content lines
            # Remove excessive whitespace but preserve intentional line breaks
            if line.strip():
                # Normalize spacing (multiple spaces to single space, but preserve line structure)
                line = re.sub(r'[ \t]+', ' ', line)
                normalized_lines.append(line)
            else:
                # Preserve empty lines (but only one consecutive empty line)
                if normalized_lines and normalized_lines[-1].strip():
                    normalized_lines.append('')
        
        # Join lines and normalize final spacing
        normalized_text = '\n'.join(normalized_lines)
        
        # Final cleanup: ensure consistent spacing around section headers
        # Add blank line before section headers (except first one)
        normalized_text = re.sub(r'\n(\d+\.\s+[A-Z][A-Z\s/&-]+:)', r'\n\n\1', normalized_text)
        normalized_text = re.sub(r'^\n+', '', normalized_text)  # Remove leading newlines
        normalized_text = re.sub(r'\n{3,}', '\n\n', normalized_text)  # Max 2 consecutive newlines
        
        return normalized_text.strip()
    
    def _generate_reflection_prompt(self, text: str) -> str:
        """Generate a reflection prompt based on explanation content."""
        # Extract key concepts from text
        key_concepts = []
        if 'action' in text.lower() or 'karma' in text.lower():
            key_concepts.append('actions and their outcomes')
        if 'detachment' in text.lower() or 'non-attachment' in text.lower():
            key_concepts.append('detachment from results')
        if 'duty' in text.lower() or 'dharma' in text.lower():
            key_concepts.append('your duties and responsibilities')
        if 'wisdom' in text.lower() or 'understanding' in text.lower():
            key_concepts.append('wisdom and understanding')
        
        if key_concepts:
            concept = key_concepts[0]
            return f"How can I apply the wisdom of this shloka regarding {concept} in my daily life? What changes would this bring to my perspective and actions?"
        else:
            return "How can I apply the wisdom of this shloka in my daily life? What changes would this bring to my perspective and actions?"
    
    def _build_prompt(self, shloka: dict, explanation_type: str, book_context: Optional[dict] = None, reduce_context: bool = False) -> str:
        """
        Build a standardized prompt for Groq API with book context.
        
        CRITICAL: This method maintains format consistency across all shlokas.
        The prompt structure MUST remain consistent to ensure all AI-generated
        explanations follow the same format. Do not modify the structure without
        careful consideration of the impact on format consistency.
        
        This method ensures consistent prompt format across all shloka explanations.
        The format is always the same structure, regardless of optional fields.
        Book context is included in a standardized way when available.
        
        Args:
            shloka: Dictionary containing shloka data with keys:
                - book_name (str): Name of the book
                - chapter_number (int): Chapter number
                - verse_number (int): Verse number
                - sanskrit_text (str): Sanskrit text (required)
                - transliteration (str, optional): Transliteration in Roman script
            explanation_type: Either 'summary' or 'detailed'
            book_context: Optional dictionary with 'english_context' and 'hindi_context' keys
            
        Returns:
            Formatted prompt string with consistent structure
            
        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        if not shloka.get('sanskrit_text'):
            raise ValueError("sanskrit_text is required for generating explanations")
        
        # Get word limit based on explanation type
        word_limit = self.SUMMARY_WORD_LIMIT if explanation_type == "summary" else self.DETAILED_WORD_LIMIT
        
        # Extract shloka information with defaults
        book_name = shloka.get('book_name', 'Bhagavad Gita')
        chapter_number = shloka.get('chapter_number', '')
        verse_number = shloka.get('verse_number', '')
        sanskrit_text = shloka.get('sanskrit_text', '')
        transliteration = shloka.get('transliteration', '').strip()
        
        # Build standardized prompt with consistent structure
        # This format ensures all prompts follow the same structure
        prompt_parts = [
            f"Explain this shloka from {book_name}",
        ]
        
        # Add chapter and verse information if available
        if chapter_number and verse_number:
            prompt_parts.append(f"Chapter {chapter_number}, Verse {verse_number}")
        elif chapter_number:
            prompt_parts.append(f"Chapter {chapter_number}")
        elif verse_number:
            prompt_parts.append(f"Verse {verse_number}")
        
        prompt_parts.append(":")
        prompt_parts.append("")  # Empty line
        prompt_parts.append("Sanskrit Text:")
        prompt_parts.append(sanskrit_text)
        prompt_parts.append("")  # Empty line
        
        # Add transliteration if available (always in same format)
        if transliteration:
            prompt_parts.append("Transliteration:")
            prompt_parts.append(transliteration)
            prompt_parts.append("")  # Empty line
        
        # Add book context if available (standardized format)
        if book_context:
            context_added = False
            
            # Add English context if available
            if book_context.get('english_context'):
                context_text = book_context['english_context']
                # If reduce_context is True, truncate context to save tokens
                if reduce_context:
                    # Limit context to first 500 characters
                    context_text = context_text[:500] + "..." if len(context_text) > 500 else context_text
                prompt_parts.append("Reference Context (English Translation):")
                prompt_parts.append(context_text)
                prompt_parts.append("")  # Empty line
                context_added = True
            
            # Add Hindi context if available
            if book_context.get('hindi_context'):
                context_text = book_context['hindi_context']
                # If reduce_context is True, truncate context to save tokens
                if reduce_context:
                    # Limit context to first 500 characters
                    context_text = context_text[:500] + "..." if len(context_text) > 500 else context_text
                prompt_parts.append("Reference Context (Hindi Translation):")
                prompt_parts.append(context_text)
                prompt_parts.append("")  # Empty line
                context_added = True
            
            if context_added:
                prompt_parts.append("Use the above reference context from authoritative translations to inform your explanation, ensuring accuracy and alignment with traditional interpretations.")
                prompt_parts.append("")  # Empty line
        
        # Add explanation requirements (always the same structure)
        # ALL explanations MUST include: Meaning, Word-by-word, Explanation, Practical Application, Example
        if explanation_type == "detailed":
            # For detailed explanations, include comprehensive word-by-word breakdown
            # If reduce_context is True, use a more concise prompt
            if reduce_context:
                prompt_parts.append(f"Provide a {explanation_type} explanation ({word_limit}) in modern, accessible language. The explanation MUST follow this EXACT structure:")
                prompt_parts.append("")
                prompt_parts.append("1. MEANING: Core meaning and philosophical significance")
                prompt_parts.append("2. WORD-BY-WORD: Break down EACH word systematically with format '- **word** – meaning'")
                prompt_parts.append("3. EXPLANATION: Deeper understanding and interpretation")
                prompt_parts.append("4. PRACTICAL APPLICATION: How this applies to daily life")
                prompt_parts.append("5. EXAMPLES: 1-2 concrete modern examples")
                prompt_parts.append("")
                prompt_parts.append("CRITICAL: ALL 5 sections are MANDATORY. Use bullet points (-), NOT tables. Use en dash (–) between word and meaning.")
            else:
                # For detailed explanations, include comprehensive word-by-word breakdown
                prompt_parts.append(f"Provide a {explanation_type} explanation ({word_limit}) in modern, accessible language. The explanation MUST follow this EXACT structure with clear section headers:")
                prompt_parts.append("")
                prompt_parts.append("1. MEANING:")
                prompt_parts.append("   - Core meaning and philosophical significance")
                prompt_parts.append("   - Context within the broader text and chapter")
                prompt_parts.append("   - Overall essence of the shloka")
                prompt_parts.append("")
                prompt_parts.append("2. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN:")
                prompt_parts.append("   - Break down EACH word or statement in the shloka systematically")
                prompt_parts.append("   - For each word/phrase, provide:")
                prompt_parts.append("     * The Sanskrit word (or transliteration if Sanskrit is not available)")
                prompt_parts.append("     * Its literal meaning")
                prompt_parts.append("     * Its grammatical role and significance in the sentence")
                prompt_parts.append("     * How it connects to other words in the shloka")
                prompt_parts.append("   - Explain each statement or phrase as a unit, showing how words combine")
                prompt_parts.append("   - Use clear formatting with bullet points (dashes) for each word/statement - NEVER use tables")
                prompt_parts.append("")
                prompt_parts.append("3. EXPLANATION:")
                prompt_parts.append("   - Deeper understanding and interpretation of the teaching")
                prompt_parts.append("   - Synthesize the word-by-word breakdown into the complete, unified meaning")
                prompt_parts.append("   - Key insights, wisdom, and philosophical depth")
                prompt_parts.append("   - How the words work together to convey the message")
                prompt_parts.append("")
                prompt_parts.append("4. PRACTICAL APPLICATION:")
                prompt_parts.append("   - How this wisdom applies to daily life")
                prompt_parts.append("   - Contemporary relevance and real-world applications")
                prompt_parts.append("   - Actionable insights for modern living")
                prompt_parts.append("")
                prompt_parts.append("5. EXAMPLES:")
                prompt_parts.append("   - Provide 1-2 concrete, relatable examples that illustrate the teaching")
                prompt_parts.append("   - Examples should be from modern life situations")
                prompt_parts.append("   - Make them specific and easy to understand")
                prompt_parts.append("")
                prompt_parts.append("CRITICAL FORMATTING REQUIREMENTS:")
                prompt_parts.append("- Use clear section headers exactly as shown above (1., 2., 3., 4., 5.)")
                prompt_parts.append("- ALL 5 sections are MANDATORY and MUST be included: Meaning, Word-by-word, Explanation, Practical Application, Examples")
                prompt_parts.append("- DO NOT skip any section. Every explanation MUST have all 5 sections.")
                prompt_parts.append("- The word-by-word breakdown is essential - explain EVERY word or statement")
                prompt_parts.append("- Format it clearly and systematically")
                prompt_parts.append("- Make it engaging and relevant for contemporary readers while respecting the traditional wisdom")
                prompt_parts.append("")
                prompt_parts.append("FORMAT RESTRICTIONS:")
                prompt_parts.append("- DO NOT use tables, markdown tables, or any tabular format")
                prompt_parts.append("- Use ONLY list format with bullet points (-) or numbered lists")
                prompt_parts.append("- For word-by-word breakdown, use EXACTLY this format: '- **word** – meaning'")
                prompt_parts.append("  * Use en dash (–) NOT hyphen (-) or em dash (—) between word and meaning")
                prompt_parts.append("  * Bold the Sanskrit word using **word**")
                prompt_parts.append("  * Use single space after dash, no extra spaces")
                prompt_parts.append("- All bullet points must start with '- ' (dash and space)")
                prompt_parts.append("- Section headers must end with colon (e.g., '1. MEANING:')")
                prompt_parts.append("- All content must be in plain text list format, never in table format")
                prompt_parts.append("- Use consistent punctuation: periods at end of sentences, no trailing periods on bullet points unless they are complete sentences")
                prompt_parts.append("")
                prompt_parts.append("VALIDATION CHECK: Before submitting your response, verify that you have included:")
                prompt_parts.append("✓ 1. MEANING section")
                prompt_parts.append("✓ 2. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN section")
                prompt_parts.append("✓ 3. EXPLANATION section")
                prompt_parts.append("✓ 4. PRACTICAL APPLICATION section")
                prompt_parts.append("✓ 5. EXAMPLES section (with at least 1-2 examples)")
                prompt_parts.append("If any section is missing, your response will be rejected. Ensure ALL sections are present.")
        else:
            # For summary explanations, include all sections but more concise
            # If reduce_context is True, use a more concise prompt
            if reduce_context:
                prompt_parts.append(f"Provide a {explanation_type} explanation ({word_limit}) in modern, accessible language. The explanation MUST follow this EXACT structure:")
                prompt_parts.append("")
                prompt_parts.append("1. MEANING: Core meaning and brief context")
                prompt_parts.append("2. WORD-BY-WORD: Brief breakdown with format '- **word** – meaning'")
                prompt_parts.append("3. EXPLANATION: Key insights and wisdom")
                prompt_parts.append("4. PRACTICAL APPLICATION: Daily life relevance")
                prompt_parts.append("5. EXAMPLE: 1 concrete modern example")
                prompt_parts.append("")
                prompt_parts.append("CRITICAL: ALL 5 sections are MANDATORY. Use bullet points (-), NOT tables. Use en dash (–) between word and meaning.")
            else:
                prompt_parts.append(f"Provide a {explanation_type} explanation ({word_limit}) in modern, accessible language. The explanation MUST follow this EXACT structure with clear section headers:")
                prompt_parts.append("")
                prompt_parts.append("1. MEANING:")
                prompt_parts.append("   - Core meaning and philosophical significance")
                prompt_parts.append("   - Brief context within the broader text")
                prompt_parts.append("")
                prompt_parts.append("2. WORD-BY-WORD:")
                prompt_parts.append("   - Brief word-by-word or phrase-by-phrase breakdown")
                prompt_parts.append("   - Key words and their meanings")
                prompt_parts.append("   - How the words combine to form the meaning")
                prompt_parts.append("")
                prompt_parts.append("3. EXPLANATION:")
                prompt_parts.append("   - Deeper understanding of the teaching")
                prompt_parts.append("   - Key insights and wisdom")
                prompt_parts.append("   - Interpretation and significance")
                prompt_parts.append("")
                prompt_parts.append("4. PRACTICAL APPLICATION:")
                prompt_parts.append("   - How this wisdom applies to daily life")
                prompt_parts.append("   - Contemporary relevance")
                prompt_parts.append("")
                prompt_parts.append("5. EXAMPLE:")
                prompt_parts.append("   - Provide 1 concrete, relatable example that illustrates the teaching")
                prompt_parts.append("   - Example should be from modern life situations")
                prompt_parts.append("   - Make it specific and easy to understand")
                prompt_parts.append("")
                prompt_parts.append("CRITICAL FORMATTING REQUIREMENTS:")
                prompt_parts.append("- Use clear section headers exactly as shown above (1., 2., 3., 4., 5.)")
                prompt_parts.append("- ALL 5 sections are MANDATORY and MUST be included: Meaning, Word-by-word, Explanation, Practical Application, Example")
                prompt_parts.append("- DO NOT skip any section. Every explanation MUST have all 5 sections.")
                prompt_parts.append("- Keep it concise but complete - include all sections")
                prompt_parts.append("- Make it engaging and relevant for contemporary readers while respecting the traditional wisdom")
                prompt_parts.append("")
                prompt_parts.append("FORMAT RESTRICTIONS:")
                prompt_parts.append("- DO NOT use tables, markdown tables, or any tabular format")
                prompt_parts.append("- Use ONLY list format with bullet points (-) or numbered lists")
                prompt_parts.append("- For word-by-word breakdown, use EXACTLY this format: '- **word** – meaning'")
                prompt_parts.append("  * Use en dash (–) NOT hyphen (-) or em dash (—) between word and meaning")
                prompt_parts.append("  * Bold the Sanskrit word using **word**")
                prompt_parts.append("  * Use single space after dash, no extra spaces")
                prompt_parts.append("- All bullet points must start with '- ' (dash and space)")
                prompt_parts.append("- Section headers must end with colon (e.g., '1. MEANING:')")
                prompt_parts.append("- All content must be in plain text list format, never in table format")
                prompt_parts.append("- Use consistent punctuation: periods at end of sentences, no trailing periods on bullet points unless they are complete sentences")
                prompt_parts.append("")
                prompt_parts.append("VALIDATION CHECK: Before submitting your response, verify that you have included:")
                prompt_parts.append("✓ 1. MEANING section")
                prompt_parts.append("✓ 2. WORD-BY-WORD section")
                prompt_parts.append("✓ 3. EXPLANATION section")
                prompt_parts.append("✓ 4. PRACTICAL APPLICATION section")
                prompt_parts.append("✓ 5. EXAMPLE section (with at least 1 example)")
                prompt_parts.append("If any section is missing, your response will be rejected. Ensure ALL sections are present.")
        
        # Join all parts with newlines to ensure consistent formatting
        prompt = "\n".join(prompt_parts)
        
        return prompt

