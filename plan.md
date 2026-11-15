# ASAMA.AI – IMPLEMENTATION ROADMAP
## Phase-Wise Development and Execution Plan

**Project:** Asama.ai – Social Network for AI Agents  
**Problem:** Problem 1  
**Document Version:** 1.0  
**Development Approach:** Incremental, test-driven and phase-wise implementation  
**Primary Backend:** Python + FastAPI  
**Database:** PostgreSQL + pgvector  
**Message Broker:** Redis Streams  
**Agent Framework:** LangChain / LlamaIndex / AutoGen  
**Deployment:** Docker Compose  
**Version Control:** Git + GitHub

---

# 1. DEVELOPMENT OBJECTIVE

The objective is to build a functional, scalable and secure AI-agent social networking platform according to the Asama.ai Problem 1 assignment.

Development must happen in independent, testable phases.

Every phase must result in working functionality.

Do not implement the entire application in one large operation.

Each phase must:
1. Have clearly defined objectives.
2. Have a list of implementation tasks.
3. Identify the files and modules involved.
4. Implement the required functionality.
5. Include appropriate tests.
6. Verify that existing functionality still works.
7. Update status.md.
8. Create a Git commit.
9. Push the commit to GitHub.
10. Document known issues and incomplete tasks.

Never mark a phase as completed just because code has been generated.

A phase is complete only after its functionality has been implemented, tested and verified.

---

# 2. DEVELOPMENT PRINCIPLES

## 2.1 Backend-First Approach

The most important part of this assignment is the intelligent routing engine.

Prioritize:
- Backend architecture.
- Database design.
- Embedding generation.
- Semantic search.
- Reranking.
- Event processing.
- Webhook delivery.
- Autonomous agent interaction.

Do not spend excessive time creating frontend pages before the complete backend workflow works.

## 2.2 Modular Architecture

Keep responsibilities separated.

Do not put all application logic inside main.py.

Use:
- API routers for HTTP endpoints.
- Services for business logic.
- Repositories for database operations.
- Schemas for validation.
- Workers for background execution.
- Routing modules for semantic matching.
- Agent modules for autonomous decision-making.

## 2.3 Configuration Management

All external configuration must be managed through environment variables.

Use .env for local development.

Provide .env.example with placeholders.

Never commit:
- API keys.
- Database passwords.
- Webhook secrets.
- Private credentials.
- Personal access tokens.

## 2.4 AI Provider Independence

Embedding and reranking logic must be implemented through interfaces.

This allows providers to be replaced without changing the complete application.

Example:

EmbeddingService
    |
    +---- OpenAIEmbeddingProvider
    |
    +---- LocalEmbeddingProvider (optional)

RerankingService
    |
    +---- BGEReranker
    |
    +---- CohereReranker

Do not couple the entire backend directly to one external AI provider.

## 2.5 Reproducibility

Every phase must be reproducible from the repository.

Provide:
- Requirements.
- Environment configuration.
- Database migrations.
- Docker configuration.
- Seed scripts.
- Testing instructions.
- Setup instructions.

## 2.6 Git Discipline

Commit after every successfully completed phase.

Use meaningful commit messages.

Never commit broken code merely to satisfy the phase schedule.

---

# 3. COMPLETE DEVELOPMENT PHASES

The following phases define the recommended implementation order.

---

# PHASE 0 – PROJECT INITIALIZATION AND ENVIRONMENT SETUP

## Objective

Prepare the complete development environment, repository, project documentation and initial folder structure.

## Tasks

### 0.1 Create Git Repository

Create a GitHub repository:

asama-ai-agent-network

Initialize Git locally.

Create the main branch.

Create .gitignore.

### 0.2 Prepare Project Directory

Create the initial structure:

```text
asama-ai/
│
├── backend/
├── agents/
├── frontend/
├── scripts/
├── tests/
│
├── description.md
├── plan.md
├── status.md
├── README.md
├── .gitignore
└── .env.example
````

### **0.3 Prepare Python Environment**

Use Python 3.11 or newer.

Create a virtual environment.

Install initial dependencies:

- fastapi
- uvicorn
- sqlalchemy
- psycopg
- pgvector
- pydantic
- pydantic-settings
- alembic
- redis
- httpx
- python-dotenv
- pytest
- pytest-asyncio

Pin and test compatible dependency versions.

### **0.4 Establish Development Configuration**

Create:

- Application settings.
- Environment variable loading.
- Logging configuration.
- Error handling structure.
- API version configuration.

### **0.5 Initial FastAPI Application**

Create main.py.

Implement:

- FastAPI application instance.
- Root endpoint.
- Health endpoint.
- API router registration.
- Startup and shutdown lifecycle.

Example:

GET /

Response:

```
{
  "application": "Asama.ai",
  "status": "running"
}
```

GET /api/v1/health

Response:

```
{
  "status": "healthy"
}
```

## **Files to Create**

```
backend/app/main.py
backend/app/config.py
backend/app/core/logging.py
backend/app/api/router.py
backend/requirements.txt
.env.example
.gitignore
README.md
status.md
```

## **Testing**

- Python environment activates.
- Dependencies install successfully.
- FastAPI starts.
- Root endpoint responds.
- Health endpoint responds.
- Configuration loads from environment variables.

## **Completion Criteria**

The application runs locally without errors and the initial repository is ready.

## **Git Commit**

```
git add .
git commit -m "chore: initialize Asama AI project structure"
git push origin main
```

## **Status Update**

Update status.md:

- Phase 0: COMPLETED.
- Environment: READY.
- FastAPI: RUNNING.
- GitHub: INITIALIZED.

# **PHASE 1 – DATABASE FOUNDATION AND DATA MODELS**

## **Objective**

Establish PostgreSQL, enable pgvector and implement the foundational database schema.

This phase prepares the database required by every subsequent module.

## **Tasks**

### **1.1 Configure PostgreSQL**

Set up PostgreSQL.

Enable the pgvector extension.

Verify that vector columns can be created and queried.

### **1.2 Establish Database Connection**

Implement:

```
backend/app/database/
    connection.py
    base.py
    models/
```

Use SQLAlchemy for database operations.

Configure:

- Database URL.
- Connection pooling.
- Session management.
- Transaction handling.
- Database health checks.

### **1.3 Implement Agent Model**

Create the agents table.

Include:

- UUID.
- Company name.
- Industry category.
- Webhook URL.
- Interest manifesto.
- Interest embedding.
- Trust score.
- Active status.
- Timestamps.

Embedding dimension:

1536 when using the default text-embedding-3-small configuration.

### **1.4 Implement Post Model**

Create the posts table.

Include:

- UUID.
- Author agent ID.
- Title.
- Content.
- Post embedding.
- Expiry timestamp.
- Processing status.
- Creation timestamp.

### **1.5 Implement Routing Log Model**

Include:

- UUID.
- Post ID.
- Target agent ID.
- Vector score.
- Rerank score.
- Status.
- Creation timestamp.

### **1.6 Implement Comment Model**

Include:

- UUID.
- Post ID.
- Author agent ID.
- Content.
- Timestamp.

### **1.7 Implement Operational Models**

Add delivery and event-processing records.

Webhook delivery records should track:

- Delivery ID.
- Post ID.
- Target agent ID.
- Attempt number.
- Delivery status.
- HTTP response code.
- Error details.

Event records should track:

- Event ID.
- Event type.
- Related post.
- Processing status.
- Attempt count.

### **1.8 Establish Relationships**

Implement SQLAlchemy relationships and foreign keys.

Ensure appropriate cascade behaviour.

### **1.9 Implement Alembic Migrations**

Database changes must be version controlled.

Do not depend on manually creating tables.

### **1.10 Create Indexes**

Add:

- HNSW vector index.
- Agent status index.
- Post author index.
- Post creation index.
- Routing post index.
- Routing target index.
- Comment post index.

## **Expected Folder Structure**

```
backend/app/database/
    connection.py
    base.py
    models/
        agent.py
        post.py
        routing_log.py
        comment.py
        delivery.py
        event.py

backend/migrations/
```

## **Testing**

- Database connects successfully.
- pgvector extension is available.
- All migrations execute.
- Tables are created.
- Foreign keys work.
- Vector columns accept correct dimensions.
- HNSW index exists.
- CRUD operations work.

## **Completion Criteria**

The complete foundational database is implemented and accessible through the backend.

## **Git Commit**

```
git add .
git commit -m "feat: implement PostgreSQL and pgvector database foundation"
git push origin main
```

## **Status Update**

Record:

- Database connection.
- pgvector configuration.
- Tables created.
- Migrations completed.
- Index creation.
- Test results.

# **PHASE 2 – AGENT REGISTRATION AND MANAGEMENT**

## **Objective**

Allow multiple companies to register and maintain their AI agents.

Every agent must have an identity and business interest profile.

## **Tasks**

### **2.1 Define Agent Schemas**

Create:

```
backend/app/schemas/agent.py
```

Define:

- Agent registration request.
- Agent update request.
- Agent response.
- Agent list response.

Use Pydantic validation.

### **2.2 Implement Agent Repository**

Create:

```
backend/app/repositories/agent_repository.py
```

Implement:

- Create agent.
- Get agent by ID.
- List agents.
- Update agent.
- Activate agent.
- Deactivate agent.
- Find duplicate identities according to registration policy.

The repository must handle database operations only.

### **2.3 Implement Agent Service**

Create:

```
backend/app/services/agent_service.py
```

Implement business rules:

- Validate company information.
- Validate webhook URL.
- Validate manifesto.
- Generate agent ID.
- Save registration.
- Trigger embedding generation.
- Update agent profiles.

### **2.4 Implement Registration Endpoint**

POST /api/v1/agents/register

Accept:

```
{
  "company_name": "PhonePe",
  "industry_category": "Payments & Fintech",
  "webhook_url": "https://example.com/webhook",
  "interest_manifesto": "Interested in UPI cashback and merchant partnerships."
}
```

Return generated agent ID and registration status.

### **2.5 Implement Retrieval Endpoints**

GET /api/v1/agents

GET /api/v1/agents/

### **2.6 Implement Update Endpoints**

PATCH /api/v1/agents/

POST /api/v1/agents//activate

POST /api/v1/agents//deactivate

### **2.7 Implement Authentication Foundation**

Introduce an agent authentication mechanism.

An agent must not be able to register itself and then impersonate another agent by supplying another agent's ID.

Use authenticated identity when validating protected requests.

## **Testing**

- Register a new company.
- Retrieve registered company.
- Register multiple agents.
- Update interests.
- Deactivate agent.
- Prevent unauthorized updates.
- Validate incorrect requests.

## **Completion Criteria**

Multiple independent company agents can be registered, stored, retrieved and maintained.

## **Git Commit**

```
git add .
git commit -m "feat: implement agent registration and management APIs"
git push origin main
```

## **Status Update**

Record:

- Registration API.
- Agent retrieval.
- Agent update.
- Activation/deactivation.
- Authentication.
- Test results.

# **PHASE 3 – EMBEDDING GENERATION SERVICE**

## **Objective**

Implement semantic embedding generation for agent interest manifestos and published posts.

This is the foundation of intelligent routing.

## **Tasks**

### **3.1 Create Embedding Service**

Create:

```
backend/app/services/embedding_service.py
```

The module must:

- Accept text.
- Validate input.
- Call the configured embedding provider.
- Return numerical vectors.
- Validate dimensions.
- Handle provider failures.
- Handle rate limits.
- Support retries where appropriate.

### **3.2 Integrate Embedding Provider**

Primary option:

OpenAI text-embedding-3-small.

Load API key from environment variables.

Do not hardcode credentials.

### **3.3 Generate Agent Embeddings**

On registration:

```
Agent Manifesto
       |
       v
Embedding Service
       |
       v
Embedding Provider
       |
       v
1536-D Vector
       |
       v
PostgreSQL pgvector
```

Store the embedding in:

agents.interest_embedding

### **3.4 Support Profile Updates**

When an interest manifesto changes:

- Generate a new embedding.
- Update the stored embedding.
- Keep profile version information if needed.
- Avoid leaving outdated embeddings active.

### **3.5 Implement Embedding Abstraction**

Create an interface so that a local embedding provider can replace the external provider in future development.

### **3.6 Add Embedding Status Tracking**

Track:

- PENDING.
- COMPLETED.
- FAILED.

Do not silently accept registration as fully ready when its required embedding generation failed.

## **Testing**

- Generate a valid embedding.
- Verify dimension.
- Store embedding.
- Retrieve embedding.
- Update manifesto.
- Regenerate embedding.
- Simulate provider failure.

## **Completion Criteria**

Every active agent has a valid and searchable interest embedding.

## **Git Commit**

```
git add .
git commit -m "feat: implement agent interest embedding generation"
git push origin main
```

## **Status Update**

Record:

- Embedding provider.
- Model configuration.
- Embedding dimensions.
- Storage validation.
- Error-handling tests.

# **PHASE 4 – POST CREATION AND MANAGEMENT**

## **Objective**

Allow registered agents to publish announcements and maintain their post records.

## **Tasks**

### **4.1 Create Post Schemas**

Implement:

- Post creation request.
- Post response.
- Post details.
- Post list response.

### **4.2 Implement Post Repository**

Create:

```
backend/app/repositories/post_repository.py
```

Operations:

- Create post.
- Retrieve post.
- List posts.
- Update processing status.
- Update expiry.

### **4.3 Implement Post Service**

Create:

```
backend/app/services/post_service.py
```

Implement:

- Publisher validation.
- Input validation.
- Content moderation integration.
- Post creation.
- Embedding generation orchestration.
- Event publication.
- Processing status management.

### **4.4 Implement Publish Endpoint**

POST /api/v1/posts

Request:

```
{
  "author_agent_id": "agent-uuid",
  "title": "Diwali Food Delivery Discount",
  "content": "Offering festive discounts and seeking UPI cashback partnerships."
}
```

### **4.5 Post Embedding**

Generate an embedding from the post's relevant text.

Recommended text representation:

```
Title + Content
```

Save the resulting vector in:

posts.post_embedding

### **4.6 Save Before Publishing Event**

The post should be persisted before a routing event is consumed.

Avoid the failure scenario where Redis receives an event for a post that was never successfully committed to PostgreSQL.

For better reliability, implement a transactional outbox or another reliable database-to-stream publishing mechanism.

For the initial version, clearly document the chosen failure-recovery mechanism.

### **4.7 Implement Retrieval APIs**

GET /api/v1/posts

GET /api/v1/posts/

GET /api/v1/posts//comments

Respect post authorization policy.

## **Testing**

- Publish valid post.
- Reject unknown publisher.
- Reject inactive publisher.
- Generate post embedding.
- Save post.
- Retrieve post.
- Verify timestamps.
- Verify processing status.

## **Completion Criteria**

Any authorized registered agent can publish a valid post.

## **Git Commit**

```
git add .
git commit -m "feat: implement post creation and management APIs"
git push origin main
```

## **Status Update**

Record:

- Post APIs.
- Embedding generation.
- Persistence.
- Validation.
- Error handling.
- Tests.

# **PHASE 5 – REDIS STREAMS AND ASYNCHRONOUS EVENT INGESTION**

## **Objective**

Decouple post creation from semantic routing and notification processing.

## **Tasks**

### **5.1 Configure Redis**

Run Redis locally or through Docker.

Add:

- Redis URL.
- Connection management.
- Health checks.
- Error handling.

### **5.2 Create Event Publisher**

Create the event publishing module.

It must publish:

post.published

Example:

```
{
  "event_id": "event-uuid",
  "event_type": "post.published",
  "post_id": "post-uuid",
  "author_agent_id": "agent-uuid"
}
```

### **5.3 Implement Redis Stream**

Create a dedicated stream for published posts.

### **5.4 Implement Consumer Groups**

Create a consumer group.

Multiple worker processes should be able to consume events safely.

### **5.5 Implement Background Consumer**

Create:

```
backend/app/workers/stream_consumer.py
```

Worker workflow:

```
Read Event
    |
    v
Validate Event
    |
    v
Retrieve Post
    |
    v
Check Idempotency
    |
    v
Execute Routing Service
    |
    v
Store Routing Results
    |
    v
Schedule Notifications
    |
    v
Acknowledge Event
```

### **5.6 Error Recovery**

Implement:

- Pending message recovery.
- Retry counters.
- Duplicate-event protection.
- Failed-event tracking.
- Worker restart handling.

### **5.7 Ensure API Independence**

Post creation must return without waiting for semantic routing and webhook delivery.

## **Testing**

- Publish post.
- Verify event creation.
- Verify worker receives event.
- Verify routing is triggered.
- Stop and restart worker.
- Verify pending event recovery.
- Test duplicate event.

## **Completion Criteria**

Post publishing and downstream processing operate independently.

## **Git Commit**

```
git add .
git commit -m "feat: implement Redis Streams event processing"
git push origin main
```

## **Status Update**

Record:

- Redis connectivity.
- Stream creation.
- Consumer group.
- Worker.
- Event recovery.
- Test results.

# **PHASE 6 – MULTI-STAGE ROUTING ENGINE: STAGE A**

## **Objective**

Implement SQL-based eligibility filtering.

This is the first stage of intelligent relevance routing.

## **Tasks**

### **6.1 Create Routing Module**

Create:

```
backend/app/routing/
    sql_filter.py
```

### **6.2 Implement Eligible Agent Retrieval**

The SQL filter must remove:

- Deactivated agents.
- Publishing agent.
- Blocked agents.
- Excluded industries.
- Agents without valid embeddings.

### **6.3 Implement Blocklist Support**

Create an appropriate data model or relationship to maintain:

- Agent blocklists.
- Domain exclusions.
- Industry exclusions.

### **6.4 Return Candidate Agents**

The service should return only eligible agents.

### **6.5 Track Filtering Statistics**

Record:

- Total agents.
- Deactivated agents removed.
- Publisher excluded.
- Blocked agents removed.
- Industry exclusions.
- Eligible candidates.

## **Testing**

Create sample agents with:

- Active status.
- Inactive status.
- Blocked domains.
- Excluded industries.

Confirm filtering is correct.

## **Completion Criteria**

Stage A dynamically returns eligible agents without hardcoded company relationships.

## **Git Commit**

```
git add .
git commit -m "feat: implement SQL eligibility filtering for agent routing"
git push origin main
```

## **Status Update**

Record:

- SQL filters.
- Blocklist support.
- Exclusion rules.
- Filtering metrics.
- Performance observations.

# **PHASE 7 – MULTI-STAGE ROUTING ENGINE: STAGE B**

## **Objective**

Implement semantic vector retrieval with pgvector.

This is one of the most important implementation phases.

## **Tasks**

### **7.1 Create Vector Search Module**

Create:

```
backend/app/routing/vector_search.py
```

### **7.2 Implement Cosine Similarity**

Compare post embeddings with eligible agent interest embeddings.

Use pgvector's cosine-distance operators.

Convert distance to similarity where appropriate.

### **7.3 Implement HNSW Index**

Create the HNSW vector index using:

vector_cosine_ops

### **7.4 Retrieve Top K Candidates**

Retrieve a maximum of 50 candidates from the eligible agent set.

Candidate results must contain:

- Agent ID.
- Company name.
- Industry.
- Interest manifesto.
- Vector similarity.

### **7.5 Implement Hybrid Retrieval Extension**

The assignment mentions hybrid dense vector and lexical retrieval.

Implement dense retrieval first.

Then add lexical retrieval using PostgreSQL full-text search if time and evaluation requirements allow.

Combine the candidate sets through a documented ranking or fusion strategy.

### **7.6 Integrate With Stage A**

The final process:

```
SQL ELIGIBILITY FILTER
         |
         v
ELIGIBLE AGENTS
         |
         v
POST EMBEDDING
         |
         v
PGVECTOR SEARCH
         |
         v
SORT BY SIMILARITY
         |
         v
TOP 50 AGENTS
```

### **7.7 Performance Measurement**

Measure:

- Query duration.
- Number of eligible agents.
- Number of retrieved candidates.
- Similarity score distribution.

## **Testing**

- Relevant agent ranks highly.
- Irrelevant agent ranks lower.
- Publisher excluded.
- Inactive agent excluded.
- Top K respected.
- HNSW index is used where expected.

Use EXPLAIN ANALYZE to inspect queries.

## **Completion Criteria**

The platform can retrieve semantically relevant agent candidates dynamically.

## **Git Commit**

```
git add .
git commit -m "feat: implement pgvector semantic agent search"
git push origin main
```

## **Status Update**

Record:

- Vector search implementation.
- HNSW configuration.
- Similarity results.
- Candidate count.
- Query performance.

# **PHASE 8 – MULTI-STAGE ROUTING ENGINE: STAGE C**

## **Objective**

Implement high-precision reranking to select the final notification recipients.

## **Tasks**

### **8.1 Create Reranking Service**

Create:

```
backend/app/services/reranking_service.py
backend/app/routing/reranker.py
```

### **8.2 Choose Reranker**

Select one:

- BGE Reranker.
- Cohere Rerank.
- Fast LLM judge.

Choose based on:

- Availability.
- Cost.
- Latency.
- Hardware requirements.
- Accuracy.

### **8.3 Build Reranking Input**

For every candidate, provide:

- Original post title.
- Original post content.
- Company name.
- Industry.
- Interest manifesto.

### **8.4 Generate Final Relevance Score**

Ensure the selected scoring method is calibrated to a comparable [0,1] scale.

### **8.5 Apply Threshold**

The assignment threshold:

0.75

Rules:

```
IF final_score >= 0.75:
    Keep candidate.
ELSE:
    Reject candidate.
```

### **8.6 Apply Recipient Limit**

Maximum recipients:

### **8.7 Implement Routing Orchestration**

Create:

```
backend/app/services/routing_service.py
```

The service must coordinate:

1. SQL filtering.
2. Vector search.
3. Reranking.
4. Recipient selection.
5. Routing log persistence.

### **8.8 Save Rejected and Selected Decisions**

For observability, record enough information to understand why an agent was selected or rejected.

Distinguish candidate retrieval from final notification decisions.

## **Testing**

- Scores above 0.75 accepted.
- Scores below 0.75 rejected.
- At most five agents selected.
- Empty candidate list handled.
- Reranking provider failure handled.
- Duplicate recipients prevented.

## **Completion Criteria**

The complete three-stage routing engine works.

## **Git Commit**

```
git add .
git commit -m "feat: implement three-stage semantic relevance routing"
git push origin main
```

## **Status Update**

Record:

- Reranker used.
- Threshold implementation.
- Recipient limit.
- Routing accuracy observations.
- Latency measurements.
- Known limitations.

# **PHASE 9 – ROUTING LOGS AND NOTIFICATION DELIVERY**

## **Objective**

Persist routing decisions and deliver authenticated notifications to selected agents.

## **Tasks**

### **9.1 Implement Routing Log Repository**

Create:

```
backend/app/repositories/routing_repository.py
```

Save:

- Post ID.
- Target agent ID.
- Vector score.
- Reranking score.
- Routing status.

### **9.2 Implement Notification Service**

Create:

```
backend/app/services/notification_service.py
```

### **9.3 Generate Webhook Payload**

Include:

- Event name.
- Post ID.
- Publisher details.
- Post information.
- Routing metadata appropriate for the recipient.

### **9.4 Implement HMAC Signing**

Create:

```
backend/app/utils/hmac_utils.py
```

Implement:

- Signature generation.
- Signature verification.
- Timestamp validation.
- Replay protection.

### **9.5 Implement HTTP Delivery**

Use HTTPX.

Send asynchronous POST requests.

### **9.6 Implement Delivery Workers**

Create:

```
backend/app/workers/notification_worker.py
```

Process notification tasks independently.

### **9.7 Implement Retry Mechanism**

Add:

- Attempt count.
- Retry delay.
- Exponential backoff.
- Maximum attempts.
- Failed delivery status.

### **9.8 Implement Circuit Breaker**

Repeated failures should temporarily stop calls to persistently failing endpoints.

### **9.9 Implement SSRF Protections**

Validate webhook destinations and block prohibited internal network targets.

## **Testing**

- Valid webhook delivery.
- HMAC verification.
- Invalid signature rejection.
- Timeout.
- Retry.
- Maximum attempts.
- Circuit breaker.
- Delivery history persistence.

## **Completion Criteria**

Selected agents receive authenticated notifications, and all delivery attempts are recorded.

## **Git Commit**

```
git add .
git commit -m "feat: implement signed webhook notification delivery"
git push origin main
```

## **Status Update**

Record:

- Webhook delivery.
- HMAC verification.
- Retry logic.
- Circuit breaker.
- SSRF protections.
- Delivery tests.

# **PHASE 10 – AUTONOMOUS AI AGENT IMPLEMENTATION**

## **Objective**

Build independent simulated company agents that can analyse notifications and decide whether to respond.

## **Tasks**

### **10.1 Create Base Agent**

Create:

```
agents/base_agent.py
```

Define common functionality:

- Agent identity.
- Company information.
- Business interests.
- Capabilities.
- Webhook handling.
- Post analysis.
- Decision generation.
- Response submission.

### **10.2 Create Agent Registry**

Create:

```
agents/agent_registry.py
```

Manage simulated agents.

### **10.3 Create Webhook Receiver**

Create:

```
agents/webhook_receiver.py
```

It must:

- Receive notifications.
- Verify HMAC.
- Validate payload.
- Identify the recipient.
- Forward the event to the agent processing logic.

### **10.4 Create Decision Engine**

Create:

```
agents/decision_engine.py
```

Responsibilities:

- Analyse announcement.
- Retrieve agent capabilities.
- Identify opportunity.
- Evaluate business relevance.
- Determine whether to respond.
- Return structured decisions.

### **10.5 Implement Company-Specific Agents**

Create at least five agents.

1. Swiggy.
2. PhonePe.
3. Paytm.
4. Amazon.
5. Bajaj Auto.

Each must have separate profiles and capabilities.

### **10.6 Agent AI Prompt Design**

Every agent must have a system instruction containing:

- Company identity.
- Business capabilities.
- Business rules.
- Decision-making requirements.
- Response format.
- Security restrictions.

Incoming posts must be supplied separately as untrusted data.

### **10.7 Implement Decision Responses**

Supported decisions:

- INTERESTED.
- NOT_INTERESTED.
- NEEDS_MORE_INFORMATION.
- REQUIRES_HUMAN_APPROVAL.

### **10.8 Prevent Unauthorized Commitments**

Agents must not make binding financial, contractual or operational commitments without appropriate approval.

### **10.9 Implement Comment Submission Client**

Create:

```
agents/comment_publisher.py
```

Submit responses to:

POST /api/v1/posts//comments

### **10.10 Demonstrate Agent Independence**

The same published post must be analysed independently by every recipient agent.

The response must depend on the recipient's individual business capabilities.

## **Testing**

- PhonePe responds to payment partnership.
- Bajaj Auto rejects an irrelevant food promotion.
- Amazon evaluates e-commerce opportunities.
- Agent generates valid structured output.
- Invalid webhook signature is rejected.
- Prompt injection does not override the agent's instructions.

## **Completion Criteria**

The platform can demonstrate an autonomous agent-to-agent interaction.

## **Git Commit**

```
git add .
git commit -m "feat: implement autonomous company agent execution"
git push origin main
```

## **Status Update**

Record:

- Base agent.
- Company agent configurations.
- Agent decision engine.
- Webhook integration.
- Comment publishing.
- Test results.

# **PHASE 11 – COMMENTS AND COMPLETE INTERACTION WORKFLOW**

## **Objective**

Implement the complete response lifecycle between publishing agents and receiving agents.

## **Tasks**

### **11.1 Implement Comment Schemas**

Create comment request and response schemas.

### **11.2 Implement Comment Repository**

Create:

```
backend/app/repositories/comment_repository.py
```

### **11.3 Implement Comment Service**

Create:

```
backend/app/services/comment_service.py
```

### **11.4 Implement Comment API**

POST /api/v1/posts//comments

### **11.5 Implement Comment Retrieval**

GET /api/v1/posts//comments

### **11.6 Update Routing Logs**

When a valid response is received:

Set the associated routing log status to:

ENGAGED

### **11.7 Prevent Duplicate Comments**

Implement idempotency and appropriate duplicate-submission protection.

### **11.8 Verify End-to-End Workflow**

```
SWIGGY
  |
  v
PUBLISH POST
  |
  v
PLATFORM ROUTING
  |
  v
PHONEPE SELECTED
  |
  v
WEBHOOK DELIVERED
  |
  v
PHONEPE ANALYSES POST
  |
  v
PHONEPE DECISION
  |
  v
GENERATE RESPONSE
  |
  v
COMMENTS API
  |
  v
SAVE COMMENT
  |
  v
MARK ENGAGED
```

## **Testing**

- Successful comment.
- Invalid agent.
- Invalid post.
- Duplicate response.
- Unauthorized submission.
- Comment retrieval.
- Routing status update.

## **Completion Criteria**

An agent can publish an announcement and receive a response from another autonomous agent.

## **Git Commit**

```
git add .
git commit -m "feat: implement autonomous comments and interactions"
git push origin main
```

## **Status Update**

Record:

- Comment APIs.
- Validation.
- Database persistence.
- Engagement updates.
- Interaction tests.

# **PHASE 12 – FEEDBACK AND DYNAMIC INTEREST LEARNING**

## **Objective**

Implement the engagement measurement and dynamic preference system.

## **Tasks**

### **12.1 Create Feedback Service**

Create:

```
backend/app/services/feedback_service.py
```

### **12.2 Track Notifications**

Record how many notifications each agent receives.

### **12.3 Track Engagement**

Track:

- Comments received.
- Responses.
- Ignored notifications.
- Failed deliveries.

### **12.4 Calculate Engagement Rate**

Formula:

R = Comments Received / Notifications Sent

Use an appropriate observation window.

Handle zero notifications safely.

### **12.5 Identify Repeatedly Ignored Topics**

Associate engagement outcomes with post embeddings.

Identify patterns across multiple ignored notifications.

### **12.6 Update Dynamic Preference**

Implement a controlled preference-vector update algorithm.

The assignment proposes:

- Positive influence from engagement.
- Negative gradient movement away from repeatedly ignored topics.

Make the update gradual and measurable.

### **12.7 Preserve Original Profile**

Do not overwrite the original agent manifesto.

Maintain:

- Original interest embedding.
- Dynamic preference embedding.
- Profile update history, if required.

### **12.8 Implement Feedback Job**

Run the feedback update through a background worker or scheduled job.

## **Testing**

- Calculate engagement rate.
- Detect repeated ignored topics.
- Verify positive engagement adjustment.
- Verify negative preference adjustment.
- Prevent one ignored notification from causing excessive changes.

## **Completion Criteria**

The platform records engagement and updates agent preferences based on interaction patterns.

## **Git Commit**

```
git add .
git commit -m "feat: implement engagement feedback and dynamic agent preferences"
git push origin main
```

## **Status Update**

Record:

- Engagement tracking.
- Feedback formula.
- Preference updates.
- Background processing.
- Test results.

# **PHASE 13 – SECURITY HARDENING**

## **Objective**

Review the entire application for security vulnerabilities.

Security should be introduced throughout development, but this phase performs a consolidated hardening review.

## **Tasks**

### **13.1 API Authentication**

Validate agent credentials.

### **13.2 Authorization**

Verify resource ownership and permissions.

### **13.3 HMAC Security**

Verify webhook signatures.

### **13.4 Prompt Injection Protection**

Test malicious posts containing instructions designed to manipulate receiving agents.

### **13.5 Input Validation**

Validate:

- URLs.
- Text lengths.
- UUIDs.
- Payload structures.
- Agent identity.
- Comment content.

### **13.6 SSRF Prevention**

Ensure webhook callbacks cannot access:

- Localhost services.
- Private infrastructure.
- Cloud metadata endpoints.
- Other prohibited destinations.

### **13.7 Secret Management**

Check:

- API keys.
- Environment variables.
- Webhook secrets.
- Database credentials.

### **13.8 Rate Limiting**

Protect registration, posting, comment and authentication endpoints.

### **13.9 Audit Logging**

Log important security events without exposing confidential data.

### **13.10 Dependency Review**

Identify vulnerable dependencies and remove unused libraries.

## **Completion Criteria**

The application passes the security tests relevant to the implemented features.

## **Git Commit**

```
git add .
git commit -m "security: harden agent authentication and platform protection"
git push origin main
```

## **Status Update**

Record:

- Authentication.
- Authorization.
- Input protections.
- HMAC.
- SSRF.
- Prompt injection.
- Dependency review.

# **PHASE 14 – FRONTEND DASHBOARD**

## **Objective**

Develop an administrative demonstration interface for the completed backend.

The frontend is a supporting presentation layer, not a replacement for the routing engine.

## **Technology**

- React.
- Vite.
- Tailwind CSS.
- Axios or Fetch API.

## **Tasks**

### **14.1 Project Setup**

Create the frontend application.

Configure:

- API base URL.
- Environment settings.
- Routing.
- Shared API client.
- Common components.

### **14.2 Dashboard Page**

Display:

- Total agents.
- Active agents.
- Total posts.
- Total notifications.
- Total comments.
- Engagement rate.
- Delivery status.

### **14.3 Agent Management Page**

Implement:

- Agent list.
- Registration form.
- Agent profile.
- Edit functionality.
- Activate/deactivate.
- Interest manifesto display.

### **14.4 Post Feed Page**

Implement:

- Post list.
- Post details.
- Company identity.
- Comments.
- Processing status.

### **14.5 Publish Post Page**

Create a form for an authenticated agent to publish a post.

### **14.6 Routing Analytics Page**

Display:

- Candidate agents.
- Vector similarity scores.
- Reranking scores.
- Selected recipients.
- Rejected candidates.
- Delivery status.

### **14.7 Interaction Details**

Show:

- Agent receiving the notification.
- Decision status.
- Concise decision explanation.
- Generated comment.
- Engagement status.

### **14.8 Error and Loading States**

Implement:

- Loading indicators.
- Empty states.
- Validation errors.
- API failure messages.
- Responsive layout.

## **Completion Criteria**

The backend functionality can be demonstrated through a functional dashboard.

## **Git Commit**

```
git add .
git commit -m "feat: implement Asama AI administrative dashboard"
git push origin main
```

## **Status Update**

Record:

- React setup.
- Pages.
- API integrations.
- UI tests.
- Screenshots if needed.

# **PHASE 15 – END-TO-END TESTING AND PERFORMANCE VALIDATION**

## **Objective**

Verify that all implemented modules operate together reliably.

## **Tasks**

### **15.1 Full Registration Workflow**

Register all simulated company agents.

### **15.2 Full Post Workflow**

Publish announcements from different agents.

### **15.3 Routing Validation**

Verify all three routing stages.

### **15.4 Webhook Validation**

Verify authenticated notification delivery.

### **15.5 Autonomous Agent Validation**

Verify independent decision-making.

### **15.6 Comments Validation**

Verify responses are saved under correct posts.

### **15.7 Feedback Validation**

Verify the engagement data is updated correctly.

### **15.8 Performance Testing**

Measure:

- SQL filter duration.
- Embedding generation duration.
- Vector retrieval duration.
- Reranking duration.
- Total routing duration.
- Webhook delivery duration.
- API latency.

### **15.9 Scalability Testing**

Start with a small dataset.

Gradually increase the number of registered agents.

Suggested test datasets:

- 10 agents.
- 100 agents.
- 1,000 agents.
- 10,000 agents, if infrastructure permits.

Measure actual performance rather than assuming scaling targets have been met.

### **15.10 Regression Testing**

Run all existing tests.

Ensure new features have not broken previous functionality.

## **Completion Criteria**

The complete application passes its defined integration and regression tests.

## **Git Commit**

```
git add .
git commit -m "test: complete end-to-end and performance validation"
git push origin main
```

## **Status Update**

Record:

- Integration test results.
- Performance results.
- Routing quality.
- Known failures.
- Remaining limitations.

# **PHASE 16 – DOCKERIZATION AND DEPLOYMENT**

## **Objective**

Make the project reproducible and easy to run.

## **Tasks**

### **16.1 Backend Dockerfile**

Create a production-oriented backend Dockerfile.

### **16.2 Frontend Dockerfile**

Create a frontend Dockerfile if the dashboard is implemented.

### **16.3 Docker Compose**

Configure services:

- Backend.
- PostgreSQL with pgvector.
- Redis.
- Routing worker.
- Notification worker.
- Simulated agent services.
- Frontend.

Ensure appropriate startup dependencies and health checks.

### **16.4 Environment Configuration**

Provide:

.env.example

Document every required variable.

### **16.5 Persistence**

Configure database volumes.

Configure Redis persistence if required.

### **16.6 Startup**

The application should be startable through:

```
docker compose up --build
```

### **16.7 Database Initialization**

Ensure extensions and migrations run in the correct order.

### **16.8 Deployment Verification**

Test:

- Fresh installation.
- Container restart.
- Database persistence.
- Redis recovery.
- Worker startup.
- Full post workflow.

## **Completion Criteria**

The project runs successfully through Docker Compose.

## **Git Commit**

```
git add .
git commit -m "chore: dockerize Asama AI application"
git push origin main
```

## **Status Update**

Record:

- Dockerfiles.
- Compose configuration.
- Database initialization.
- Container health.
- Deployment tests.

# **PHASE 17 – DOCUMENTATION AND FINAL DELIVERY**

## **Objective**

Prepare a professional, reproducible project submission and demonstration.

## **Tasks**

### **17.1 Complete README.md**

Include:

- Project introduction.
- Architecture.
- Features.
- Technology stack.
- Prerequisites.
- Environment setup.
- Installation.
- Database setup.
- Running locally.
- Running using Docker.
- API documentation.
- Testing.
- Demonstration instructions.

### **17.2 Complete API Documentation**

Use FastAPI OpenAPI documentation.

Verify:

- Request bodies.
- Response models.
- Authentication information.
- Error responses.

### **17.3 Prepare Seed Data**

Include sample agents.

Include sample posts.

Include a repeatable demonstration dataset.

### **17.4 Prepare Final Demonstration**

Demonstrate:

1. Agent registration.
2. Interest embedding generation.
3. Post creation.
4. Redis event.
5. SQL filtering.
6. Vector matching.
7. Reranking.
8. Selected recipients.
9. Signed notification delivery.
10. Autonomous agent analysis.
11. Comment submission.
12. Feedback update.

### **17.5 Final Git Review**

Check:

- All phases have commits.
- No secrets committed.
- No unnecessary files.
- Tests pass.
- README is accurate.
- Working tree is clean.

### **17.6 Final Status Update**

Mark the project as completed only after all required acceptance criteria are met.

## **Git Commit**

```
git add .
git commit -m "docs: finalize Asama AI project documentation and submission"
git push origin main
```

## **Completion Criteria**

The repository is ready for evaluation and the complete application can be reproduced and demonstrated.

# **4. GLOBAL GIT AND STATUS MANAGEMENT RULES**

These rules apply to every phase.

## **4.1 Mandatory Git Workflow**

At the beginning of a phase:

```
git status
```

Ensure there are no accidental changes from previous phases.

During development:

- Write code.
- Run tests.
- Review changes.
- Fix errors.
- Verify existing functionality.

At successful phase completion:

```
git add .
git commit -m "feat: meaningful phase description"
git push origin main
```

Do not use a generic commit message for every phase.

Suggested commit prefixes:

- feat: New functionality.
- fix: Bug correction.
- refactor: Code restructuring.
- test: Testing changes.
- docs: Documentation.
- chore: Build or configuration changes.
- security: Security improvements.

If a phase fails verification:

1. Do not mark it completed.
2. Do not create a completion commit.
3. Record the failure in status.md.
4. Correct the implementation.
5. Re-run the tests.

If work needs to be saved before completion, create an explicitly named work-in-progress commit rather than claiming the phase is complete.

## **4.2 Mandatory status.md Update**

After every completed phase, update status.md.

The update must include:

- Current phase.
- Phase completion status.
- Completed functionality.
- Files created or modified.
- Database changes.
- APIs implemented.
- Tests performed.
- Test results.
- Git commit ID.
- Git push status.
- Current known issues.
- Remaining work.
- Next phase.

Maintain historical phase records.

Do not erase the history of previously completed phases.

## **4.3 Status Accuracy**

Use these status labels:

NOT_STARTED\
IN_PROGRESS\
BLOCKED\
COMPLETED\
PARTIALLY_COMPLETED

Never mark a feature completed without implementation and verification.

## **4.4 Git Commit Verification**

After committing:

```
git log -5 --oneline
```

Verify that the commit exists.

After pushing:

```
git status
```

Verify the working tree.

If the push fails, record that status accurately and resolve the problem.

