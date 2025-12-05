# Shloka Explanation Quality Improvement - Implementation Plan

## Overview
Restructure shloka explanations to use structured fields only (no duplication), add quality checking, and implement Celery-based improvement pipeline.

## Architecture Decision
**Option 1: Structured Fields Only** (Selected)
- Store only structured fields (summary, detailed_meaning, detailed_explanation, context, why_this_matters, modern_examples, themes, reflection_prompt)
- Generate `explanation_text` on-demand via property
- No data duplication
- Easy to query/filter by section

---

## Phase 1: Data Model Update ✅

### 1.1 Update ShlokaExplanation Model
- [x] Remove `explanation_type` field (no more summary/detailed distinction)
- [x] Remove `explanation_text` field (will be generated from structured fields)
- [x] Add new structured fields:
  - `summary` (TextField) - Brief overview
  - `detailed_meaning` (TextField) - Core meaning and philosophical significance
  - `detailed_explanation` (TextField) - Deeper understanding and interpretation
  - `context` (TextField) - When/why it was said, context in dialogue/story
  - `why_this_matters` (TextField) - Modern relevance and practical importance
  - `modern_examples` (JSONField) - Array of modern examples
  - `themes` (JSONField) - Array of key themes/tags
  - `reflection_prompt` (TextField) - Question for contemplation
- [x] Add quality tracking fields:
  - `quality_score` (IntegerField, 0-100, default=0)
  - `quality_checked_at` (DateTimeField, null=True)
  - `improvement_version` (IntegerField, default=0)
- [x] Update Meta: Remove `explanation_type` from unique_together, update indexes
- [x] Add `explanation_text` property for backward compatibility

### 1.2 Create Database Migration
- [x] Generate migration for model changes
- [x] Handle data migration (consolidate existing summary/detailed in Phase 6)
- [x] Fix migration conflicts and simplify migration chain

---

## Phase 2: Celery Setup ✅

### 2.1 Install Dependencies
- [x] Add `celery==5.3.4` to requirements.txt
- [x] Add `redis==5.0.1` to requirements.txt (or use RabbitMQ)
- [ ] Install dependencies

### 2.2 Configure Celery
- [x] Create `core/celery.py` with Celery app configuration
- [x] Update `core/__init__.py` to import Celery app
- [x] Add Celery settings to `core/settings.py`:
  - `CELERY_BROKER_URL` (Redis/RabbitMQ)
  - `CELERY_RESULT_BACKEND`
  - `CELERY_ACCEPT_CONTENT`
  - `CELERY_TASK_SERIALIZER`
  - `CELERY_RESULT_SERIALIZER`
  - `CELERY_TIMEZONE`

### 2.3 Test Celery Setup
- [x] Create simple test task
- [x] Start Celery worker
- [x] Test task execution

---

## Phase 3: Quality Checking System ✅

### 3.1 Create QualityCheckerService
- [x] Create `apps/sanatan_app/services/quality_checker.py`
- [x] Define quality metrics:
  - **Completeness** (0-25): All required sections present
  - **Clarity** (0-25): Readability and understandability
  - **Accuracy** (0-25): Alignment with traditional interpretations
  - **Relevance** (0-15): Modern application quality
  - **Structure** (0-10): Proper formatting and organization
- [x] Implement scoring algorithm using LLM evaluation

### 3.2 Quality Check Implementation
- [x] Create method to check completeness of all sections
- [x] Create method to evaluate clarity using LLM
- [x] Create method to evaluate accuracy using LLM
- [x] Create method to evaluate relevance using LLM
- [x] Create method to check structure/formatting
- [x] Combine scores into overall quality_score (0-100)

---

## Phase 4: Improvement System ✅

### 4.1 Create ImprovementService
- [x] Create `apps/sanatan_app/services/improvement_service.py`
- [x] Create targeted improvement prompts for each section
- [x] Implement section-specific improvement logic

### 4.2 Iterative Refinement
- [x] Implement improvement loop (max 3 iterations)
- [x] Track improvement_version
- [x] Only improve sections with low scores
- [x] Preserve high-quality content

---

## Phase 5: Celery Task Implementation ✅

### 5.1 Create Main Task
- [x] Create `apps/sanatan_app/tasks.py` (test task created)
- [x] Implement `improve_shloka_explanation(shloka_id)` task
- [x] Flow: Load → Check Quality → Improve → Re-check → Save

### 5.2 Error Handling & Retries
- [x] Add retry logic with exponential backoff
- [x] Handle API rate limits
- [x] Log errors appropriately
- [x] Add task status tracking

### 5.3 Progress Tracking
- [x] Add task state updates
- [ ] Consider WebSocket/SSE for real-time updates (optional - future enhancement)

### 5.4 Quality Checking Tasks ✅
- [x] Implement `check_shloka_quality(shloka_id)` task
  - Check quality only (no improvement)
  - Update quality_score and quality_checked_at
  - Return quality metrics
- [x] Implement `batch_check_shlokas_quality()` task
  - Process multiple shlokas from DB
  - Filter by criteria (e.g., never checked, checked before date, low scores)
  - Queue individual check tasks
- [x] Implement `batch_improve_shlokas()` task
  - Process multiple shlokas for improvement
  - Filter by quality score threshold
  - Queue individual improvement tasks

### 5.5 Scheduled Tasks (Celery Beat) ✅
- [x] Configure periodic tasks in `core/celery.py`
- [x] Add main daily QA task at 5 AM UTC (matches architecture diagram)
  - `batch_qa_existing_shlokas`: QA → If not good enough → Groq → QA again → Save
- [x] Add scheduled task to check quality of unchecked explanations (daily at 2 AM UTC)
- [x] Add scheduled task to improve low-quality explanations (weekly on Sunday at 3 AM UTC)
- [x] Add scheduled task to re-check old explanations (monthly on 1st at 4 AM UTC)

### 5.6 Architecture-Matching Tasks ✅
- [x] Implement `qa_and_improve_shloka(shloka_id)` task
  - Step 1: QA for existing Shloka (check quality)
  - Step 2: If not good enough → Send to Groq for improvement
  - Step 3: QA for regenerated Shloka (re-check quality)
  - Step 4: Save to DB
- [x] Implement `batch_qa_existing_shlokas()` task
  - Processes multiple shlokas for daily QA
  - Queues individual `qa_and_improve_shloka` tasks
  - Scheduled daily at 5 AM UTC

---

## Phase 6: Data Migration ❌ CANCELLED

**Decision**: We will create fresh explanations going forward. No migration of existing data needed.

### 6.1 Migration Script
- [x] ~~Create management command `migrate_explanations_to_structured`~~ (Not needed)
- [x] ~~For each shloka:~~ (Not needed)
  - ~~Load summary and detailed explanations~~
  - ~~Extract structured fields from both~~
  - ~~Merge/consolidate into single explanation~~
  - ~~Generate structured fields from existing explanation_text~~
  - ~~Save new structured explanation~~

### 6.2 Extract Structured Fields
- [x] ~~Parse existing explanation_text to extract:~~ (Not needed)
  - ~~Summary (from summary explanation)~~
  - ~~Detailed meaning (from MEANING section)~~
  - ~~Detailed explanation (from EXPLANATION section)~~
  - ~~Context (from context field or MEANING section)~~
  - ~~Practical application (from PRACTICAL APPLICATION section)~~
  - ~~Examples (from EXAMPLES section)~~
  - ~~Themes (from themes field or extract from content)~~

---

## Phase 7: Update Services ✅

### 7.1 Update GroqService ✅
- [x] Add `generate_structured_explanation()` method to return structured fields directly
- [x] Create structured prompt that requests JSON format
- [x] Parse JSON response to extract all structured fields
- [x] Fallback to text parsing if JSON parsing fails
- [x] Return dict with all structured fields matching model

### 7.2 Update ShlokaService ✅
- [x] Update `generate_and_store_explanation()` to work with structured fields
- [x] Remove explanation_type parameter (single explanation per shloka)
- [x] Use `generate_structured_explanation()` from GroqService
- [x] Save structured fields directly to model
- [x] Handle both create and update cases

### 7.3 Backward Compatibility ✅
- [x] Add `explanation_text` property to ShlokaExplanation model
- [x] Generate full text from structured fields
- [x] Update serializers to include both structured fields and explanation_text

### 7.4 Update Serializers ✅
- [x] Update `ExplanationSerializer` to handle new structured fields
- [x] Add explanation_text as read-only computed field (SerializerMethodField)
- [x] Include all structured fields in API responses
- [x] Include quality tracking fields

---

## Phase 8: Update Management Command ✅

### 8.1 Update fill_shloka_explanation_gaps.py ✅
- [x] Remove summary/detailed distinction
- [x] Work with single explanation per shloka
- [x] Use Celery tasks for processing (default behavior)
- [x] Update to create missing explanations and check/improve quality
- [x] Add options for dry-run, verbose, single shloka processing
- [x] Support both Celery (async) and synchronous processing modes

---

## Testing Strategy

### Unit Tests
- [ ] Test quality checker scoring
- [ ] Test improvement service
- [ ] Test Celery tasks
- [ ] Test GroqService structured field generation
- [ ] Test ShlokaService explanation generation

### Integration Tests
- [ ] Test full improvement pipeline
- [ ] Test API endpoints with new structure
- [ ] Test backward compatibility (explanation_text property)
- [ ] Test fresh explanation generation flow

---

## Rollout Plan

1. **Development**: Implement all phases in dev environment
2. **Testing**: Run comprehensive tests
3. **Validation**: Verify new explanation generation works correctly
4. **Deployment**: Deploy to production
5. **Monitoring**: Monitor Celery tasks and quality scores
6. **Fresh Explanations**: All new explanations will use structured format

---

## Notes

- Keep ReadingType enum for ReadingLog (still needed for user reading history)
- Maintain backward compatibility during transition
- Consider gradual rollout (process shlokas in batches)
- Monitor API costs (quality checking uses LLM calls)

