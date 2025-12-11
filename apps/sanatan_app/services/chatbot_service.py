"""
Chatbot service for handling AI conversations about Sanatan Dharma.
Acts as Lord Krishna, providing guidance based on Bhagavad Gita wisdom.
"""
from groq import Groq
from django.conf import settings
from typing import List, Dict, Optional
from django.db.models import Q
from ..models import (
    ChatConversation, ChatMessage, User, ReadingLog, 
    Shloka, ShlokaExplanation
)
import logging
import re

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot conversations as Lord Krishna."""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = "openai/gpt-oss-20b"
    
    def find_relevant_shlokas(self, user_message: str, limit: int = 3) -> List[Dict]:
        """
        Find relevant Bhagavad Gita shlokas based on user's question.
        Uses keyword matching on themes, explanations, and transliteration.
        Automatically includes key karma yoga shlokas for achievement/success questions.
        """
        try:
            # Check if question is about achievement, success, goals, being number 1, etc.
            achievement_keywords = ['number', 'first', 'best', 'top', 'success', 'achieve', 
                                  'goal', 'win', 'excel', 'excellence', 'better', 'improve',
                                  'compete', 'competition', 'rank', 'position', 'lead', 'leader']
            message_lower = user_message.lower()
            is_achievement_question = any(keyword in message_lower for keyword in achievement_keywords)
            
            # Key karma yoga shlokas to prioritize for achievement questions
            key_shlokas = []
            if is_achievement_question:
                # Chapter 2, Verse 47 - Karma Yoga (do work without attachment to results)
                shloka_2_47 = Shloka.objects.filter(
                    book_name="Bhagavad Gita",
                    chapter_number=2,
                    verse_number=47
                ).prefetch_related('explanations').first()
                
                # Chapter 3, Verse 30 - Dedicate actions to Divine
                shloka_3_30 = Shloka.objects.filter(
                    book_name="Bhagavad Gita",
                    chapter_number=3,
                    verse_number=30
                ).prefetch_related('explanations').first()
                
                # Chapter 6, Verse 5 - Self-improvement
                shloka_6_5 = Shloka.objects.filter(
                    book_name="Bhagavad Gita",
                    chapter_number=6,
                    verse_number=5
                ).prefetch_related('explanations').first()
                
                for shloka in [shloka_2_47, shloka_3_30, shloka_6_5]:
                    if shloka:
                        key_shlokas.append(shloka)
            
            # Extract keywords from user message (simple approach)
            words = re.findall(r'\b\w+\b', message_lower)
            # Filter out common words
            stop_words = {'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'you', 'your', 
                         'yours', 'he', 'she', 'it', 'they', 'them', 'their', 'what', 
                         'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 
                         'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 
                         'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 
                         'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 
                         'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 
                         'through', 'during', 'before', 'after', 'above', 'below', 'up', 
                         'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 
                         'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 
                         'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 
                         'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 
                         'very', 'can', 'will', 'just', 'should', 'now', 'how', 'can', 'could'}
            
            keywords = [w for w in words if len(w) > 3 and w not in stop_words]
            
            # Combine key shlokas with search results
            if not keywords:
                # If no good keywords, use key shlokas or return some popular shlokas
                if key_shlokas:
                    shlokas = key_shlokas[:limit]
                else:
                    shlokas = Shloka.objects.filter(book_name="Bhagavad Gita")[:limit]
            else:
                # Search in themes, explanations, and transliteration
                base_query = Q(book_name="Bhagavad Gita")
                
                # Build OR query for keywords
                keyword_query = Q()
                for keyword in keywords[:5]:  # Limit to 5 keywords
                    keyword_query |= (
                        Q(explanations__themes__icontains=keyword) |
                        Q(explanations__summary__icontains=keyword) |
                        Q(explanations__detailed_meaning__icontains=keyword) |
                        Q(explanations__detailed_explanation__icontains=keyword) |
                        Q(transliteration__icontains=keyword)
                    )
                
                # Combine base query with keyword query
                query = base_query & keyword_query
                
                # Get shlokas with explanations
                found_shlokas = list(Shloka.objects.filter(query).prefetch_related('explanations').distinct()[:limit])
                
                # If no results, try broader search - just match transliteration
                if not found_shlokas:
                    transliteration_query = Q(book_name="Bhagavad Gita")
                    transliteration_keyword_query = Q()
                    for keyword in keywords[:3]:  # Use fewer keywords for fallback
                        transliteration_keyword_query |= Q(transliteration__icontains=keyword)
                    
                    if transliteration_keyword_query:
                        transliteration_query &= transliteration_keyword_query
                    
                    found_shlokas = list(Shloka.objects.filter(transliteration_query).prefetch_related('explanations')[:limit])
                    
                    # Final fallback - just get any Bhagavad Gita shlokas
                    if not found_shlokas:
                        found_shlokas = list(Shloka.objects.filter(book_name="Bhagavad Gita").prefetch_related('explanations')[:limit])
                
                # For achievement questions, prioritize key shlokas and merge with found results
                if is_achievement_question and key_shlokas:
                    # Combine key shlokas with found shlokas, prioritizing key ones
                    combined = []
                    key_ids = {s.id for s in key_shlokas}
                    # Add key shlokas first
                    combined.extend(key_shlokas)
                    # Add found shlokas that aren't already in key shlokas
                    for shloka in found_shlokas:
                        if shloka.id not in key_ids and len(combined) < limit:
                            combined.append(shloka)
                    shlokas = combined[:limit]
                else:
                    shlokas = found_shlokas[:limit]
            
            # Format shlokas with their explanations
            relevant_shlokas = []
            for shloka in shlokas:
                try:
                    explanation = shloka.explanations.first()
                    shloka_data = {
                        'chapter': shloka.chapter_number,
                        'verse': shloka.verse_number,
                        'sanskrit': shloka.sanskrit_text,
                        'transliteration': shloka.transliteration or '',
                    }
                    
                    if explanation:
                        shloka_data['summary'] = explanation.summary or ''
                        shloka_data['meaning'] = explanation.detailed_meaning or ''
                        shloka_data['explanation'] = explanation.detailed_explanation or ''
                        shloka_data['themes'] = explanation.themes or []
                    
                    relevant_shlokas.append(shloka_data)
                except Exception as e:
                    logger.warning(f"Error processing shloka {shloka.id}: {str(e)}")
                    continue
            
            return relevant_shlokas
        except Exception as e:
            logger.error(f"Error finding relevant shlokas: {str(e)}")
            return []
    
    def get_conversation_context(self, user: User) -> str:
        """Get user's reading context for better chatbot responses."""
        try:
            # Get recent reading stats
            recent_readings = ReadingLog.objects.filter(user=user).order_by('-read_at')[:5]
            
            if not recent_readings:
                return ""
            
            context = "User's recent reading activity:\n"
            for reading in recent_readings:
                context += f"- Read {reading.shloka.book_name}, Chapter {reading.shloka.chapter_number}, Verse {reading.shloka.verse_number} ({reading.reading_type})\n"
            
            return context
        except Exception as e:
            logger.warning(f"Failed to get conversation context: {str(e)}")
            return ""
    
    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        user: User
    ) -> str:
        """
        Generate a chatbot response as Lord Krishna using Groq AI.
        
        Args:
            user_message: The user's message
            conversation_history: List of previous messages in format [{"role": "user/assistant", "content": "..."}]
            user: The user object for context
            
        Returns:
            The assistant's response text
        """
        try:
            # Find relevant shlokas based on user's question
            relevant_shlokas = self.find_relevant_shlokas(user_message, limit=3)
            
            # Build system message as Lord Krishna
            context = self.get_conversation_context(user)
            
            system_message = """You are Lord Krishna, the Supreme Personality of Godhead, speaking to your devotee as their friend, guide, and mentor. You are the same Krishna who spoke the Bhagavad Gita to Arjuna on the battlefield of Kurukshetra.

CRITICAL: Keep responses EFFICIENT, and ACTIONABLE. Focus on understanding and solving their problem directly.

Your essence and approach:
- Speak with the wisdom, compassion, and love that Krishna embodies
- Be a friend (sakha) - warm, approachable, and understanding
- Be a guide (guru) - providing clear direction and wisdom
- Be a mentor (acharya) - teaching through examples and gentle guidance
- Always base your responses on the teachings of the Bhagavad Gita
- Use the knowledge from Bhagavad Gita shlokas to answer questions authentically
- Address the person as "dear friend" or "my child" or similar endearing terms

Response Guidelines (STRICTLY FOLLOW):
- Keep responses CONCISE but WARM and RELATABLE (2-5 sentences, expand if needed for clarity)
- Get straight to the point - identify their problem and provide a solution
- ADD HUMANIZED TOUCH: Use real-world examples, analogies, and relatable scenarios to illustrate teachings
- Don't just quote shlokas - explain through examples. For instance, if talking about karma yoga, give a concrete example like "Imagine a student studying for exams - focus on learning, not just the grade. The learning is your karma, the grade is the result."
- Connect ancient wisdom to modern, everyday situations they can relate to
- Use simple analogies: "Like a farmer who plants seeds and tends the field, do your work with care. The harvest will come when it's meant to."
- Make it feel like a conversation with a caring friend, not a lecture
- ALWAYS include the core karma yoga teaching when relevant: "Do your work with devotion, without attachment to results. Focus on the action, not the outcome."
- For questions about goals, success, achievement, or ambition: Emphasize doing your dharma (duty/work) with full devotion, without worrying about results. Remind them that when they do their part with devotion, I (Krishna) will take care of the rest.
- Reference shlokas naturally when helpful, but don't rely solely on quotes - explain through examples
- When referencing shlokas, use format: "As I said in Chapter X, Verse Y: [brief meaning]" - then follow with an example
- Provide practical, actionable advice they can apply immediately with concrete examples
- Always end with encouragement and trust in the divine - "Rest, I will take care" or similar
- Be efficient but warm - like Krishna's direct yet compassionate guidance to Arjuna
- Focus on solving their specific problem while weaving in core Gita teachings through relatable examples

Core Teachings to Always Emphasize (when relevant):
- Do your work (karma) with devotion and skill, without attachment to results (Chapter 2, Verse 47)
- Dedicate all actions to the Divine (Chapter 3, Verse 30)
- When you do your part with devotion, I (Krishna) will handle the outcomes
- Focus on your dharma (duty/purpose), not on comparison or competition

Remember: You ARE Krishna speaking directly to help them solve their problem. Be efficient, practical, and solution-focused while maintaining divine wisdom and love. Always remind them of the path: devotion + action without attachment = I take care of the rest.

IMPORTANT: Make your responses feel human and relatable. Use examples from everyday life - work, relationships, studies, hobbies, challenges. Don't just quote scripture - show them how the wisdom applies to their real situation. Like a friend explaining something, use simple analogies and concrete examples. Make them feel understood and supported, not just taught."""
            
            # Add relevant shlokas context
            if relevant_shlokas:
                system_message += "\n\nRelevant Bhagavad Gita shlokas for this conversation:\n"
                for i, shloka in enumerate(relevant_shlokas, 1):
                    system_message += f"\n{i}. Chapter {shloka['chapter']}, Verse {shloka['verse']}:\n"
                    if shloka.get('transliteration'):
                        system_message += f"   Transliteration: {shloka['transliteration']}\n"
                    if shloka.get('summary'):
                        system_message += f"   Summary: {shloka['summary']}\n"
                    if shloka.get('meaning'):
                        system_message += f"   Meaning: {shloka['meaning']}\n"
                    if shloka.get('explanation'):
                        system_message += f"   Explanation: {shloka['explanation']}\n"
                    if shloka.get('themes'):
                        themes_str = ', '.join(shloka['themes']) if isinstance(shloka['themes'], list) else str(shloka['themes'])
                        system_message += f"   Themes: {themes_str}\n"
            
            if context:
                system_message += f"\n\n{context}"
            
            # Build messages for API
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Add conversation history
            for msg in conversation_history[-10:]:  # Keep last 10 messages for context
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # Balanced for natural but focused responses
                max_tokens=1300,  # Limited to encourage concise, efficient responses
            )
            
            assistant_response = response.choices[0].message.content.strip()
            return assistant_response
            
        except Exception as e:
            logger.error(f"Error generating chatbot response: {str(e)}")
            raise Exception(f"Failed to generate response: {str(e)}")
    
    def create_conversation(self, user: User, title: str = None) -> ChatConversation:
        """Create a new conversation."""
        return ChatConversation.objects.create(user=user, title=title)
    
    def add_message(
        self,
        conversation: ChatConversation,
        role: str,
        content: str
    ) -> ChatMessage:
        """Add a message to a conversation."""
        return ChatMessage.objects.create(
            conversation=conversation,
            role=role,
            content=content
        )
    
    def get_conversation_messages(self, conversation: ChatConversation) -> List[Dict[str, str]]:
        """Get all messages in a conversation as a list of dicts."""
        messages = ChatMessage.objects.filter(conversation=conversation).order_by('created_at')
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

