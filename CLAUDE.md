# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Property portfolio management platform with document ingestion, feature extraction, and analytics dashboards. Uses Bronze → Silver → Gold medallion data architecture.
**Stack:** React 18 + TypeScript + Vite | FastAPI + asyncpg | PostgreSQL (PostGIS) | AWS CDK

## Python Environment

Use the venv in the project root:
```bash
./venv/bin/python
./venv/bin/pytest
```

For local development with Python 3.13:
```bash
./venv_local/bin/python
./venv_local/bin/uvicorn
```

## Common Commands

### Backend

```bash
# Start backend (requires Docker services running)
DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_PASSWORD=postgres DB_NAME=platform_dev \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
S3_ENDPOINT_URL=http://localhost:4566 S3_BUCKET_NAME=platform-bronze \
DEV_MODE=true ./venv/bin/uvicorn backend.main:app --reload --port 8000

# Run all tests
./venv/bin/pytest tests/ -v

# Run single test file
./venv/bin/pytest tests/test_silver_processor.py -v

# Run specific test
./venv/bin/pytest tests/test_silver_processor.py::TestParseS3KeyForMetadata -v
```
API docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev                    # Dev server on port 3000
npm test                       # Run tests once
npm run test:watch             # Watch mode
npm run build                  # Production build
npm run lint                   # ESLint
npm run dev -- --host 127.0.0.1 --port 3000
```

### Docker Services (Postgres + LocalStack)
```bash
docker compose up -d           # Start services
docker compose down            # Stop services

# Apply migrations (run in order)
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001a_bronze_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001b_silver_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001c_gold_layer.sql
# ... continue with 002-011

# Create S3 bucket
docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze

# Seed test data
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/seeds/week3_seed.sql
```

### Testing
```bash
pytest tests/                           # All tests
pytest tests/test_file_type_detector.py -v  # Single file
pytest tests/geo/                       # Geographic tests
```

### AWS CDK

```bash
cd infrastructure/aws/cdk
source .venv/bin/activate
cdk synth                      # Synthesize CloudFormation
cdk diff                       # Show pending changes
cdk deploy PlatformNetworkingDev  # Deploy specific stack
```

## Architecture

### Data Flow

```
Upload (CSV/Excel/PDF) → S3 Bronze bucket
    ↓ EventBridge
    ↓ Step Functions
    ├─ Step 1: PDF extraction → features.json
    └─ Step 2: Silver processor → PostgreSQL
```

### Database Schemas

- **public**: Reference tables (`housing_associations`, `upload_audit`, `processing_audit`)
- **silver**: Entity/feature tables (`document_features`, `fraew_features`, `fra_features`, `scr_features`, `properties`, `portfolios`)
- **gold**: Analytics views (`portfolio_summary_v1`, `portfolio_readiness_v1`, etc.)

### Backend Structure

- `backend/main.py` - FastAPI app entry, lifespan manages DatabasePool
- `backend/api/ingestion/` - Upload endpoints
- `backend/api/v1/` - Portfolio/lineage routers (query gold views)
- `backend/workers/silver_processor.py` - S3 → Silver layer processing
- `backend/core/database/db_pool.py` - asyncpg connection pool singleton

### Frontend Structure

- `frontend/src/pages/` - IngestionLandingPage, PortfolioOverviewPage
- `frontend/src/services/apiClient.ts` - API communication layer
- `frontend/src/components/` - Shared UI components

### AWS CDK Stacks (infrastructure/aws/cdk/)

Deploy in order: Networking → Security → Data → Ingestion → Compute → Observability

## Key Patterns

### SQL Queries Use Schema Prefix

Silver layer tables are in `silver` schema:
```python
await conn.execute("INSERT INTO silver.document_features ...")
await conn.fetchrow("SELECT * FROM silver.fraew_features WHERE ...")
```

Gold views are in `gold` schema:
```python
await conn.fetch("SELECT * FROM gold.portfolio_summary_v1 WHERE ...")
```

### Tenant Isolation

All queries should be scoped by `ha_id`. In DEV_MODE, tenant scoping is relaxed.

### Database Connection

Use `DatabasePool` for connection management:
```python
async with DatabasePool.acquire() as conn:
    result = await conn.fetch(query, *params)
```

### S3 Partitioning

```
ha_id=<tenant>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<uuid>/
```

## Environment Variables

Backend requires:
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- `S3_ENDPOINT_URL` (LocalStack: `http://localhost:4566`)
- `S3_BUCKET_NAME` (`platform-bronze`)
- `DEV_MODE=true` (bypasses auth, relaxes tenant scoping)

Frontend:
- `VITE_API_BASE_URL` (default: same origin, for local: `http://localhost:8000`)

## Testing

Backend tests use moto for S3 mocking. Database tests require running Postgres.

Frontend tests use Vitest + @testing-library/react with jsdom.


## Code Standards

From `.cursor/rules.md`:
- Python: Type hints everywhere, thin routes, business logic in services
- TypeScript: Strict mode, functional components only, API calls in services layer
- SQL: Parameterized queries, explicit column selection, snake_case naming
- AWS CDK: All resources via CDK, use cdk-nag for security validation

## Key Files
- `backend/api/ingestion/file_type_detector.py` - Auto-detects CSV/Excel/PDF file types
- `backend/core/pdf_extraction/pdf_pipeline.py` - PDF processing pipeline
- `backend/geo/confidence.py` - UPRN matching confidence scoring
- `database/migrations/` - Schema migrations (apply in numerical order)
- `.cursor/rules.md` - Detailed coding standards (409 lines)
