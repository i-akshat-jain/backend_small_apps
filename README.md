# Sanatan App Backend API

FastAPI backend for the Sanatan App - providing Hindu mythology knowledge through AI-powered shloka explanations.

## Setup

### 1. Install Dependencies

```bash
cd backend_apps
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the `backend_apps` directory with the following variables:

```bash
# Database Connection (PostgreSQL/Supabase)
user=postgres
password=your_password
host=db.your-project.supabase.co
port=5432
dbname=postgres

# Or use DATABASE_URL instead:
# DATABASE_URL=postgresql://user:password@host:port/dbname

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key

# Optional: API Configuration
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development

# CORS Configuration (for React Native frontend)
# Use "*" to allow all origins in development (default)
# For production, specify exact origins: "https://your-domain.com,https://app.your-domain.com"
CORS_ORIGINS=*
```

### 3. Database Setup

Run the migration script to create all required tables:

```bash
python migrate_tables.py
```

This will create the following tables:
- `shlokas` - Main shloka table
- `shloka_explanations` - AI-generated explanations
- `users` - User accounts
- `reading_logs` - User reading history

You can also test the database connection:

```bash
python test_connection.py
```

### 4. Run the Server

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
- `GET /` - Root endpoint
- `GET /health` - Health check

### Shlokas
- `GET /api/shlokas/random` - Get random shloka with explanation
- `GET /api/shlokas/{shloka_id}` - Get specific shloka by ID
- `GET /api/shlokas/{shloka_id}/summary` - Get summary explanation
- `GET /api/shlokas/{shloka_id}/detailed` - Get detailed explanation

## Adding Shlokas

You can add shlokas to the database using SQLAlchemy. Example script:

```python
from database import SessionLocal
from models import ShlokaORM
import uuid

db = SessionLocal()
try:
    shloka = ShlokaORM(
        id=uuid.uuid4(),
        book_name="Bhagavad Gita",
        chapter_number=2,
        verse_number=47,
        sanskrit_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन...",
        transliteration="karmaṇy-evādhikāras te mā phaleṣhu kadāchana..."
    )
    db.add(shloka)
    db.commit()
    print(f"Added shloka with ID: {shloka.id}")
finally:
    db.close()
```

Or use the provided script:

```bash
python scripts/add_sample_shloka.py
```

## Architecture

- **Hybrid Lazy Generation**: Explanations are generated on-demand and cached in the database
- **FastAPI**: Modern, fast web framework
- **PostgreSQL/Supabase**: Database using psycopg2 for synchronous connections
- **SQLAlchemy**: ORM for database operations
- **Groq AI**: Fast AI inference for generating explanations

## Database Migration

The project uses SQLAlchemy's `create_all()` for table creation. To migrate:

```bash
python migrate_tables.py
```

This script will:
- Check existing tables
- Create missing tables from models
- Show table structures
- Verify all tables exist

## Development

The server runs in development mode with auto-reload by default. Check `config.py` for configuration options.

## Connecting with React Native Frontend

The backend is configured to work with the React Native frontend. Key points:

- **CORS**: Configured to allow all origins in development mode (set `CORS_ORIGINS=*` in `.env`)
- **Health Check**: Use `GET /health` endpoint to test connectivity
- **API Endpoints**: All endpoints are prefixed with `/api/shlokas`

For detailed connection instructions, see the [Connection Guide](../CONNECTION_GUIDE.md) in the project root.

