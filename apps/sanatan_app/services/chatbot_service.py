"""
Chatbot service for handling AI conversations about Sanatan Dharma.
"""
from groq import Groq
from django.conf import settings
from typing import List, Dict
from ..models import ChatConversation, ChatMessage, User, ReadingLog
import logging

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot conversations."""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = "openai/gpt-oss-20b"
    
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
        Generate a chatbot response using Groq AI.
        
        Args:
            user_message: The user's message
            conversation_history: List of previous messages in format [{"role": "user/assistant", "content": "..."}]
            user: The user object for context
            
        Returns:
            The assistant's response text
        """
        try:
            # Build system message with context
            context = self.get_conversation_context(user)
            system_message = """You are a knowledgeable and friendly AI assistant specializing in Sanatan Dharma (Hindu philosophy, scriptures, and spiritual wisdom). 

Your role is to:
- Answer questions about Hindu philosophy, scriptures (Bhagavad Gita, Upanishads, etc.), and spiritual practices
- Provide clear, accessible explanations that help modern readers understand ancient wisdom
- Be respectful, inclusive, and supportive in your responses
- When relevant, reference specific shlokas or texts if appropriate
- Encourage spiritual growth and understanding

Keep responses concise but informative. If you don't know something, admit it rather than making things up."""
            
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
                temperature=0.7,
                max_tokens=1000,
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

