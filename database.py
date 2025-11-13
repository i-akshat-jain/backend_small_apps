"""Database connection and setup for synchronous SQLAlchemy with PostgreSQL/Supabase using psycopg2."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from config import settings
from typing import Generator
import logging

logger = logging.getLogger(__name__)

# Get database connection parameters from config
USER = settings.user or settings.db_user
PASSWORD = settings.password or settings.db_password
HOST = settings.host or settings.db_host
PORT = settings.port or settings.db_port or "5432"
DBNAME = settings.dbname or settings.db_name

# Configure SSL for Supabase connections
connect_args = {}
if "supabase.co" in (HOST or "") or "supabase.com" in (HOST or ""):
    import ssl
    # Create SSL context that doesn't verify hostname (required for some Supabase setups)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args = {
        "sslmode": "require",
        "sslcert": None,
        "sslkey": None,
        "sslrootcert": None,
    }

# Create synchronous engine using psycopg2
# Use the explicit connection format similar to psycopg2.connect()
engine = create_engine(
    settings.database_url_computed,
    echo=settings.environment == "development",  # Log SQL queries in development
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Number of connections to maintain
    max_overflow=10,  # Maximum number of connections beyond pool_size
    connect_args=connect_args,
)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base class for ORM models (already defined in models.py, but keeping for reference)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency to get database session.
    
    Usage in routes:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database (create tables if they don't exist)."""
    # Import all models to ensure they're registered with Base
    from models import (
        Base,
        ShlokaORM,
        ShlokaExplanationORM,
        UserORM,
        ReadingLogORM
    )
    # Create all tables defined in models
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized - tables created if they didn't exist")


def close_db():
    """Close database connections."""
    engine.dispose()
    logger.info("Database connections closed")
