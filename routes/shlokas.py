"""API routes for shlokas."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from services.shloka_service import ShlokaService
from models import ShlokaResponse
from database import get_db
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shlokas", tags=["shlokas"])
shloka_service = ShlokaService()


@router.get("/random", response_model=ShlokaResponse)
def get_random_shloka(db: Session = Depends(get_db)):
    """
    Get a random shloka with both summary and detailed explanations.
    
    If explanations don't exist, they will be generated on-demand.
    """
    try:
        return shloka_service.get_random_shloka(db)
    except Exception as e:
        logger.error(f"Error in get_random_shloka: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{shloka_id}", response_model=ShlokaResponse)
def get_shloka_by_id(shloka_id: UUID, db: Session = Depends(get_db)):
    """
    Get a specific shloka by ID with both summary and detailed explanations.
    
    If explanations don't exist, they will be generated on-demand.
    """
    try:
        return shloka_service.get_shloka_by_id(db, shloka_id)
    except Exception as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        logger.error(f"Error in get_shloka_by_id: {error_message}")
        raise HTTPException(status_code=500, detail=error_message)

