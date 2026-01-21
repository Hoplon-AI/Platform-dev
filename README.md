# Platform-dev

Full-stack property portfolio management and ingestion platform built with **React (Vite) + FastAPI + Postgres**.

## Overview

This project is a web-based platform for property portfolio management, ingestion, and analytics.
Current focus is **Week 1–3** groundwork:
- Bronze ingestion to S3 (LocalStack for local dev)
- Postgres-backed Silver/Gold schemas and Gold views for dashboards
- A small Week 3 UI: **Ingestion** page + **PortfolioOverview** dashboard

## Project Structure

```
Platform-dev/
├── backend/                    # FastAPI API (ingestion + portfolios + lineage)
├── frontend/                   # Vite + React + TypeScript UI
├── database/
│   ├── migrations/             # Bronze/Silver/Gold SQL
│   └── seeds/                  # Local seed data
├── infrastructure/storage/      # S3 keying + upload service
├── docs/                        # Roadmap + local dev guide
└── docker-compose.yml           # Postgres 16.9 + LocalStack (S3)
```

## Technology Stack

### Frontend
- **React** + **TypeScript**
- **Vite** (dev/build tooling)
- **React Router**

### Backend
- **FastAPI**
- **asyncpg** (Postgres)
- **boto3** (S3)

## Features

### Current Features
- **Ingestion landing page** (`/`): list submissions + batch upload (auto-detect file type)
- **PortfolioOverview dashboard** (`/portfolio`): summary, readiness, risk distribution, recent activity

## Local development (recommended)

Use the step-by-step guide in:
- `docs/LOCAL_DEV.md`

Quickstart (Option B: real DB + LocalStack):

```bash
docker compose up -d
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_bronze_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/002_async_processing_retries.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_silver_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_gold_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/seeds/week3_seed.sql
docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze
```

### Backend

This repo supports a local runtime venv for Python 3.13:

```bash
python3 -m venv venv_local
./venv_local/bin/pip install -r requirements.local.txt

DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_PASSWORD=postgres DB_NAME=platform_dev \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
S3_ENDPOINT_URL=http://localhost:4566 S3_BUCKET_NAME=platform-bronze \
DEV_MODE=true DEV_HA_ID=ha_demo \
./venv_local/bin/uvicorn backend.main:app --reload --port 8000
```

API docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

UI:
- Ingestion: `http://127.0.0.1:3000/`
- PortfolioOverview: `http://127.0.0.1:3000/portfolio`

## S3 partitioning (Bronze)

Uploads are stored using lake-style partitioning and submission sidecars:

```
ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<upload_id>/file=<filename>
ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<upload_id>/manifest.json
ha_id=<ha_id>/bronze/dataset=<file_type>/ingest_date=YYYY-MM-DD/submission_id=<upload_id>/metadata.json
```

## API Endpoints

### Backend API (FastAPI)

- Ingestion:
  - `POST /api/v1/upload/batch` (multi-file upload + type detection)
  - `GET /api/v1/upload/submissions` (recent submissions)
  - `GET /api/v1/upload/{upload_id}/status` (single submission)
- Portfolios (Gold-backed):
  - `GET /api/v1/portfolios`
  - `GET /api/v1/portfolios/{portfolio_id}/summary`
  - `GET /api/v1/portfolios/{portfolio_id}/readiness`
  - `GET /api/v1/portfolios/{portfolio_id}/risk-distribution`
  - `GET /api/v1/portfolios/{portfolio_id}/recent-activity`

## Data Schemas

The project uses JSON schemas to define core data structures:

- **[Property Schema](schemas/property-schema.json)** - Complete property data structure with all fields including insurance, risk, and high-value property details
- **[Standardized Property Schema](schemas/standardized-property-schema.json)** - Property data after column standardization (based on preprocessing column mapping)
- **[CSV Upload Response Schema](schemas/csv-upload-response-schema.json)** - API response structure for CSV upload endpoint
- **[Auto-Detection Result Schema](schemas/auto-detection-result-schema.json)** - Structure of auto-detection results from the data type detection system

These schemas can be used for:
- API validation
- Data transformation pipelines
- Frontend type definitions
- Documentation and testing

## Data Processing

The backend includes utilities for:
- **Column Standardization** - Automatically standardize CSV column names
- **Data Preprocessing** - Clean and prepare data for analysis
- **Auto-Detection** - Automatically detect data patterns and types (see [Auto-Detection Documentation](docs/auto-detection.md))
- **Geographic Processing** - Handle postcode and location data

## Roadmap

See:
- `docs/mvp-3month-roadmap.md`
- `docs/AWS_ASYNC_INGESTION.md` (AWS-first async ingestion: S3 → Step Functions)
