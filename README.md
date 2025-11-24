# Sanatan App Backend API

Django REST Framework backend for the Sanatan App - providing Hindu mythology knowledge through AI-powered shloka explanations.

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
# Option 1: Use individual parameters
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=db.your-project.supabase.co
DB_PORT=5432
DB_NAME=postgres

# Option 2: Use DATABASE_URL (full connection string)
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

Run migrations to create all required tables:

```bash
python manage.py makemigrations
python manage.py migrate
```

This will create the following tables:
- `shlokas` - Main shloka table
- `shloka_explanations` - AI-generated explanations
- `users` - User accounts
- `reading_logs` - User reading history

### 4. Add Sample Data (Optional)

Add sample shlokas to the database:

```bash
python manage.py add_sample_shlokas
```

### 5. Create Superuser (Optional)

Create an admin user to access the Django admin panel:

```bash
python manage.py createsuperuser
```

### 6. Run the Server

```bash
python manage.py runserver
```

Or specify host and port:

```bash
python manage.py runserver 0.0.0.0:8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Quick Reference

- `GET /` - Root endpoint (API info)
- `GET /health` - Health check
- `GET /api/shlokas/random` - Get random shloka with explanations
- `GET /api/shlokas/{shloka_id}` - Get specific shloka by ID

For detailed API documentation with request/response examples, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

## Project Structure

```
backend_apps/
├── apps/
│   └── sanatan_app/          # Main Django app
│       ├── models.py         # Database models
│       ├── views.py          # API views
│       ├── serializers.py    # DRF serializers
│       ├── services.py       # Business logic
│       ├── groq_service.py   # AI service integration
│       ├── urls.py           # URL routing
│       ├── admin.py          # Django admin configuration
│       └── management/
│           └── commands/     # Custom management commands
├── core/                     # Django project settings
│   ├── settings.py          # Django settings
│   ├── urls.py              # Root URL configuration
│   └── wsgi.py              # WSGI configuration
├── manage.py                # Django management script
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (create this)
```

## Architecture

- **Django REST Framework**: Modern, powerful web framework for building APIs
- **PostgreSQL/Supabase**: Database using psycopg2
- **Django ORM**: Object-relational mapping for database operations
- **Groq AI**: Fast AI inference for generating explanations
- **Hybrid Lazy Generation**: Explanations are generated on-demand and cached in the database

## Database Migration

Django uses migrations to manage database schema changes:

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# View migration status
python manage.py showmigrations
```

## Development

### Running in Development Mode

The server runs in development mode by default with auto-reload enabled:

```bash
python manage.py runserver
```

### Django Admin Panel

Access the admin panel at `http://localhost:8000/admin/` after creating a superuser:

```bash
python manage.py createsuperuser
```

### Adding Shlokas

You can add shlokas through:

1. **Management Command** (Recommended):
   ```bash
   python manage.py add_sample_shlokas
   ```

2. **Django Admin Panel**: Navigate to `http://localhost:8000/admin/` and add shlokas manually

3. **Django Shell**:
   ```bash
   python manage.py shell
   ```
   ```python
   from apps.sanatan_app.models import Shloka
   shloka = Shloka.objects.create(
       book_name="Bhagavad Gita",
       chapter_number=2,
       verse_number=47,
       sanskrit_text="कर्मण्येवाधिकारस्ते...",
       transliteration="karmaṇy-evādhikāras te..."
   )
   ```

## Connecting with React Native Frontend

The backend is configured to work with the React Native frontend. Key points:

- **CORS**: Configured to allow all origins in development mode (set `CORS_ORIGINS=*` in `.env`)
- **Health Check**: Use `GET /health` endpoint to test connectivity
- **API Endpoints**: All endpoints are prefixed with `/api/shlokas`
- **Error Handling**: All errors return JSON with a `detail` field

### Example Frontend Integration

```typescript
// Get random shloka
const response = await fetch('http://localhost:8000/api/shlokas/random');
const data = await response.json();
console.log(data.shloka, data.summary, data.detailed);
```

For complete API documentation and examples, see [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

## Troubleshooting

### Database Connection Issues

If you're getting database connection errors:

1. **Check your `.env` file**: Ensure all database credentials are correct
2. **Verify Supabase is running**: If using Supabase, ensure your project is not paused
3. **Check network connectivity**: Ensure you can reach the database host
4. **SSL Configuration**: Supabase requires SSL connections - this is handled automatically

### Common Errors

- **"No shlokas found"**: Run `python manage.py add_sample_shlokas` to add sample data
- **"Module not found"**: Ensure virtual environment is activated and dependencies are installed
- **"Database connection failed"**: Check your `.env` file and database credentials

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in settings or environment
2. Configure `ALLOWED_HOSTS` in settings
3. Set specific `CORS_ORIGINS` instead of `*`
4. Use a production-grade WSGI server (e.g., Gunicorn)
5. Set up proper database connection pooling
6. Configure static files serving
7. Set up proper logging

## API Documentation

For complete API documentation including:
- Detailed endpoint descriptions
- Request/response examples
- Error handling
- Data models
- Frontend integration examples

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

## License

[Add your license here]
