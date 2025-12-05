"""
Quality checking service for Shloka explanations.

Evaluates explanation quality across multiple dimensions:
- Completeness: All required sections present
- Clarity: Readability and understandability
- Accuracy: Alignment with traditional interpretations
- Relevance: Modern application quality
- Structure: Proper formatting and organization
"""
from typing import Dict, Optional
from django.conf import settings
from django.utils import timezone
from apps.sanatan_app.models import ShlokaExplanation, Shloka
from apps.sanatan_app.groq_service import GroqService
import logging

logger = logging.getLogger(__name__)


class QualityCheckerService:
    """Service for checking and scoring explanation quality."""
    
    # Quality metric weights (must sum to 100)
    COMPLETENESS_WEIGHT = 25
    CLARITY_WEIGHT = 25
    ACCURACY_WEIGHT = 25
    RELEVANCE_WEIGHT = 15
    STRUCTURE_WEIGHT = 10
    
    # Required sections for completeness check
    REQUIRED_SECTIONS = [
        'summary',
        'detailed_meaning',
        'detailed_explanation',
        'context',
        'why_this_matters',
        'modern_examples',
        'themes',
    ]
    
    def __init__(self):
        self.groq_service = GroqService()
    
    def check_quality(self, explanation: ShlokaExplanation) -> Dict:
        """
        Check quality of an explanation and return detailed scores.
        
        Also checks Shloka completeness (transliteration, word_by_word).
        
        Args:
            explanation: ShlokaExplanation instance to check
            
        Returns:
            Dictionary with:
            - overall_score: Overall quality score (0-100)
            - completeness_score: Completeness score (0-25)
            - clarity_score: Clarity score (0-25)
            - accuracy_score: Accuracy score (0-25)
            - relevance_score: Relevance score (0-15)
            - structure_score: Structure score (0-10)
            - feedback: Detailed feedback for each metric
            - shloka_completeness: Information about Shloka data completeness
        """
        logger.info(f"Checking quality for explanation {explanation.id}")
        
        # Check Shloka completeness (transliteration, word_by_word)
        shloka_completeness = self._check_shloka_completeness(explanation.shloka)
        
        # Check completeness (rule-based)
        completeness_result = self._check_completeness(explanation)
        
        # Adjust completeness score based on Shloka data
        if not shloka_completeness['is_complete']:
            # Deduct points if Shloka data is missing
            missing_items = shloka_completeness['missing_items']
            deduction = min(5, len(missing_items) * 2.5)  # Max 5 points deduction
            completeness_result['score'] = max(0, completeness_result['score'] - deduction)
            completeness_result['feedback'] += f" | Missing Shloka data: {', '.join(missing_items)}"
        
        # Check structure (rule-based)
        structure_result = self._check_structure(explanation)
        
        # Check clarity, accuracy, relevance (LLM-based)
        llm_results = self._check_with_llm(explanation)
        
        # Combine scores
        overall_score = (
            completeness_result['score'] +
            structure_result['score'] +
            llm_results['clarity_score'] +
            llm_results['accuracy_score'] +
            llm_results['relevance_score']
        )
        
        result = {
            'overall_score': round(overall_score, 2),
            'completeness_score': completeness_result['score'],
            'clarity_score': llm_results['clarity_score'],
            'accuracy_score': llm_results['accuracy_score'],
            'relevance_score': llm_results['relevance_score'],
            'structure_score': structure_result['score'],
            'feedback': {
                'completeness': completeness_result['feedback'],
                'clarity': llm_results['clarity_feedback'],
                'accuracy': llm_results['accuracy_feedback'],
                'relevance': llm_results['relevance_feedback'],
                'structure': structure_result['feedback'],
            },
            'shloka_completeness': shloka_completeness
        }
        
        logger.info(f"Quality check complete for explanation {explanation.id}: {overall_score}/100")
        return result
    
    def _check_completeness(self, explanation: ShlokaExplanation) -> Dict:
        """
        Check if all required sections are present and non-empty.
        
        Returns:
            Dict with 'score' (0-25) and 'feedback'
        """
        missing_sections = []
        empty_sections = []
        
        for section in self.REQUIRED_SECTIONS:
            value = getattr(explanation, section, None)
            if value is None:
                missing_sections.append(section)
            elif isinstance(value, (list, dict)) and len(value) == 0:
                empty_sections.append(section)
            elif isinstance(value, str) and not value.strip():
                empty_sections.append(section)
        
        # Calculate score: 25 points, deduct for missing/empty sections
        total_sections = len(self.REQUIRED_SECTIONS)
        present_sections = total_sections - len(missing_sections) - len(empty_sections)
        score = (present_sections / total_sections) * self.COMPLETENESS_WEIGHT
        
        # Generate feedback
        feedback_parts = []
        if missing_sections:
            feedback_parts.append(f"Missing sections: {', '.join(missing_sections)}")
        if empty_sections:
            feedback_parts.append(f"Empty sections: {', '.join(empty_sections)}")
        if not missing_sections and not empty_sections:
            feedback_parts.append("All required sections are present and filled.")
        
        feedback = " | ".join(feedback_parts) if feedback_parts else "Complete"
        
        return {
            'score': round(score, 2),
            'feedback': feedback,
            'missing_sections': missing_sections,
            'empty_sections': empty_sections,
        }
    
    def _check_structure(self, explanation: ShlokaExplanation) -> Dict:
        """
        Check formatting and structure quality.
        
        Returns:
            Dict with 'score' (0-10) and 'feedback'
        """
        issues = []
        score = self.STRUCTURE_WEIGHT
        
        # Check if examples is a valid JSON array
        if explanation.modern_examples:
            if not isinstance(explanation.modern_examples, list):
                issues.append("modern_examples should be a list")
                score -= 2
            else:
                for example in explanation.modern_examples:
                    if not isinstance(example, dict):
                        issues.append("Each example should be a dict with 'category' and 'description'")
                        score -= 1
                        break
                    if 'category' not in example or 'description' not in example:
                        issues.append("Examples missing 'category' or 'description' fields")
                        score -= 1
                        break
        
        # Check if themes is a valid JSON array
        if explanation.themes:
            if not isinstance(explanation.themes, list):
                issues.append("themes should be a list")
                score -= 1
            elif not all(isinstance(theme, str) for theme in explanation.themes):
                issues.append("All themes should be strings")
                score -= 1
        
        # Check text length (basic sanity check)
        text_fields = ['summary', 'detailed_meaning', 'detailed_explanation', 'context', 'why_this_matters']
        for field in text_fields:
            value = getattr(explanation, field, None)
            if value and isinstance(value, str):
                if len(value.strip()) < 10:
                    issues.append(f"{field} is too short (less than 10 characters)")
                    score -= 0.5
                elif len(value.strip()) > 10000:
                    issues.append(f"{field} is too long (more than 10000 characters)")
                    score -= 0.5
        
        score = max(0, score)  # Ensure score doesn't go below 0
        
        feedback = "Structure is good." if not issues else " | ".join(issues)
        
        return {
            'score': round(score, 2),
            'feedback': feedback,
        }
    
    def _check_with_llm(self, explanation: ShlokaExplanation) -> Dict:
        """
        Use LLM to evaluate clarity, accuracy, and relevance.
        
        Returns:
            Dict with scores and feedback for clarity, accuracy, and relevance
        """
        try:
            shloka = explanation.shloka
            
            # Build evaluation prompt
            prompt = self._build_evaluation_prompt(explanation, shloka)
            
            # Call Groq API
            # CRITICAL: Use very low temperature (0.2) for consistent, accurate evaluation of religious content
            response = self.groq_service.client.chat.completions.create(
                model=self.groq_service.model,
                messages=[
                    {"role": "system", "content": self._get_evaluation_system_message()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Very low temperature for consistent, accurate evaluation
                max_tokens=1500,
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse LLM response
            return self._parse_llm_evaluation(response_text)
            
        except Exception as e:
            logger.error(f"Error in LLM quality check: {str(e)}")
            # Return default scores on error
            return {
                'clarity_score': self.CLARITY_WEIGHT * 0.5,  # Default to 50% of max
                'accuracy_score': self.ACCURACY_WEIGHT * 0.5,
                'relevance_score': self.RELEVANCE_WEIGHT * 0.5,
                'clarity_feedback': f"Evaluation error: {str(e)}",
                'accuracy_feedback': f"Evaluation error: {str(e)}",
                'relevance_feedback': f"Evaluation error: {str(e)}",
            }
    
    def _build_evaluation_prompt(self, explanation: ShlokaExplanation, shloka: Shloka) -> str:
        """Build prompt for LLM evaluation."""
        prompt_parts = [
            "Evaluate the quality of this shloka explanation:",
            "",
            f"Shloka: {shloka.book_name} - Chapter {shloka.chapter_number}, Verse {shloka.verse_number}",
            f"Sanskrit: {shloka.sanskrit_text}",
            "",
            "Explanation sections:",
            "",
        ]
        
        sections = {
            'Summary': explanation.summary,
            'Detailed Meaning': explanation.detailed_meaning,
            'Detailed Explanation': explanation.detailed_explanation,
            'Context': explanation.context,
            'Why This Matters': explanation.why_this_matters,
            'Modern Examples': explanation.modern_examples,
            'Themes': explanation.themes,
        }
        
        for section_name, section_value in sections.items():
            if section_value:
                if isinstance(section_value, list):
                    section_value = str(section_value)
                prompt_parts.append(f"{section_name}: {section_value}")
                prompt_parts.append("")
        
        prompt_parts.extend([
            "Please evaluate and provide scores (0-100) and brief feedback for:",
            "",
            "1. CLARITY (0-100): How clear, readable, and understandable is the explanation?",
            "",
            "2. ACCURACY (0-100): CRITICAL - How accurate and aligned with traditional interpretations?",
            "   - Deduct heavily for interpretations not supported by traditional sources",
            "   - Deduct for inaccuracies in meaning, context, or philosophical concepts",
            "   - Accuracy is more important than clarity or modern relevance",
            "",
            "3. RELEVANCE (0-100): How relevant and applicable to modern life?",
            "",
            "Respond in this exact format:",
            "CLARITY_SCORE: [0-100]",
            "CLARITY_FEEDBACK: [brief feedback]",
            "ACCURACY_SCORE: [0-100]",
            "ACCURACY_FEEDBACK: [brief feedback - be specific about any inaccuracies]",
            "RELEVANCE_SCORE: [0-100]",
            "RELEVANCE_FEEDBACK: [brief feedback]",
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_evaluation_system_message(self) -> str:
        """Get system message for LLM evaluation.
        
        CRITICAL: Emphasizes accuracy evaluation for religious content.
        """
        return """You are an expert evaluator of Hindu philosophical explanations and Sanskrit literature.

CRITICAL: You are evaluating religious content that is deeply meaningful to millions of people.
Accuracy is the most important criterion - explanations must be faithful to traditional interpretations.

Your task is to evaluate explanations for:
1. CLARITY (0-100): How clear, readable, and understandable is the explanation?
2. ACCURACY (0-100): How accurate and aligned with traditional interpretations? This is CRITICAL.
   - Deduct heavily for any interpretations not supported by traditional sources
   - Deduct for any inaccuracies in meaning, context, or philosophical concepts
   - Accuracy is more important than clarity or modern relevance
3. RELEVANCE (0-100): How relevant and applicable to modern life?

Be thorough and strict in your evaluation, especially regarding accuracy.
Provide specific, constructive feedback that identifies any issues."""
    
    def _parse_llm_evaluation(self, response_text: str) -> Dict:
        """Parse LLM evaluation response."""
        import re
        
        # Default values
        clarity_score = self.CLARITY_WEIGHT * 0.5
        accuracy_score = self.ACCURACY_WEIGHT * 0.5
        relevance_score = self.RELEVANCE_WEIGHT * 0.5
        clarity_feedback = "Could not parse evaluation"
        accuracy_feedback = "Could not parse evaluation"
        relevance_feedback = "Could not parse evaluation"
        
        try:
            # Extract clarity
            clarity_match = re.search(r'CLARITY_SCORE:\s*(\d+)', response_text, re.IGNORECASE)
            if clarity_match:
                raw_score = int(clarity_match.group(1))
                clarity_score = min(100, max(0, raw_score)) / 100 * self.CLARITY_WEIGHT
            
            clarity_feedback_match = re.search(r'CLARITY_FEEDBACK:\s*(.+?)(?=\n[A-Z_]|$)', response_text, re.IGNORECASE | re.DOTALL)
            if clarity_feedback_match:
                clarity_feedback = clarity_feedback_match.group(1).strip()
            
            # Extract accuracy
            accuracy_match = re.search(r'ACCURACY_SCORE:\s*(\d+)', response_text, re.IGNORECASE)
            if accuracy_match:
                raw_score = int(accuracy_match.group(1))
                accuracy_score = min(100, max(0, raw_score)) / 100 * self.ACCURACY_WEIGHT
            
            accuracy_feedback_match = re.search(r'ACCURACY_FEEDBACK:\s*(.+?)(?=\n[A-Z_]|$)', response_text, re.IGNORECASE | re.DOTALL)
            if accuracy_feedback_match:
                accuracy_feedback = accuracy_feedback_match.group(1).strip()
            
            # Extract relevance
            relevance_match = re.search(r'RELEVANCE_SCORE:\s*(\d+)', response_text, re.IGNORECASE)
            if relevance_match:
                raw_score = int(relevance_match.group(1))
                relevance_score = min(100, max(0, raw_score)) / 100 * self.RELEVANCE_WEIGHT
            
            relevance_feedback_match = re.search(r'RELEVANCE_FEEDBACK:\s*(.+?)(?=\n[A-Z_]|$)', response_text, re.IGNORECASE | re.DOTALL)
            if relevance_feedback_match:
                relevance_feedback = relevance_feedback_match.group(1).strip()
                
        except Exception as e:
            logger.warning(f"Error parsing LLM evaluation: {str(e)}")
        
        return {
            'clarity_score': round(clarity_score, 2),
            'accuracy_score': round(accuracy_score, 2),
            'relevance_score': round(relevance_score, 2),
            'clarity_feedback': clarity_feedback,
            'accuracy_feedback': accuracy_feedback,
            'relevance_feedback': relevance_feedback,
        }
    
    def _check_shloka_completeness(self, shloka: Shloka) -> Dict:
        """
        Check if Shloka has all desired data fields.
        
        Args:
            shloka: Shloka instance to check
            
        Returns:
            Dictionary with:
            - is_complete: Whether all desired fields are present
            - missing_items: List of missing field names
            - has_transliteration: Whether transliteration is present
            - has_word_by_word: Whether word_by_word is present
        """
        missing_items = []
        
        # Check transliteration
        has_transliteration = bool(shloka.transliteration and shloka.transliteration.strip())
        if not has_transliteration:
            missing_items.append('transliteration')
        
        # Check word_by_word
        has_word_by_word = bool(
            shloka.word_by_word and 
            isinstance(shloka.word_by_word, list) and 
            len(shloka.word_by_word) > 0
        )
        if not has_word_by_word:
            missing_items.append('word_by_word')
        
        return {
            'is_complete': len(missing_items) == 0,
            'missing_items': missing_items,
            'has_transliteration': has_transliteration,
            'has_word_by_word': has_word_by_word,
        }
    
    def update_explanation_quality(self, explanation: ShlokaExplanation) -> Dict:
        """
        Check quality and update the explanation record.
        
        Args:
            explanation: ShlokaExplanation instance to check and update
            
        Returns:
            Quality check result dictionary
        """
        result = self.check_quality(explanation)
        
        # Update explanation with quality scores
        explanation.quality_score = int(result['overall_score'])
        explanation.quality_checked_at = timezone.now()
        explanation.save(update_fields=['quality_score', 'quality_checked_at'])
        
        return result

