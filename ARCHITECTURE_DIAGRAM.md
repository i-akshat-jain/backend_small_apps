# Shloka Explanation Quality Improvement - Architecture Diagram

## Main Architecture Flow (As Designed)

This matches the architecture diagram you provided:

```mermaid
graph TB
    subgraph "Frontend & Backend"
        FE[Front End]
        BE[Back End]
        FE <-->|API Calls| BE
    end

    subgraph "Database"
        DB[(Database)]
        BE <-->|Read/Write| DB
    end

    subgraph "New Shloka Creation Flow"
        NewShloka[Creating New Shlokas<br/>separately]
        NewShloka -->|Generate| Groq1[Groq Service]
        Groq1 -->|Save| DB
    end

    subgraph "Daily QA Flow - 5 AM"
        CeleryBeat[Celery Beat<br/>Everyday at 5 AM]
        CeleryBeat -->|Trigger| BatchQA[batch_qa_existing_shlokas<br/>Batch QA Task]
        BatchQA <-->|Load/Update| DB
        
        BatchQA -->|Queue| QA[qa_and_improve_shloka<br/>QA for Existing Shlokas]
        QA <-->|Step 1: Check Quality| DB
        
        QA -->|Step 2: If Score < 70| Groq2[Groq Service<br/>Improvement]
        Groq2 -->|Step 3: Improved Content| ReQA[QA for Regenerated<br/>Shlokas]
        ReQA -->|Step 4: Re-check Quality| DB
        ReQA -->|Save to DB| DB
    end

    style CeleryBeat fill:#FFD700
    style QA fill:#90EE90
    style ReQA fill:#90EE90
    style Groq1 fill:#87CEEB
    style Groq2 fill:#87CEEB
    style DB fill:#FFE4B5
```

**Key Flow:**
1. **New Shlokas**: Created separately → Groq generates → Saved to DB
2. **Daily QA (5 AM)**: 
   - Celery Beat triggers batch QA
   - For each shloka: QA check → If low quality → Groq improvement → QA again → Save

## System Architecture Overview (Detailed)

### Main Architecture Flow (As Designed)

```mermaid
graph TB
    subgraph "Frontend & Backend"
        FE[Front End]
        BE[Back End]
        FE <-->|API Calls| BE
    end

    subgraph "Database"
        DB[(Database)]
        BE <-->|Read/Write| DB
    end

    subgraph "New Shloka Creation Flow"
        NewShloka[Creating New Shlokas<br/>separately]
        NewShloka -->|Generate| Groq1[Groq Service]
        Groq1 -->|Save| DB
    end

    subgraph "Daily QA Flow - 5 AM"
        CeleryBeat[Celery Beat<br/>Everyday at 5 AM]
        CeleryBeat -->|Trigger| BatchQA[Batch QA for<br/>Existing Shlokas]
        BatchQA <-->|Load/Update| DB
        
        BatchQA -->|If Not Good Enough| QA[QA for Existing<br/>Shlokas]
        QA <-->|Check Quality| DB
        
        QA -->|Score < Threshold| Groq2[Groq Service<br/>Improvement]
        Groq2 -->|Improved Content| ReQA[QA for Regenerated<br/>Shlokas]
        ReQA -->|Re-check Quality| DB
        ReQA -->|Save| DB
    end

    style CeleryBeat fill:#9AD708
    style QA fill:#90EE90
    style ReQA fill:#90EE90
    style Groq1 fill:#87CEEB
    style Groq2 fill:#87CEEB
```

## System Architecture Overview (Detailed)

```mermaid
graph TB
    subgraph "✅ COMPLETED - Phase 1: Data Model"
        Model[ShlokaExplanation Model]
        Model --> |Structured Fields| Fields[summary, detailed_meaning,<br/>detailed_explanation, context,<br/>why_this_matters, modern_examples,<br/>themes, reflection_prompt]
        Model --> |Quality Tracking| Quality[quality_score,<br/>quality_checked_at,<br/>improvement_version]
        Model --> |Computed Property| Prop[explanation_text property<br/>generates full text on-demand]
    end

    subgraph "✅ COMPLETED - Phase 2: Celery Setup"
        CeleryApp[Celery App]
        CeleryApp --> |Broker| Redis[Redis/RabbitMQ]
        CeleryApp --> |Result Backend| ResultBackend[Result Backend]
        CeleryApp --> |Auto-discover| Tasks[Tasks Module]
    end

    subgraph "✅ COMPLETED - Phase 3: Quality Checking"
        QCS[QualityCheckerService]
        QCS --> |Rule-based| Completeness[Completeness Check<br/>0-25 points]
        QCS --> |Rule-based| Structure[Structure Check<br/>0-10 points]
        QCS --> |LLM-based| LLMCheck[LLM Evaluation<br/>via GroqService]
        LLMCheck --> Clarity[Clarity Score<br/>0-25 points]
        LLMCheck --> Accuracy[Accuracy Score<br/>0-25 points]
        LLMCheck --> Relevance[Relevance Score<br/>0-15 points]
        Completeness --> Overall[Overall Score<br/>0-100]
        Structure --> Overall
        Clarity --> Overall
        Accuracy --> Overall
        Relevance --> Overall
    end

    subgraph "✅ COMPLETED - Phase 4: Improvement System"
        IS[ImprovementService]
        IS --> |Identify| Identify[Identify Sections<br/>to Improve]
        IS --> |Improve| Improve[Improve Sections<br/>via GroqService]
        IS --> |Iterate| Iterate[Max 3 Iterations<br/>Track improvement_version]
        Improve --> |Targeted Prompts| Groq[GroqService<br/>LLM API]
    end

    subgraph "✅ COMPLETED - Phase 5: Celery Tasks"
        Task1[improve_shloka_explanation Task]
        Task1 --> |1. Load| Load[Load Shloka &<br/>Explanation]
        Load --> |2. Check| Check[Check Quality<br/>QualityCheckerService]
        Check --> |3. If Low| ImproveTask[Improve Explanation<br/>ImprovementService]
        ImproveTask --> |4. Re-check| ReCheck[Re-check Quality]
        ReCheck --> |5. Save| Save[Save Updated<br/>Explanation]
        
        Task2[check_shloka_quality Task<br/>✅ NEW]
        Task2 --> |Check Only| CheckOnly[Check Quality<br/>Update Score]
        
        Task3[batch_check_shlokas_quality Task<br/>✅ NEW]
        Task3 --> |Queue| BatchCheck[Multiple Check Tasks]
        
        Task4[batch_improve_shlokas Task<br/>✅ NEW]
        Task4 --> |Queue| BatchImprove[Multiple Improve Tasks]
        
        Beat[Celery Beat Scheduler<br/>✅ NEW]
        Beat --> |Daily| Task3
        Beat --> |Weekly| Task4
        Beat --> |Monthly| Task3
        
        Task1 --> |Retry Logic| Retry[Exponential Backoff<br/>Max 3 retries]
        Task2 --> |Retry Logic| Retry
    end

    subgraph "❌ CANCELLED - Phase 6: Data Migration"
        Note1[No Migration Needed<br/>Creating Fresh Explanations Only]
    end

    subgraph "❌ REMAINING - Phase 7: Service Updates"
        GroqService[GroqService]
        GroqService --> |Update| UpdateGroq[Return Structured<br/>Fields Directly]
        ShlokaService[ShlokaService]
        ShlokaService --> |Update| UpdateShloka[Work with<br/>Structured Fields]
        Serializer[ExplanationSerializer]
        Serializer --> |Update| UpdateSerializer[Include Structured<br/>Fields + explanation_text]
    end

    subgraph "❌ REMAINING - Phase 8: Management Command"
        Cmd[fill_shloka_explanation_gaps.py]
        Cmd --> |Update| UpdateCmd[Remove summary/detailed<br/>Use Celery Tasks<br/>Check/Improve Quality]
    end

    %% Flow connections
    Task -.->|Uses| QCS
    Task -.->|Uses| IS
    IS -.->|Uses| QCS
    IS -.->|Uses| Groq
    QCS -.->|Uses| Groq

    style Model fill:#90EE90
    style CeleryApp fill:#90EE90
    style QCS fill:#90EE90
    style IS fill:#90EE90
    style Task fill:#90EE90
    style Migrate fill:#FFB6C1
    style GroqService fill:#FFB6C1
    style ShlokaService fill:#FFB6C1
    style Serializer fill:#FFB6C1
    style Cmd fill:#FFB6C1
```

## Detailed Flow Diagram

```mermaid
sequenceDiagram
    participant User/API
    participant Celery as Celery Task
    participant DB as Database
    participant QC as QualityCheckerService
    participant IS as ImprovementService
    participant Groq as GroqService

    Note over User/API,Groq: ✅ COMPLETED FLOW

    User/API->>Celery: Trigger improve_shloka_explanation(shloka_id)
    Celery->>DB: Load Shloka & Explanation
    DB-->>Celery: ShlokaExplanation object

    Celery->>QC: check_quality(explanation)
    
    QC->>QC: _check_completeness() [Rule-based]
    QC->>QC: _check_structure() [Rule-based]
    QC->>Groq: _check_with_llm() [LLM Evaluation]
    Groq-->>QC: Clarity, Accuracy, Relevance scores
    
    QC->>QC: Calculate overall_score (0-100)
    QC-->>Celery: Quality result with scores & feedback

    alt Quality Score < Threshold (70)
        Celery->>IS: improve_explanation(explanation, max_iterations=3)
        
        loop For each iteration (max 3)
            IS->>QC: check_quality() to identify issues
            QC-->>IS: Quality feedback
            
            IS->>IS: _identify_sections_to_improve()
            IS->>IS: _improve_sections(sections)
            
            loop For each section to improve
                IS->>Groq: Generate improved content
                Groq-->>IS: Improved section content
                IS->>IS: _update_section()
            end
            
            IS->>DB: Save improved explanation
            IS->>QC: Re-check quality
            
            alt Score >= Threshold
                IS-->>Celery: Improvement complete
            end
        end
        
        IS-->>Celery: Final result with scores
    else Quality Score >= Threshold
        Celery-->>User/API: Already meets quality threshold
    end

    Celery->>DB: Update quality_score, quality_checked_at
    Celery-->>User/API: Task result with improvement details
```

## Data Flow Diagram

```mermaid
flowchart LR
    subgraph "✅ New Model Structure"
        New[Single ShlokaExplanation]
        New --> S1[summary: TextField]
        New --> S2[detailed_meaning: TextField]
        New --> S3[detailed_explanation: TextField]
        New --> S4[context: TextField]
        New --> S5[why_this_matters: TextField]
        New --> S6[modern_examples: JSONField]
        New --> S7[themes: JSONField]
        New --> S8[reflection_prompt: TextField]
        New --> Q1[quality_score: IntegerField]
        New --> Q2[quality_checked_at: DateTimeField]
        New --> Q3[improvement_version: IntegerField]
        New --> |Computed| Prop[explanation_text property]
    end

    subgraph "❌ REMAINING - Phase 7: Service Updates"
        GroqService[GroqService<br/>Generate Structured Fields]
        GroqService --> |Returns| Structured[Structured Fields Dict]
        Structured --> |Save| New
    end

    style New fill:#90EE90
    style GroqService fill:#FFB6C1
    style Structured fill:#FFB6C1
```

## Component Interaction Diagram

```mermaid
graph TB
    subgraph "External Services"
        GroqAPI[Groq LLM API]
        RedisQueue[Redis Queue]
    end

    subgraph "Django Application"
        subgraph "Models"
            ShlokaModel[Shloka Model]
            ExplanationModel[ShlokaExplanation Model<br/>✅ Structured Fields]
        end

        subgraph "Services ✅"
            GroqService[GroqService<br/>❌ Needs Update]
            QualityService[QualityCheckerService<br/>✅ Complete]
            ImprovementService[ImprovementService<br/>✅ Complete]
            ShlokaService[ShlokaService<br/>❌ Needs Update]
        end

        subgraph "Tasks ✅"
            CeleryTask[improve_shloka_explanation<br/>✅ Complete]
        end

        subgraph "API Layer"
            Views[Views]
            Serializers[Serializers<br/>❌ Needs Update]
        end

        subgraph "Management Commands"
            FillGaps[fill_shloka_explanation_gaps.py<br/>❌ Needs Update]
        end
    end

    CeleryTask --> |Uses| QualityService
    CeleryTask --> |Uses| ImprovementService
    CeleryTask --> |Reads/Writes| ExplanationModel
    CeleryTask --> |Queued via| RedisQueue

    QualityService --> |Uses| GroqService
    ImprovementService --> |Uses| GroqService
    ImprovementService --> |Uses| QualityService

    GroqService --> |Calls| GroqAPI

    Views --> |Uses| Serializers
    Serializers --> |Serializes| ExplanationModel
    Serializers --> |Reads| ShlokaModel

    ShlokaService --> |Uses| GroqService
    ShlokaService --> |Reads/Writes| ExplanationModel

    FillGaps --> |Should Use| CeleryTask
    FillGaps --> |Reads/Writes| ExplanationModel

    style ExplanationModel fill:#90EE90
    style QualityService fill:#90EE90
    style ImprovementService fill:#90EE90
    style CeleryTask fill:#90EE90
    style GroqService fill:#FFB6C1
    style ShlokaService fill:#FFB6C1
    style Serializers fill:#FFB6C1
    style FillGaps fill:#FFB6C1
```

## Summary

### ✅ Completed (Phases 1-5)
1. **Data Model**: Structured fields, quality tracking, computed `explanation_text` property
2. **Celery Setup**: Configured with Redis, auto-discovery, retry logic
3. **Quality Checking**: Multi-dimensional scoring (completeness, clarity, accuracy, relevance, structure)
4. **Improvement System**: Iterative refinement with targeted section improvements
5. **Celery Tasks**: 
   - `improve_shloka_explanation`: Complete pipeline for quality checking and improvement
   - `check_shloka_quality`: Quality check only (no improvement)
   - `batch_check_shlokas_quality`: Batch quality checking with filtering
   - `batch_improve_shlokas`: Batch improvement processing
6. **Scheduled Tasks (Celery Beat)**: 
   - Daily: Check unchecked explanations
   - Weekly: Improve low-quality explanations
   - Monthly: Re-check old explanations

### ❌ Remaining (Phases 7-8)
1. **Service Updates**: Update GroqService and ShlokaService to generate and work with structured fields directly
2. **Serializer Updates**: Update API serializers to expose structured fields
3. **Management Command**: Update fill_gaps command to use new structure and Celery tasks

### ❌ Cancelled
1. **Data Migration (Phase 6)**: Not needed - creating fresh explanations only

