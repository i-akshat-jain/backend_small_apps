"""
Improvement service for Shloka explanations.

Provides targeted improvements to specific sections based on quality feedback.
Implements iterative refinement with preservation of high-quality content.

CRITICAL: This service handles religious content and must maintain the highest
standards of accuracy. All improvements are validated before saving, and original
content is preserved to allow rollback if quality degrades.
"""
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from apps.sanatan_app.models import ShlokaExplanation, Shloka
from apps.sanatan_app.groq_service import GroqService
from apps.sanatan_app.services.quality_checker import QualityCheckerService
import logging
import copy

logger = logging.getLogger(__name__)


class ImprovementService:
    """Service for improving explanation quality through targeted section improvements.
    
    CRITICAL SAFETY FEATURES:
    - Validates improvements before saving (only saves if quality improves or stays same)
    - Preserves original content for rollback if quality degrades
    - Uses lower temperature (0.2) for maximum accuracy with religious content
    - Includes quality feedback in prompts to guide improvements
    - Requires minimum improvement threshold to prevent marginal changes
    """
    
    MAX_IMPROVEMENT_ITERATIONS = 5  # Increased to allow more attempts
    MIN_SCORE_THRESHOLD = 95  # Only improve sections with scores below this threshold
    MIN_IMPROVEMENT_DELTA = 0.5  # Minimum score improvement required (must actually improve, not just stay same)
    
    # Section field mappings
    SECTION_FIELDS = {
        'summary': 'summary',
        'detailed_meaning': 'detailed_meaning',
        'detailed_explanation': 'detailed_explanation',
        'context': 'context',
        'why_this_matters': 'why_this_matters',
        'modern_examples': 'modern_examples',
        'themes': 'themes',
        'reflection_prompt': 'reflection_prompt',
    }
    
    def __init__(self):
        self.groq_service = GroqService()
        self.quality_checker = QualityCheckerService()
    
    def _clean_corrupted_json_fields(self, explanation: ShlokaExplanation) -> bool:
        """
        Clean corrupted JSON fields in an explanation before processing.
        
        Args:
            explanation: ShlokaExplanation instance to clean
            
        Returns:
            True if any cleaning was done, False otherwise
        """
        cleaned = False
        
        # Clean themes field
        if explanation.themes:
            try:
                import json
                # Test if themes can be serialized
                json.dumps(explanation.themes)
                # Validate structure
                if isinstance(explanation.themes, list):
                    cleaned_themes = []
                    for item in explanation.themes:
                        if isinstance(item, str):
                            cleaned_themes.append(item)
                        elif isinstance(item, list) and len(item) > 0:
                            # Flatten nested lists
                            cleaned_themes.append(str(item[0]) if item[0] else "")
                        else:
                            cleaned_themes.append(str(item) if item else "")
                    if cleaned_themes != explanation.themes:
                        explanation.themes = cleaned_themes
                        cleaned = True
                        logger.info(f"Cleaned corrupted themes field for explanation {explanation.id}")
            except (TypeError, ValueError) as e:
                logger.warning(f"Found corrupted themes field, resetting: {e}")
                explanation.themes = []
                cleaned = True
        
        # Clean modern_examples field
        if explanation.modern_examples:
            try:
                import json
                # Test if modern_examples can be serialized
                json.dumps(explanation.modern_examples)
                # Validate structure
                if isinstance(explanation.modern_examples, list):
                    cleaned_examples = []
                    for item in explanation.modern_examples:
                        if isinstance(item, dict):
                            cleaned_item = {
                                'category': str(item.get('category', '')),
                                'description': str(item.get('description', ''))
                            }
                            cleaned_examples.append(cleaned_item)
                        elif isinstance(item, list):
                            # Skip nested lists
                            logger.warning(f"Skipping nested list in modern_examples: {item}")
                            continue
                        else:
                            # Skip invalid items
                            continue
                    if cleaned_examples != explanation.modern_examples:
                        explanation.modern_examples = cleaned_examples
                        cleaned = True
                        logger.info(f"Cleaned corrupted modern_examples field for explanation {explanation.id}")
            except (TypeError, ValueError) as e:
                logger.warning(f"Found corrupted modern_examples field, resetting: {e}")
                explanation.modern_examples = []
                cleaned = True
        
        if cleaned:
            # Save the cleaned data
            try:
                explanation.save(update_fields=['modern_examples', 'themes'])
            except Exception as e:
                logger.error(f"Failed to save cleaned data: {e}")
                return False
        
        return cleaned
    
    def improve_explanation(
        self, 
        explanation: ShlokaExplanation,
        max_iterations: int = MAX_IMPROVEMENT_ITERATIONS,
        min_score_threshold: int = MIN_SCORE_THRESHOLD
    ) -> Dict:
        """
        Improve an explanation through iterative refinement.
        
        CRITICAL: Also checks and fills missing Shloka data (transliteration, word_by_word)
        before improving the explanation.
        
        Args:
            explanation: ShlokaExplanation instance to improve
            max_iterations: Maximum number of improvement iterations (default: 3)
            min_score_threshold: Only improve if overall score is below this (default: 95)
            
        Returns:
            Dictionary with:
            - success: Whether improvement was successful
            - iterations: Number of iterations performed
            - initial_score: Initial quality score
            - final_score: Final quality score after improvement
            - improvements_made: List of sections that were improved
            - shloka_fixes: List of Shloka fields that were filled
            - message: Status message
        """
        logger.info(f"Starting improvement process for explanation {explanation.id}")
        
        # CRITICAL: First check and fill missing Shloka data
        shloka = explanation.shloka
        shloka_fixes = self._check_and_fill_shloka_data(shloka)
        if shloka_fixes:
            logger.info(f"Fixed missing Shloka data: {', '.join(shloka_fixes)}")
        
        # CRITICAL: Clean any corrupted JSON fields before processing
        if self._clean_corrupted_json_fields(explanation):
            logger.info(f"Cleaned corrupted JSON fields for explanation {explanation.id}")
            explanation.refresh_from_db()
        
        # Check initial quality
        initial_quality = self.quality_checker.check_quality(explanation)
        initial_score = initial_quality['overall_score']
        
        # If already above threshold, no improvement needed
        if initial_score >= min_score_threshold:
            logger.info(
                f"Explanation {explanation.id} already has high quality score ({initial_score}/100). "
                f"Skipping improvement."
            )
            return {
                'success': True,
                'iterations': 0,
                'initial_score': initial_score,
                'final_score': initial_score,
                'improvements_made': [],
                'shloka_fixes': shloka_fixes,
                'message': f'Explanation already meets quality threshold ({initial_score}/100)'
            }
        
        improvements_made = []
        current_explanation = explanation
        current_score = initial_score
        
        # CRITICAL: Save original state for rollback if needed
        original_state = self._save_explanation_state(explanation)
        
        # Perform iterative improvements - keep trying until quality improves or threshold reached
        consecutive_failures = 0
        max_consecutive_failures = 3  # Stop if we fail 3 times in a row
        
        for iteration in range(1, max_iterations + 1):
            logger.info(
                f"Iteration {iteration}/{max_iterations} for explanation {explanation.id}. "
                f"Current score: {current_score}/100 (target: {min_score_threshold})"
            )
            
            # If we've reached the threshold, stop
            if current_score >= min_score_threshold:
                logger.info(
                    f"✓ Reached quality threshold ({current_score}/100) after iteration {iteration-1}"
                )
                break
            
            # Re-check quality to get fresh feedback
            current_quality = self.quality_checker.check_quality(current_explanation)
            current_score_from_check = current_quality['overall_score']
            
            # Update current_score if quality check shows different value (shouldn't happen, but be safe)
            if abs(current_score_from_check - current_score) > 1.0:
                logger.warning(
                    f"Score mismatch: stored={current_score:.2f}, checked={current_score_from_check:.2f}. "
                    f"Using checked value."
                )
                current_score = current_score_from_check
            
            # Identify sections that need improvement
            sections_to_improve = self._identify_sections_to_improve(
                current_explanation, 
                current_quality,
                min_score_threshold
            )
            
            if not sections_to_improve:
                logger.info(f"No more sections need improvement after iteration {iteration}")
                # If we're still below threshold but no sections to improve, try improving all sections
                if current_score < min_score_threshold:
                    logger.info("Still below threshold - trying to improve all sections...")
                    sections_to_improve = list(self.SECTION_FIELDS.keys())
            
            # CRITICAL: Save state before making changes (for rollback)
            pre_improvement_state = self._save_explanation_state(current_explanation)
            pre_improvement_score = current_score
            
            # Improve identified sections
            improved_sections = self._improve_sections(
                current_explanation,
                sections_to_improve,
                current_quality  # Pass quality feedback to guide improvements
            )
            
            if improved_sections:
                # CRITICAL: Validate improvement before saving - must actually improve
                updated_quality = self.quality_checker.check_quality(current_explanation)
                new_score = updated_quality['overall_score']
                score_delta = new_score - pre_improvement_score
                
                logger.info(
                    f"Quality check after improvement: {pre_improvement_score:.2f} → {new_score:.2f} "
                    f"(Δ{score_delta:+.2f}, required: ≥{self.MIN_IMPROVEMENT_DELTA})"
                )
                
                # Only save if quality actually improved (not just stayed same)
                if score_delta >= self.MIN_IMPROVEMENT_DELTA:
                    improvements_made.extend(improved_sections)
                    current_score = new_score
                    consecutive_failures = 0  # Reset failure counter on success
                    
                    # Update quality tracking
                    current_explanation.quality_score = int(current_score)
                    current_explanation.quality_checked_at = timezone.now()
                    current_explanation.improvement_version = iteration
                    current_explanation.save(update_fields=[
                        'quality_score', 
                        'quality_checked_at', 
                        'improvement_version',
                        'summary',
                        'detailed_meaning',
                        'detailed_explanation',
                        'context',
                        'why_this_matters',
                        'modern_examples',
                        'themes',
                        'reflection_prompt',
                    ])
                    
                    logger.info(
                        f"✓ Improvement validated and saved. Score: {pre_improvement_score:.2f} → {new_score:.2f}"
                    )
                    
                    # Continue to next iteration to see if we can improve further
                    continue
                else:
                    # Quality didn't improve enough - rollback and try again
                    consecutive_failures += 1
                    logger.warning(
                        f"⚠ Quality didn't improve enough (Δ{score_delta:+.2f} < {self.MIN_IMPROVEMENT_DELTA}). "
                        f"Rolling back and trying different approach. "
                        f"Consecutive failures: {consecutive_failures}/{max_consecutive_failures}"
                    )
                    self._restore_explanation_state(current_explanation, pre_improvement_state)
                    current_score = pre_improvement_score
                    current_explanation.refresh_from_db()
                    
                    # If we've failed too many times in a row, stop
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            f"Stopping after {consecutive_failures} consecutive failures. "
                            f"Current score: {current_score:.2f}/100"
                        )
                        break
                    # Otherwise, continue to next iteration
                    continue
            else:
                consecutive_failures += 1
                logger.warning(
                    f"No improvements could be made in iteration {iteration}. "
                    f"Consecutive failures: {consecutive_failures}/{max_consecutive_failures}"
                )
                
                # If we've failed too many times, stop
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        f"Stopping after {consecutive_failures} consecutive failures. "
                        f"Current score: {current_score:.2f}/100"
                    )
                    break
                # Otherwise, continue to next iteration
                continue
        
        final_score = current_score
        improvement_delta = final_score - initial_score
        
        logger.info(
            f"Improvement complete for explanation {explanation.id}. "
            f"Score: {initial_score} -> {final_score} (Δ{improvement_delta:+.1f})"
        )
        
        return {
            'success': True,
            'iterations': iteration,
            'initial_score': initial_score,
            'final_score': final_score,
            'improvement_delta': improvement_delta,
            'improvements_made': list(set(improvements_made)),  # Remove duplicates
            'shloka_fixes': shloka_fixes,
            'message': f'Improved from {initial_score} to {final_score} in {iteration} iteration(s)'
        }
    
    def _identify_sections_to_improve(
        self,
        explanation: ShlokaExplanation,
        quality_result: Dict,
        min_score_threshold: int
    ) -> List[str]:
        """
        Identify which sections need improvement based on quality feedback.
        
        Args:
            explanation: ShlokaExplanation instance
            quality_result: Quality check result from QualityCheckerService
            min_score_threshold: Minimum acceptable score threshold
            
        Returns:
            List of section names that need improvement
        """
        sections_to_improve = []
        feedback = quality_result.get('feedback', {})
        
        # Check completeness feedback for missing/empty sections
        completeness_feedback = feedback.get('completeness', '')
        if 'Missing sections' in completeness_feedback or 'Empty sections' in completeness_feedback:
            # Extract missing/empty sections from feedback
            if 'Missing sections:' in completeness_feedback:
                missing_part = completeness_feedback.split('Missing sections:')[1].split('|')[0].strip()
                missing_sections = [s.strip() for s in missing_part.split(',')]
                sections_to_improve.extend(missing_sections)
            
            if 'Empty sections:' in completeness_feedback:
                empty_part = completeness_feedback.split('Empty sections:')[1].strip()
                empty_sections = [s.strip() for s in empty_part.split(',')]
                sections_to_improve.extend(empty_sections)
        
        # Check clarity feedback for sections that need clarity improvement
        clarity_feedback = feedback.get('clarity', '')
        if clarity_feedback and 'unclear' in clarity_feedback.lower():
            # If clarity is low, improve main explanation sections
            if not explanation.detailed_meaning or len(explanation.detailed_meaning) < 50:
                sections_to_improve.append('detailed_meaning')
            if not explanation.detailed_explanation or len(explanation.detailed_explanation) < 50:
                sections_to_improve.append('detailed_explanation')
        
        # Check relevance feedback
        relevance_feedback = feedback.get('relevance', '')
        if relevance_feedback and ('irrelevant' in relevance_feedback.lower() or 'not relevant' in relevance_feedback.lower()):
            if not explanation.why_this_matters or len(explanation.why_this_matters) < 50:
                sections_to_improve.append('why_this_matters')
            if not explanation.modern_examples or len(explanation.modern_examples) == 0:
                sections_to_improve.append('modern_examples')
        
        # Check accuracy feedback
        accuracy_feedback = feedback.get('accuracy', '')
        if accuracy_feedback and ('inaccurate' in accuracy_feedback.lower() or 'incorrect' in accuracy_feedback.lower()):
            # Improve meaning and explanation sections for accuracy
            sections_to_improve.extend(['detailed_meaning', 'detailed_explanation'])
        
        # Remove duplicates and return
        return list(set(sections_to_improve))
    
    def _improve_sections(
        self,
        explanation: ShlokaExplanation,
        sections: List[str],
        quality_result: Dict
    ) -> List[str]:
        """
        Improve specific sections of an explanation.
        
        Args:
            explanation: ShlokaExplanation instance to improve
            sections: List of section names to improve
            quality_result: Quality check result with feedback to guide improvements
            
        Returns:
            List of section names that were successfully improved
        """
        improved_sections = []
        shloka = explanation.shloka
        
        for section_name in sections:
            try:
                logger.info(f"Improving section '{section_name}' for explanation {explanation.id}")
                
                # Get improvement prompt for this section (includes quality feedback)
                improvement_prompt = self._build_improvement_prompt(
                    explanation,
                    shloka,
                    section_name,
                    quality_result  # Pass quality feedback
                )
                
                # Call Groq API to get improved content
                # CRITICAL: Use lower temperature (0.2) for maximum accuracy with religious content
                response = self.groq_service.client.chat.completions.create(
                    model=self.groq_service.model,
                    messages=[
                        {"role": "system", "content": self._get_improvement_system_message()},
                        {"role": "user", "content": improvement_prompt}
                    ],
                    temperature=0.2,  # Lower temperature for maximum accuracy (critical for religious content)
                    max_tokens=2000,
                )
                
                improved_content = response.choices[0].message.content.strip()
                
                # Parse and update the section
                if self._update_section(explanation, section_name, improved_content):
                    improved_sections.append(section_name)
                    logger.info(f"Successfully improved section '{section_name}'")
                else:
                    logger.warning(f"Failed to parse improved content for section '{section_name}'")
                    
            except Exception as e:
                logger.error(f"Error improving section '{section_name}': {str(e)}")
                continue
        
        return improved_sections
    
    def _build_improvement_prompt(
        self,
        explanation: ShlokaExplanation,
        shloka: Shloka,
        section_name: str,
        quality_result: Dict
    ) -> str:
        """
        Build a targeted improvement prompt for a specific section.
        Includes quality feedback to guide improvements.
        
        Args:
            explanation: ShlokaExplanation instance
            shloka: Shloka instance
            section_name: Name of the section to improve
            quality_result: Quality check result with feedback
            
        Returns:
            Improvement prompt string
        """
        # Safely get current content, handling corrupted JSON data
        try:
            current_content = getattr(explanation, section_name, None)
            # For JSON fields, convert to JSON string for display
            if section_name in ['modern_examples', 'themes'] and current_content:
                try:
                    import json
                    current_content = json.dumps(current_content, indent=2, ensure_ascii=False)
                except (TypeError, ValueError) as e:
                    # If data is corrupted and can't be serialized, use a safe representation
                    logger.warning(f"Could not serialize existing {section_name} for prompt: {e}")
                    current_content = "[Corrupted data - will be replaced]"
            elif not current_content:
                current_content = ""
            else:
                current_content = str(current_content) if current_content else ""
        except Exception as e:
            logger.warning(f"Error accessing current {section_name} content: {e}")
            current_content = "[Error accessing current content]"
        
        section_descriptions = {
            'summary': 'a brief overview (2-3 sentences) that captures the essence of the shloka',
            'detailed_meaning': 'the core meaning and philosophical significance of the shloka',
            'detailed_explanation': 'a deeper understanding and interpretation of the teaching',
            'context': 'the context of when/why this was said, including its place in the dialogue or story',
            'why_this_matters': 'why this teaching is relevant and important for modern life',
            'modern_examples': 'concrete modern examples as a JSON array of objects with "category" and "description" fields',
            'themes': 'key themes/tags as a JSON array of strings',
            'reflection_prompt': 'a thoughtful question for contemplation',
        }
        
        section_description = section_descriptions.get(section_name, 'this section')
        
        # Extract relevant quality feedback
        feedback = quality_result.get('feedback', {})
        relevant_feedback = []
        
        # Add feedback that's relevant to this section
        if section_name in ['detailed_meaning', 'detailed_explanation']:
            if feedback.get('clarity'):
                relevant_feedback.append(f"Clarity feedback: {feedback['clarity']}")
            if feedback.get('accuracy'):
                relevant_feedback.append(f"Accuracy feedback: {feedback['accuracy']}")
        elif section_name in ['why_this_matters', 'modern_examples']:
            if feedback.get('relevance'):
                relevant_feedback.append(f"Relevance feedback: {feedback['relevance']}")
        elif section_name == 'context':
            if feedback.get('completeness'):
                relevant_feedback.append(f"Completeness feedback: {feedback['completeness']}")
        
        prompt_parts = [
            f"CRITICAL: You are improving religious content that is deeply meaningful to people.",
            f"Accuracy and respect for traditional interpretations are paramount.",
            "",
            f"IMPORTANT: This improvement MUST significantly enhance the quality of the '{section_name}' section.",
            f"The current content needs substantial improvement to meet high quality standards.",
            f"Make meaningful, substantial improvements - not just minor tweaks.",
            "",
            f"Improve the '{section_name}' section of this shloka explanation.",
            "",
            f"Shloka: {shloka.book_name} - Chapter {shloka.chapter_number}, Verse {shloka.verse_number}",
            f"Sanskrit: {shloka.sanskrit_text}",
            "",
            f"Current {section_name} content:",
            current_content if current_content else "[Empty or missing]",
            "",
        ]
        
        # Add quality feedback to guide improvements
        if relevant_feedback:
            prompt_parts.extend([
                "Quality feedback to address:",
                *[f"- {fb}" for fb in relevant_feedback],
                "",
            ])
        
        prompt_parts.extend([
            f"Please provide an improved version of {section_description}.",
            "",
        ])
        
        # Add section-specific guidance
        if section_name == 'modern_examples':
            prompt_parts.extend([
                "CRITICAL FORMAT REQUIREMENTS:",
                "- You MUST return a valid JSON array of objects",
                "- Each object MUST have exactly two fields: 'category' and 'description'",
                "- Both 'category' and 'description' MUST be strings (not arrays or objects)",
                "- Example format: [{\"category\": \"In Your Career\", \"description\": \"When facing ethical dilemmas at work...\"}, {\"category\": \"In Relationships\", \"description\": \"When dealing with family conflicts...\"}]",
                "- Return ONLY the JSON array, nothing else (no explanations, no markdown, no code blocks)",
            ])
        elif section_name == 'themes':
            prompt_parts.extend([
                "CRITICAL FORMAT REQUIREMENTS:",
                "- You MUST return a valid JSON array of strings",
                "- Each element MUST be a string (not an array, not an object)",
                "- Example format: [\"Dharma\", \"Karma\", \"Wisdom\", \"Self-Realization\"]",
                "- Return ONLY the JSON array, nothing else (no explanations, no markdown, no code blocks)",
            ])
        elif section_name in ['summary', 'detailed_meaning', 'detailed_explanation', 'context', 'why_this_matters']:
            prompt_parts.extend([
                "CRITICAL REQUIREMENTS:",
                "- Maintain 100% accuracy to traditional interpretations",
                "- Use clear, accessible language for modern readers",
                "- Preserve the spiritual and philosophical depth",
                "- Do not add interpretations that are not supported by traditional sources",
            ])
        
        prompt_parts.extend([
            "",
            "CRITICAL: Provide a SIGNIFICANTLY IMPROVED version that will increase the quality score.",
            "The improvement must be substantial and meaningful, addressing all quality feedback provided above.",
            "",
            "Provide ONLY the improved content for this section, nothing else.",
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_improvement_system_message(self) -> str:
        """Get system message for improvement prompts.
        
        CRITICAL: This message emphasizes accuracy and respect for religious content.
        """
        return """You are an expert in Hindu philosophy, Sanskrit literature, and the Bhagavad Gita.

CRITICAL: You are working with religious content that is deeply meaningful to millions of people.
Accuracy and respect for traditional interpretations are absolutely paramount.

Your task is to improve specific sections of shloka explanations while:
1. MAINTAINING 100% ACCURACY to traditional interpretations - never add interpretations not supported by traditional sources
2. Preserving the spiritual and philosophical depth of the original meaning
3. Making content clearer and more accessible to modern readers
4. Respecting the sacred nature of this content

Be precise and focused - only improve the requested section.
If you are uncertain about any interpretation, maintain the existing content rather than risk inaccuracy.
Never compromise accuracy for clarity or modern relevance."""
    
    def _update_section(
        self,
        explanation: ShlokaExplanation,
        section_name: str,
        improved_content: str
    ) -> bool:
        """
        Update a specific section of the explanation with improved content.
        
        Args:
            explanation: ShlokaExplanation instance
            section_name: Name of the section to update
            improved_content: Improved content from LLM
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # For JSON fields, parse and validate the content
            if section_name in ['modern_examples', 'themes']:
                import json
                # Try to extract JSON from the response
                # Sometimes LLM wraps JSON in markdown code blocks
                content = improved_content.strip()
                if content.startswith('```'):
                    # Extract JSON from code block
                    lines = content.split('\n')
                    json_lines = []
                    in_code_block = False
                    for line in lines:
                        if line.strip().startswith('```'):
                            in_code_block = not in_code_block
                            continue
                        if in_code_block:
                            json_lines.append(line)
                    content = '\n'.join(json_lines)
                
                # Check if content is empty or just whitespace
                if not content or not content.strip():
                    logger.warning(f"LLM returned empty content for {section_name}, keeping existing content")
                    return False
                
                # Try to parse as JSON
                parsed = None
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON for {section_name}: {content[:100]}. Error: {e}")
                    # If JSON parsing fails, try to extract a simple list from text (only for themes)
                    if section_name == 'themes':
                        # Try to extract themes from text (e.g., "Dharma, Karma, Wisdom")
                        themes = []
                        # Look for common patterns
                        if ',' in content:
                            themes = [t.strip().strip('"\'[]') for t in content.split(',') if t.strip()]
                        elif '\n' in content:
                            themes = [t.strip().strip('"\'[]-•') for t in content.split('\n') if t.strip() and not t.strip().startswith('#')]
                        if themes:
                            logger.info(f"Extracted {len(themes)} themes from text format, validating...")
                            parsed = themes
                        else:
                            logger.warning(f"Could not extract themes from malformed response, keeping existing content")
                            return False
                    else:
                        logger.warning(f"JSON parsing failed for {section_name} and no fallback available, keeping existing content")
                        return False
                
                # If we got here, we have a parsed value (either from JSON or text extraction)
                # Validate that parsed result is not empty
                if not parsed or (isinstance(parsed, list) and len(parsed) == 0):
                    logger.warning(f"Parsed {section_name} is empty, keeping existing content")
                    return False
                
                # CRITICAL: Validate structure before setting
                if section_name == 'themes':
                    # themes must be a list of strings
                    if not isinstance(parsed, list):
                        logger.error(f"themes must be a list, got {type(parsed).__name__}")
                        return False
                    # Validate each item is a string (not a list or dict)
                    validated_themes = []
                    for i, item in enumerate(parsed):
                        if isinstance(item, str):
                            validated_themes.append(item)
                        elif isinstance(item, (list, dict)):
                            logger.error(f"themes[{i}] is {type(item).__name__}, expected string. Flattening...")
                            # Try to extract string from nested structure
                            if isinstance(item, list) and len(item) > 0 and isinstance(item[0], str):
                                validated_themes.append(item[0])
                            else:
                                # Skip invalid items
                                continue
                        else:
                            # Convert to string if possible
                            validated_themes.append(str(item))
                    parsed = validated_themes
                    
                elif section_name == 'modern_examples':
                    # modern_examples must be a list of dicts with 'category' and 'description'
                    if not isinstance(parsed, list):
                        logger.error(f"modern_examples must be a list, got {type(parsed).__name__}")
                        return False
                    # Validate each item is a dict with required fields
                    validated_examples = []
                    for i, item in enumerate(parsed):
                        if isinstance(item, dict):
                            # Ensure it has required fields
                            if 'category' in item and 'description' in item:
                                # Ensure values are strings, not nested structures
                                validated_item = {
                                    'category': str(item['category']) if item['category'] else '',
                                    'description': str(item['description']) if item['description'] else ''
                                }
                                validated_examples.append(validated_item)
                            else:
                                logger.warning(f"modern_examples[{i}] missing 'category' or 'description', skipping")
                        elif isinstance(item, list):
                            logger.error(f"modern_examples[{i}] is a list, expected dict. Skipping...")
                            continue
                        else:
                            logger.warning(f"modern_examples[{i}] is {type(item).__name__}, expected dict. Skipping...")
                            continue
                    parsed = validated_examples
                
                # CRITICAL: Validate that data is JSON-serializable before setting
                try:
                    json.dumps(parsed)  # Test serialization
                except (TypeError, ValueError) as e:
                    logger.error(f"Validated {section_name} is not JSON-serializable: {e}")
                    return False
                
                # Set the attribute with error handling
                try:
                    setattr(explanation, section_name, parsed)
                    return True
                except Exception as e:
                    logger.error(f"Error setting {section_name} attribute: {e}", exc_info=True)
                    return False
            else:
                # For text fields, use content directly
                setattr(explanation, section_name, improved_content.strip())
                return True
                
        except Exception as e:
            logger.error(f"Error updating section {section_name}: {str(e)}", exc_info=True)
            return False
    
    def _save_explanation_state(self, explanation: ShlokaExplanation) -> Dict:
        """
        Save the current state of an explanation for potential rollback.
        
        Args:
            explanation: ShlokaExplanation instance
            
        Returns:
            Dictionary containing all section values
        """
        return {
            'summary': explanation.summary,
            'detailed_meaning': explanation.detailed_meaning,
            'detailed_explanation': explanation.detailed_explanation,
            'context': explanation.context,
            'why_this_matters': explanation.why_this_matters,
            'modern_examples': copy.deepcopy(explanation.modern_examples) if explanation.modern_examples else [],
            'themes': copy.deepcopy(explanation.themes) if explanation.themes else [],
            'reflection_prompt': explanation.reflection_prompt,
        }
    
    def _restore_explanation_state(self, explanation: ShlokaExplanation, state: Dict) -> None:
        """
        Restore an explanation to a previously saved state.
        
        Args:
            explanation: ShlokaExplanation instance to restore
            state: Dictionary containing saved state from _save_explanation_state
        """
        for field_name, field_value in state.items():
            setattr(explanation, field_name, field_value)
    
    def _check_and_fill_shloka_data(self, shloka: Shloka) -> List[str]:
        """
        Check Shloka for missing data and fill it if needed.
        
        Checks for:
        - Missing transliteration
        - Missing word_by_word breakdown
        
        Args:
            shloka: Shloka instance to check and fill
            
        Returns:
            List of field names that were filled
        """
        fixes_made = []
        
        # Check if transliteration is missing
        if not shloka.transliteration or not shloka.transliteration.strip():
            logger.info(f"Shloka {shloka.id} missing transliteration - generating...")
            transliteration = self._generate_transliteration(shloka)
            if transliteration:
                shloka.transliteration = transliteration
                shloka.save(update_fields=['transliteration', 'updated_at'])
                fixes_made.append('transliteration')
                logger.info(f"✓ Generated transliteration for shloka {shloka.id}")
        
        # Check if word_by_word is missing
        if not shloka.word_by_word or not isinstance(shloka.word_by_word, list) or len(shloka.word_by_word) == 0:
            logger.info(f"Shloka {shloka.id} missing word_by_word - generating...")
            word_by_word = self._generate_word_by_word(shloka)
            if word_by_word:
                shloka.word_by_word = word_by_word
                shloka.save(update_fields=['word_by_word', 'updated_at'])
                fixes_made.append('word_by_word')
                logger.info(f"✓ Generated word_by_word for shloka {shloka.id}")
        
        return fixes_made
    
    def _generate_transliteration(self, shloka: Shloka) -> Optional[str]:
        """
        Generate transliteration for a shloka using LLM.
        
        Args:
            shloka: Shloka instance
            
        Returns:
            Transliteration string or None if generation failed
        """
        try:
            prompt = f"""Provide the transliteration (Roman script) for this Sanskrit shloka.

Shloka: {shloka.book_name} - Chapter {shloka.chapter_number}, Verse {shloka.verse_number}
Sanskrit Text:
{shloka.sanskrit_text}

CRITICAL: Provide ONLY the transliteration in Roman script (IAST or ITRANS format).
Do not include any explanations, comments, or additional text.
Just the transliteration, one line per line of Sanskrit text.

Transliteration:"""

            response = self.groq_service.client.chat.completions.create(
                model=self.groq_service.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in Sanskrit transliteration. Provide accurate transliterations in Roman script (IAST format preferred)."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Very low temperature for accuracy
                max_tokens=500,
            )
            
            transliteration = response.choices[0].message.content.strip()
            # Clean up any extra text the LLM might have added
            lines = transliteration.split('\n')
            # Remove lines that are clearly not transliteration (like "Transliteration:" header)
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.lower().startswith('transliteration'):
                    cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines) if cleaned_lines else transliteration.strip()
            
        except Exception as e:
            logger.error(f"Error generating transliteration for shloka {shloka.id}: {str(e)}")
            return None
    
    def _generate_word_by_word(self, shloka: Shloka) -> Optional[List[Dict]]:
        """
        Generate word-by-word breakdown for a shloka using LLM.
        
        Args:
            shloka: Shloka instance
            
        Returns:
            List of word-by-word dictionaries or None if generation failed
        """
        try:
            transliteration_text = shloka.transliteration or ""
            
            # Build prompt parts to avoid backslash in f-string expression
            prompt_parts = [
                "Provide a word-by-word breakdown for this Sanskrit shloka.",
                "",
                f"Shloka: {shloka.book_name} - Chapter {shloka.chapter_number}, Verse {shloka.verse_number}",
                "Sanskrit Text:",
                shloka.sanskrit_text,
            ]
            
            # Add transliteration if available
            if transliteration_text:
                prompt_parts.extend([
                    "",
                    "Transliteration:",
                    transliteration_text,
                ])
            
            prompt_parts.extend([
                "",
                "CRITICAL: Provide a word-by-word breakdown in this EXACT format:",
                "- **sanskrit_word** (transliteration) – meaning",
                "- **sanskrit_word** (transliteration) – meaning",
                "...",
                "",
                "For each word, provide:",
                "1. Sanskrit word in Devanagari (in bold with **)",
                "2. Transliteration in parentheses (optional but preferred)",
                "3. Meaning after an en dash (–)",
                "",
                "Example format:",
                "- **धर्म** (dharma) – duty, righteousness",
                "- **क्षेत्रे** (kṣetre) – in the field",
                "",
                "Provide ONLY the word-by-word breakdown, nothing else.",
            ])
            
            prompt = "\n".join(prompt_parts)

            response = self.groq_service.client.chat.completions.create(
                model=self.groq_service.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert in Sanskrit grammar and word-by-word analysis.
Provide accurate word-by-word breakdowns with proper transliteration and meanings.
Maintain 100% accuracy to traditional interpretations."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Low temperature for accuracy
                max_tokens=2000,
            )
            
            word_by_word_text = response.choices[0].message.content.strip()
            
            # Parse the word-by-word breakdown using GroqService parser
            word_by_word = self.groq_service._parse_word_by_word(word_by_word_text)
            
            return word_by_word if word_by_word else None
            
        except Exception as e:
            logger.error(f"Error generating word_by_word for shloka {shloka.id}: {str(e)}")
            return None

