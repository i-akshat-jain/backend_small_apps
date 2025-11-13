"""Configuration settings for the application."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Explicitly load .env file to ensure environment variables are available
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration (PostgreSQL/Supabase)
    # Option 1: Use DATABASE_URL (full connection string)
    # Format: postgresql://user:password@host:port/database
    # For Supabase: Use the direct connection (port 5432) or connection pooling URL (port 6543)
    database_url: Optional[str] = Field(None, validation_alias="DATABASE_URL")
    
    # Option 2: Use individual database connection parameters
    # These are used if DATABASE_URL is not provided
    # Supports both DB_* prefixed and lowercase versions (user, password, host, port, dbname)
    db_user: Optional[str] = Field(None, validation_alias="DB_USER")
    db_password: Optional[str] = Field(None, validation_alias="DB_PASSWORD")
    db_host: Optional[str] = Field(None, validation_alias="DB_HOST")
    db_port: Optional[str] = Field(None, validation_alias="DB_PORT")
    db_name: Optional[str] = Field(None, validation_alias="DB_NAME")
    
    # Legacy support: also check for lowercase versions (as in user's example)
    user: Optional[str] = Field(None, validation_alias="user")
    password: Optional[str] = Field(None, validation_alias="password")
    host: Optional[str] = Field(None, validation_alias="host")
    port: Optional[str] = Field(None, validation_alias="port")
    dbname: Optional[str] = Field(None, validation_alias="dbname")
    
    # Groq API Configuration
    # Explicitly reads from GROQ_API_KEY environment variable in .env file
    groq_api_key: str = Field(..., validation_alias="GROQ_API_KEY")
    
    # FastAPI Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    environment: str = "development"
    
    # CORS Configuration
    # For React Native: In development, allow all origins for easier testing
    # In production, specify exact origins
    cors_origins: str = "*"  # Default to allow all in development
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        # If "*" is specified, return ["*"] to allow all origins (development only)
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @property
    def database_url_computed(self) -> str:
        """
        Get database URL, either from DATABASE_URL or constructed from individual components.
        Prioritizes DATABASE_URL if provided, otherwise constructs from individual parameters.
        """
        # If DATABASE_URL is provided, use it
        if self.database_url:
            return self.database_url
        
        # Otherwise, construct from individual components
        # Try DB_* prefixed variables first, then fallback to lowercase versions
        user = self.db_user or self.user
        password = self.db_password or self.password
        host = self.db_host or self.host
        port = self.db_port or self.port or "5432"
        dbname = self.db_name or self.dbname
        
        if not all([user, password, host, dbname]):
            raise ValueError(
                "Either DATABASE_URL must be provided, or all of the following must be set: "
                "DB_USER/user, DB_PASSWORD/password, DB_HOST/host, DB_NAME/dbname"
            )
        
        # URL encode password to handle special characters
        password_encoded = quote_plus(password)
        
        # Construct the connection URL
        return f"postgresql://{user}:{password_encoded}@{host}:{port}/{dbname}"
    
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env that aren't in the model


settings = Settings()

