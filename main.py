"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import shlokas
from config import settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sanatan App API",
    description="Backend API for Sanatan App - Hindu Mythology Knowledge",
    version="1.0.0"
)

# Configure CORS
# Note: When allow_origins=["*"], allow_credentials must be False
# For React Native, we typically don't need credentials, so this is fine
cors_origins = settings.cors_origins_list
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(shlokas.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sanatan App API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development"
    )

