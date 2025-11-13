"""SQLAlchemy ORM models for database tables."""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, CheckConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel as PydanticBaseModel
from uuid import UUID as PyUUID
import uuid

Base = declarative_base()


class TimestampedMixin:
    """Mixin for models with timestamp fields."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)


class ShlokaORM(Base, TimestampedMixin):
    """Shloka table model (SQLAlchemy ORM)."""
    __tablename__ = "shlokas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    book_name = Column(Text, nullable=False)
    chapter_number = Column(Integer, nullable=False)
    verse_number = Column(Integer, nullable=False)
    sanskrit_text = Column(Text, nullable=False)
    transliteration = Column(Text, nullable=True)
    
    # Relationships
    explanations = relationship("ShlokaExplanationORM", back_populates="shloka", cascade="all, delete-orphan")
    reading_logs = relationship("ReadingLogORM", back_populates="shloka", cascade="all, delete-orphan")


class ShlokaExplanationORM(Base, TimestampedMixin):
    """Shloka explanation table model (SQLAlchemy ORM)."""
    __tablename__ = "shloka_explanations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    shloka_id = Column(UUID(as_uuid=True), ForeignKey("shlokas.id", ondelete="CASCADE"), nullable=False)
    explanation_type = Column(String(20), nullable=False)  # 'summary' or 'detailed'
    explanation_text = Column(Text, nullable=False)
    ai_model_used = Column(Text, nullable=True)
    generation_prompt = Column(Text, nullable=True)
    
    # Relationships
    shloka = relationship("ShlokaORM", back_populates="explanations")
    
    __table_args__ = (
        CheckConstraint("explanation_type IN ('summary', 'detailed')", name="check_explanation_type"),
        {'extend_existing': True}
    )


class UserORM(Base, TimestampedMixin):
    """User table model (SQLAlchemy ORM)."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True, index=True)
    password = Column(Text, nullable=False)  # Should be hashed
    
    # Relationships
    reading_logs = relationship("ReadingLogORM", back_populates="user", cascade="all, delete-orphan")


class ReadingLogORM(Base):
    """Reading log table model (SQLAlchemy ORM)."""
    __tablename__ = "reading_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shloka_id = Column(UUID(as_uuid=True), ForeignKey("shlokas.id", ondelete="CASCADE"), nullable=False)
    reading_type = Column(String(20), nullable=False)  # 'summary' or 'detailed'
    read_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("UserORM", back_populates="reading_logs")
    shloka = relationship("ShlokaORM", back_populates="reading_logs")
    
    __table_args__ = (
        CheckConstraint("reading_type IN ('summary', 'detailed')", name="check_reading_type"),
    )


# Pydantic models for API responses
class ReadingType(str, Enum):
    """Reading type enum."""
    SUMMARY = "summary"
    DETAILED = "detailed"


class Shloka(PydanticBaseModel):
    """Pydantic model for Shloka response."""
    id: PyUUID
    book_name: str
    chapter_number: int
    verse_number: int
    sanskrit_text: str
    transliteration: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class Explanation(PydanticBaseModel):
    """Pydantic model for Shloka explanation response."""
    id: PyUUID
    shloka_id: PyUUID
    explanation_type: str
    explanation_text: str
    ai_model_used: Optional[str] = None
    generation_prompt: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ShlokaResponse(PydanticBaseModel):
    """Pydantic model for complete Shloka response with explanations."""
    shloka: Shloka
    summary: Optional[Explanation] = None
    detailed: Optional[Explanation] = None
    
    class Config:
        from_attributes = True
