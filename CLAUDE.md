# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Property portfolio management and ingestion platform using **React (Vite) + FastAPI + PostgreSQL** with AWS S3 integration. Implements a **medallion architecture** (Bronze/Silver/Gold layers) for data processing.

## Development Commands

### Docker Services (Postgres + LocalStack S3)
```bash
docker compose up -d
```

### Database Setup
```bash
# Apply migrations in order
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_bronze_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/002_async_processing_retries.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_silver_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/003_silver_document_features.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_gold_layer.sql

# Create S3 bucket
docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze

# Seed test data
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/seeds/week3_seed.sql
```

### Backend
```bash
# Setup virtual environment (Python 3.13)
python3 -m venv venv_local
./venv_local/bin/pip install -r requirements.local.txt

# Run API
DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_PASSWORD=postgres DB_NAME=platform_dev \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
S3_ENDPOINT_URL=http://localhost:4566 S3_BUCKET_NAME=platform-bronze \
DEV_MODE=true DEV_HA_ID=ha_demo \
./venv_local/bin/uvicorn backend.main:app --reload --port 8000
```
API docs: http://127.0.0.1:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

### Testing
```bash
pytest tests/                           # All tests
pytest tests/test_file_type_detector.py -v  # Single file
pytest tests/geo/                       # Geographic tests
```

### Linting
- Python: `ruff`, `black`, `mypy`
- Frontend: `eslint`

## Architecture

### Medallion Data Flow
- **Bronze Layer**: Raw file ingestion to S3 + audit tables
- **Silver Layer**: Data standardization and feature extraction
- **Gold Layer**: Aggregated views for dashboards

### Backend Structure (`backend/`)
- `main.py` - FastAPI entry point with 4 routers: upload, lineage, portfolios, geo
- `api/ingestion/` - File upload with auto-detection (property schedules, EPC, FRA/FRAEW/SCR PDFs)
- `api/v1/` - Portfolio and lineage endpoints
- `core/audit/` - Upload audit logging and lineage tracking
- `core/database/db_pool.py` - AsyncPG connection pooling (5-20 connections)
- `core/tenancy/` - Multi-tenant isolation via JWT (ha_id extraction)
- `core/pdf_extraction/` - PDF text and feature extraction pipeline
- `geo/` - UPRN/postcode confidence scoring
- `workers/` - Silver layer processor, Step Functions worker

### Frontend Structure (`frontend/`)
- React 18 + TypeScript + Vite
- `src/pages/` - IngestionLandingPage (upload), LandingPage (dashboard)
- `src/services/apiClient.ts` - Centralized API client

### S3 Partitioning
```
ha_id=<id>/bronze/dataset=<type>/ingest_date=<date>/submission_id=<uuid>/file=<name>
```
Sidecars: `manifest.json`, `metadata.json`, `extraction.json`, `features.json`, `interpretation.json`

## Code Patterns

### Python/Backend
- Python 3.11+, strict PEP 8, type hints everywhere
- Thin routes → business logic in services → DB logic in repositories
- All database operations use asyncpg with async/await (no blocking calls)
- Error format: `{"error": "type", "message": "...", "details": {}}`
- Dependency injection via FastAPI `Depends()`

### Frontend/React
- TypeScript only, functional components only
- Single API client abstraction (no direct fetch in components)
- Server state via React Query/TanStack Query

### Database
- PostgreSQL with PostGIS, snake_case naming, plural table names
- Parameterized queries only, explicit transactions
- Raw SQL migrations in `database/migrations/`

### Multi-Tenancy
- All endpoints require ha_id from JWT token
- DEV_MODE=true allows fallback to DEV_HA_ID for local development

## Key Files

- `backend/api/ingestion/file_type_detector.py` - Auto-detects CSV/Excel/PDF file types
- `backend/core/pdf_extraction/pdf_pipeline.py` - PDF processing pipeline
- `backend/geo/confidence.py` - UPRN matching confidence scoring
- `database/migrations/` - Schema migrations (apply in numerical order)
- `.cursor/rules.md` - Detailed coding standards (409 lines)
