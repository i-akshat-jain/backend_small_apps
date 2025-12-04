# Testing Guide - Sanatan App

This guide explains how to run and understand the comprehensive test suite for the Sanatan App.

## Overview

The test suite includes:
- **Backend Unit Tests**: Django TestCase-based tests for all views and services
- **Backend Integration Tests**: End-to-end API testing script
- **Frontend Unit Tests**: Jest-based tests for API service and components

## Backend Testing

### Unit Tests

Location: `apps/sanatan_app/tests.py`

These tests use Django's TestCase framework and test individual components in isolation.

#### Running Unit Tests

```bash
cd backend_apps
source venv/bin/activate
python manage.py test apps.sanatan_app.tests
```

#### Running Specific Test Classes

```bash
# Test only authentication
python manage.py test apps.sanatan_app.tests.AuthenticationTests

# Test only favorites
python manage.py test apps.sanatan_app.tests.FavoriteTests

# Test only stats
python manage.py test apps.sanatan_app.tests.UserStatsTests
```

#### Running Specific Test Methods

```bash
# Test only signup
python manage.py test apps.sanatan_app.tests.AuthenticationTests.test_signup_success
```

#### Test Coverage

The unit tests cover:
- ✅ Authentication (signup, login, token refresh)
- ✅ Shloka endpoints (random, detail)
- ✅ Reading logs
- ✅ User stats
- ✅ Favorites (GET, POST, DELETE with query params)
- ✅ Achievements
- ✅ Chatbot endpoints
- ✅ Service layer (StatsService, AchievementService)
- ✅ Authentication requirements

### Integration Tests

Location: `test_all_endpoints.py`

This script tests the entire API end-to-end, simulating real user interactions.

#### Prerequisites

1. Start the Django development server:
```bash
cd backend_apps
source venv/bin/activate
python manage.py runserver
```

2. Ensure you have test data in the database (shlokas, achievements, etc.)

#### Running Integration Tests

```bash
cd backend_apps
source venv/bin/activate
python test_all_endpoints.py --base-url http://localhost:8000
```

#### What It Tests

The integration test script:
1. Tests health check
2. Creates a new user (signup)
3. Logs in the user
4. Fetches a random shloka
5. Gets shloka details
6. Creates a reading log
7. Gets user stats
8. Tests favorites (add, list, delete)
9. Gets achievements
10. Tests chatbot (conversations, messages)

#### Output

The script provides color-coded output:
- ✅ Green: Test passed
- ❌ Red: Test failed
- ⚠️ Yellow: Warning
- ℹ️ Blue: Information

## Frontend Testing

### Setup

The frontend uses Jest with React Native testing utilities.

#### Running Frontend Tests

```bash
cd StanatanApp
npm test
```

#### Running Tests in Watch Mode

```bash
npm test -- --watch
```

#### Running Specific Tests

```bash
# Test only API service
npm test -- api.test.ts

# Test only components
npm test -- KnowledgeCard.test.tsx
```

### Test Files

1. **API Service Tests** (`src/services/__tests__/api.test.ts`)
   - Tests all API methods
   - Mocks fetch calls
   - Validates request/response formats

2. **Component Tests** (`src/components/__tests__/KnowledgeCard.test.tsx`)
   - Tests component rendering
   - Tests user interactions
   - Tests state management

3. **Screen Tests** (`src/screens/__tests__/HomeScreen.test.tsx`)
   - Tests screen rendering
   - Tests data loading
   - Tests error handling

## Test Data Setup

### Backend Test Data

The unit tests create their own test data automatically. For integration tests, you may need:

1. **Shlokas**: Use the management command:
```bash
python manage.py add_sample_shlokas
```

2. **Achievements**: Create via Django admin or management command:
```python
from apps.sanatan_app.models import Achievement

Achievement.objects.create(
    code="first_read",
    name="First Steps",
    description="Read your first shloka",
    condition_type="shlokas_read",
    condition_value=1
)
```

## Common Issues

### Backend Tests

1. **Database errors**: Make sure migrations are up to date:
```bash
python manage.py migrate
```

2. **Import errors**: Ensure virtual environment is activated and dependencies are installed:
```bash
pip install -r requirements.txt
```

3. **Authentication errors**: Tests use JWT tokens - ensure `djangorestframework-simplejwt` is installed

### Frontend Tests

1. **Module not found**: Ensure all dependencies are installed:
```bash
npm install
```

2. **Mock errors**: Check that mocks are properly set up in test files

3. **Async errors**: Use `waitFor` for async operations in tests

## Best Practices

1. **Run tests before committing**: Always run the full test suite before pushing code
2. **Write tests for new features**: Add tests when adding new functionality
3. **Keep tests isolated**: Each test should be independent and not rely on others
4. **Use descriptive test names**: Test names should clearly describe what they test
5. **Mock external dependencies**: Mock API calls, timers, and other external dependencies

## Continuous Integration

For CI/CD pipelines, you can run:

```bash
# Backend
cd backend_apps && python manage.py test apps.sanatan_app.tests

# Frontend
cd StanatanApp && npm test -- --coverage --watchAll=false
```

## Coverage Reports

### Backend Coverage

Install coverage:
```bash
pip install coverage
```

Run with coverage:
```bash
coverage run --source='.' manage.py test apps.sanatan_app.tests
coverage report
coverage html  # Generates HTML report
```

### Frontend Coverage

Jest automatically generates coverage:
```bash
npm test -- --coverage
```

## Troubleshooting

### Tests are slow

- Use `--keepdb` flag for Django tests to reuse database:
```bash
python manage.py test --keepdb apps.sanatan_app.tests
```

### Tests fail randomly

- Check for race conditions
- Ensure proper cleanup in `tearDown` methods
- Use `setUp` and `tearDown` consistently

### Integration tests fail

- Ensure server is running
- Check base URL is correct
- Verify database has test data
- Check GROQ_API_KEY for chatbot tests

## Next Steps

1. Add more edge case tests
2. Increase test coverage to 90%+
3. Add performance tests
4. Add E2E tests with Detox or similar
5. Set up CI/CD pipeline

