"""Groq AI service for generating shloka explanations."""
from groq import Groq
from config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GroqService:
    """Service for interacting with Groq API."""
    
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = "openai/gpt-oss-20b"  # Updated to use active model
    
    def generate_explanation(
        self,
        shloka: dict,
        explanation_type: str = "summary"
    ) -> tuple[str, str]:
        """
        Generate explanation for a shloka.
        
        Args:
            shloka: Dictionary containing shloka data
            explanation_type: Either 'summary' or 'detailed'
            
        Returns:
            Tuple of (explanation_text, generation_prompt)
        """
        try:
            prompt = self._build_prompt(shloka, explanation_type)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in Hindu philosophy, Sanskrit literature, and the Bhagavad Gita. Provide clear, accessible explanations that help modern readers understand the deep wisdom of these ancient texts."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000 if explanation_type == "summary" else 2000,
            )
            
            explanation_text = response.choices[0].message.content.strip()
            return explanation_text, prompt
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            raise Exception(f"Failed to generate explanation: {str(e)}")
    
    def _build_prompt(self, shloka: dict, explanation_type: str) -> str:
        """Build the prompt for Groq API."""
        word_limit = "150-200 words" if explanation_type == "summary" else "400-500 words"
        
        prompt = f"""Explain this shloka from {shloka.get('book_name', 'Bhagavad Gita')}, Chapter {shloka.get('chapter_number')}, Verse {shloka.get('verse_number')}:

Sanskrit Text:
{shloka.get('sanskrit_text', '')}

{f"Transliteration: {shloka.get('transliteration', '')}" if shloka.get('transliteration') else ""}

Provide a {explanation_type} explanation ({word_limit}) in modern, accessible language. Include:
1. Core meaning and philosophical significance
2. Practical application in daily life
3. Context within the broader text

Make it engaging and relevant for contemporary readers while respecting the traditional wisdom."""
        
        return prompt

