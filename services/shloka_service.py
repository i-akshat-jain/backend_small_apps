"""Service for shloka operations using synchronous SQLAlchemy."""
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException
from services.groq_service import GroqService
from models import (
    ShlokaORM, ShlokaExplanationORM,  # ORM models
    Shloka, Explanation, ShlokaResponse, ReadingType  # Pydantic models
)
from typing import Optional
from uuid import UUID
import logging
import random

logger = logging.getLogger(__name__)


class ShlokaService:
    """Service for managing shlokas and their explanations."""
    
    def __init__(self):
        self.groq_service = GroqService()
    
    def get_random_shloka(self, db: Session) -> ShlokaResponse:
        """
        Get a random shloka with both summary and detailed explanations.
        
        Args:
            db: Database session
            
        Returns:
            ShlokaResponse object with summary and detailed explanations
        """
        try:
            # Get total count
            total_count = db.query(func.count(ShlokaORM.id)).scalar()
            
            if total_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No shlokas found in database. Please add shlokas using the script: python scripts/add_sample_shloka.py"
                )
            
            # Get random shloka using PostgreSQL RANDOM()
            shloka_orm = db.query(ShlokaORM).order_by(func.random()).limit(1).first()
            
            if shloka_orm is None:
                raise Exception("Failed to fetch random shloka")
            
            # Convert ORM to Pydantic
            shloka = Shloka.model_validate(shloka_orm)
            
            # Get or generate both summary and detailed explanations
            summary = self.get_explanation(db, shloka.id, ReadingType.SUMMARY)
            detailed = self.get_explanation(db, shloka.id, ReadingType.DETAILED)
            
            return ShlokaResponse(shloka=shloka, summary=summary, detailed=detailed)
            
        except Exception as e:
            logger.error(f"Error getting random shloka: {str(e)}")
            raise
    
    def _get_shloka_only(self, db: Session, shloka_id: UUID) -> Optional[Shloka]:
        """Get shloka by ID without explanations (internal helper)."""
        try:
            shloka_orm = db.query(ShlokaORM).filter(ShlokaORM.id == shloka_id).first()
            
            if shloka_orm is None:
                return None
            
            return Shloka.model_validate(shloka_orm)
        except Exception as e:
            logger.error(f"Error getting shloka by ID: {str(e)}")
            return None
    
    def get_shloka_by_id(self, db: Session, shloka_id: UUID) -> ShlokaResponse:
        """
        Get shloka by ID with both summary and detailed explanations.
        
        Args:
            db: Database session
            shloka_id: UUID of the shloka
            
        Returns:
            ShlokaResponse object with summary and detailed explanations
        """
        try:
            shloka = self._get_shloka_only(db, shloka_id)
            
            if shloka is None:
                raise Exception(f"Shloka with ID {shloka_id} not found")
            
            # Get or generate both summary and detailed explanations
            summary = self.get_explanation(db, shloka_id, ReadingType.SUMMARY)
            detailed = self.get_explanation(db, shloka_id, ReadingType.DETAILED)
            
            return ShlokaResponse(shloka=shloka, summary=summary, detailed=detailed)
        except Exception as e:
            logger.error(f"Error getting shloka by ID: {str(e)}")
            raise
    
    def get_explanation(
        self,
        db: Session,
        shloka_id: UUID,
        explanation_type: ReadingType = ReadingType.SUMMARY
    ) -> Optional[Explanation]:
        """
        Get explanation for a shloka, generating if it doesn't exist.
        
        Args:
            db: Database session
            shloka_id: UUID of the shloka
            explanation_type: Either ReadingType.SUMMARY or ReadingType.DETAILED
            
        Returns:
            Explanation object
        """
        # Try to get existing explanation
        explanation = self._get_explanation(db, shloka_id, explanation_type)
        
        if explanation is None:
            # Get shloka data (without explanations to avoid circular dependency)
            shloka = self._get_shloka_only(db, shloka_id)
            if shloka is None:
                raise Exception(f"Shloka with ID {shloka_id} not found")
            
            # Generate and store explanation
            explanation = self._generate_and_store_explanation(
                db, shloka, explanation_type
            )
        
        return explanation
    
    def _get_explanation(
        self,
        db: Session,
        shloka_id: UUID,
        explanation_type: ReadingType
    ) -> Optional[Explanation]:
        """Get existing explanation from database."""
        try:
            explanation_orm = db.query(ShlokaExplanationORM).filter(
                ShlokaExplanationORM.shloka_id == shloka_id,
                ShlokaExplanationORM.explanation_type == explanation_type.value
            ).first()
            
            if explanation_orm is None:
                return None
            
            return Explanation.model_validate(explanation_orm)
        except Exception as e:
            logger.error(f"Error getting explanation: {str(e)}")
            return None
    
    def _generate_and_store_explanation(
        self,
        db: Session,
        shloka: Shloka,
        explanation_type: ReadingType
    ) -> Explanation:
        """Generate explanation using Groq and store in database."""
        try:
            # Convert shloka to dict for Groq service
            shloka_dict = {
                "book_name": shloka.book_name,
                "chapter_number": shloka.chapter_number,
                "verse_number": shloka.verse_number,
                "sanskrit_text": shloka.sanskrit_text,
                "transliteration": shloka.transliteration,
            }
            
            # Generate explanation
            explanation_text, prompt = self.groq_service.generate_explanation(
                shloka_dict, explanation_type.value
            )
            
            # Create new explanation ORM object
            explanation_orm = ShlokaExplanationORM(
                shloka_id=shloka.id,
                explanation_type=explanation_type.value,
                explanation_text=explanation_text,
                ai_model_used=self.groq_service.model,
                generation_prompt=prompt,
            )
            
            # Add to session and commit
            db.add(explanation_orm)
            db.flush()  # Flush to get the ID
            db.refresh(explanation_orm)  # Refresh to get all fields including timestamps
            
            # Convert to Pydantic model
            return Explanation.model_validate(explanation_orm)
            
        except Exception as e:
            logger.error(f"Error generating and storing explanation: {str(e)}")
            raise
