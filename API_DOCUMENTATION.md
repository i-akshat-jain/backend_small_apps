# Sanatan App API Documentation

Complete API documentation for the Sanatan App backend. This document provides detailed information about all available endpoints, request/response formats, and error handling.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: (To be configured)

## Authentication

Currently, the API does not require authentication. All endpoints are publicly accessible.

## Endpoints

### 1. Root Endpoint

Get basic API information.

**Endpoint**: `GET /`

**Response**:
```json
{
  "message": "Sanatan App API",
  "version": "1.0.0",
  "status": "running"
}
```

**Status Codes**:
- `200 OK`: Success

---

### 2. Health Check

Check if the API is running and healthy.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy"
}
```

**Status Codes**:
- `200 OK`: API is healthy

---

### 3. Get Random Shloka

Get a random shloka with both summary and detailed explanations. If explanations don't exist, they will be generated on-demand using AI.

**Endpoint**: `GET /api/shlokas/random`

**Response**:
```json
{
  "shloka": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "book_name": "Bhagavad Gita",
    "chapter_number": 2,
    "verse_number": 47,
    "sanskrit_text": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
    "transliteration": "karmaṇy-evādhikāras te mā phaleṣhu kadāchana\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi",
    "created_at": "2025-01-24T10:30:00Z",
    "updated_at": "2025-01-24T10:30:00Z"
  },
  "summary": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "shloka_id": "550e8400-e29b-41d4-a716-446655440000",
    "explanation_type": "summary",
    "explanation_text": "This verse teaches us about the nature of action and detachment...",
    "ai_model_used": "openai/gpt-oss-20b",
    "generation_prompt": "Explain this shloka...",
    "created_at": "2025-01-24T10:30:05Z",
    "updated_at": "2025-01-24T10:30:05Z"
  },
  "detailed": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "shloka_id": "550e8400-e29b-41d4-a716-446655440000",
    "explanation_type": "detailed",
    "explanation_text": "This profound verse from the Bhagavad Gita encapsulates one of the most important teachings of Lord Krishna...",
    "ai_model_used": "openai/gpt-oss-20b",
    "generation_prompt": "Explain this shloka...",
    "created_at": "2025-01-24T10:30:10Z",
    "updated_at": "2025-01-24T10:30:10Z"
  }
}
```

**Status Codes**:
- `200 OK`: Success
- `404 Not Found`: No shlokas found in database
- `500 Internal Server Error`: Server error (database connection issues, AI service errors, etc.)

**Error Response** (404):
```json
{
  "detail": "No shlokas found in database. Please add shlokas using the command: python manage.py add_sample_shlokas"
}
```

**Error Response** (500):
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

### 4. Get Shloka by ID

Get a specific shloka by its UUID with both summary and detailed explanations. If explanations don't exist, they will be generated on-demand using AI.

**Endpoint**: `GET /api/shlokas/{shloka_id}`

**Path Parameters**:
- `shloka_id` (UUID, required): The unique identifier of the shloka

**Example**: `GET /api/shlokas/550e8400-e29b-41d4-a716-446655440000`

**Response**: Same structure as "Get Random Shloka" endpoint

**Status Codes**:
- `200 OK`: Success
- `404 Not Found`: Shloka with the given ID not found
- `500 Internal Server Error`: Server error

**Error Response** (404):
```json
{
  "detail": "Shloka with ID 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

---

## Data Models

### Shloka

Represents a shloka (verse) from Hindu scriptures.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier |
| `book_name` | String | Name of the book (e.g., "Bhagavad Gita") |
| `chapter_number` | Integer | Chapter number |
| `verse_number` | Integer | Verse number |
| `sanskrit_text` | String | Original Sanskrit text |
| `transliteration` | String (optional) | Transliteration in Roman script |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### Explanation

Represents an AI-generated explanation of a shloka.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier |
| `shloka_id` | UUID | Reference to the shloka |
| `explanation_type` | String | Either "summary" or "detailed" |
| `explanation_text` | String | The explanation text |
| `ai_model_used` | String (optional) | AI model used for generation |
| `generation_prompt` | String (optional) | Prompt used for generation |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### ShlokaResponse

Complete response containing a shloka with its explanations.

| Field | Type | Description |
|-------|------|-------------|
| `shloka` | Shloka | The shloka object |
| `summary` | Explanation (optional) | Summary explanation |
| `detailed` | Explanation (optional) | Detailed explanation |

---

## Error Handling

All endpoints follow consistent error handling:

1. **404 Not Found**: Resource not found (e.g., shloka ID doesn't exist, no shlokas in database)
2. **500 Internal Server Error**: Server-side errors (database connection issues, AI service failures, etc.)

All error responses follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Rate Limiting

Currently, there are no rate limits. However, AI-generated explanations are cached in the database, so repeated requests for the same shloka will be faster.

---

## CORS

The API is configured to allow CORS requests. In development, all origins are allowed. In production, specific origins should be configured.

---

## Notes for Frontend Developers

1. **Explanation Generation**: When requesting a shloka, if explanations don't exist, they will be generated automatically. This may take a few seconds on the first request. Subsequent requests will be instant as explanations are cached.

2. **UUID Format**: All IDs are UUIDs in the format: `550e8400-e29b-41d4-a716-446655440000`

3. **Error Handling**: Always check the status code and handle errors appropriately. The `detail` field in error responses contains a human-readable error message.

4. **Random Shloka**: The random endpoint uses database-level randomization, so each request may return a different shloka.

5. **Date Format**: All timestamps are in ISO 8601 format (UTC): `2025-01-24T10:30:00Z`

---

## Example Usage

### JavaScript/TypeScript (Fetch API)

```javascript
// Get random shloka
async function getRandomShloka() {
  try {
    const response = await fetch('http://localhost:8000/api/shlokas/random');
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    const data = await response.json();
    console.log('Shloka:', data.shloka);
    console.log('Summary:', data.summary?.explanation_text);
    console.log('Detailed:', data.detailed?.explanation_text);
    
    return data;
  } catch (error) {
    console.error('Error fetching shloka:', error.message);
    throw error;
  }
}

// Get specific shloka by ID
async function getShlokaById(shlokaId) {
  try {
    const response = await fetch(`http://localhost:8000/api/shlokas/${shlokaId}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching shloka:', error.message);
    throw error;
  }
}
```

### React Native Example

```typescript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

interface ShlokaResponse {
  shloka: {
    id: string;
    book_name: string;
    chapter_number: number;
    verse_number: number;
    sanskrit_text: string;
    transliteration?: string;
    created_at: string;
    updated_at: string;
  };
  summary?: {
    id: string;
    explanation_text: string;
    explanation_type: string;
  };
  detailed?: {
    id: string;
    explanation_text: string;
    explanation_type: string;
  };
}

export const getRandomShloka = async (): Promise<ShlokaResponse> => {
  try {
    const response = await axios.get<ShlokaResponse>(
      `${API_BASE_URL}/api/shlokas/random`
    );
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      throw new Error(error.response.data.detail || 'Failed to fetch shloka');
    }
    throw error;
  }
};

export const getShlokaById = async (id: string): Promise<ShlokaResponse> => {
  try {
    const response = await axios.get<ShlokaResponse>(
      `${API_BASE_URL}/api/shlokas/${id}`
    );
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      throw new Error(error.response.data.detail || 'Failed to fetch shloka');
    }
    throw error;
  }
};
```

---

## Support

For issues or questions, please contact the development team or refer to the main README.md file.

