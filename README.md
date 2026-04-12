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

---

## Frontend–Backend Wireframing Progress and Setup Guide

This section documents the wireframing and integration work completed so far to connect the frontend dashboard flow to the backend ingestion pipeline, along with the environment setup and run steps needed for local development. It also records what is currently working, what was fixed during the latest integration pass, and what still remains to be completed.

### Purpose of this wireframing phase

The goal of this phase has been to move the frontend away from a mostly mock/local parsing flow and align it with the real backend ingestion and enrichment flow already present in the repository.

The intended user flow is now:

1. Start from the unchanged landing page.
2. Navigate to the upload page.
3. Upload a SoV file through the real backend ingestion endpoint.
4. Normalize the backend response into frontend-friendly property objects.
5. Feed those normalized rows into the portfolio dashboard.
6. Group properties into blocks for block-level mapping and analysis.
7. Show selected block/property details in the dashboard panel.
8. Prepare the UI structure for later enrichment, risk, PDF ingestion, and export workflows.

---

## What has been done so far

### 1. Frontend routing and page flow were reworked

The frontend flow now preserves the original landing page and overall navigation flow, but the application after the landing page has been remodeled to better reflect the backend functionality.

Completed changes include:

- the landing page remains unchanged
- the upload page has been restyled to match the ingestion-style visual reference
- the dashboard page now acts as the main portfolio overview page
- the upload page now leads directly into the backend-driven portfolio dashboard
- the sidebar structure now reflects the actual backend-oriented workflow:
  - Upload SoV
  - Portfolio Overview
  - placeholder areas for Evidence Summary, Block Analysis, and Documents

### 2. The upload page is now backend-connected

Previously, frontend ingestion utilities were doing more local work. This phase changed that so the upload page uses the backend ingestion API.

Current frontend upload behavior:

- builds a `FormData` object
- sends the file to:

  `/api/v1/upload/ingest?document_type=sov`

- waits for the backend JSON response
- validates the response structure
- normalizes backend rows into the frontend property model
- stores the result in application state
- redirects into the dashboard view

This means the frontend is now consuming backend-produced rows instead of relying only on local spreadsheet parsing logic.

### 3. Backend ingestion response handling was aligned to the UI

The frontend was updated to normalize the backend response structure into one consistent shape. This includes mapping fields such as:

- `property_id`
- `property_reference`
- `address_line_1`
- `address_line_2`
- `address_3`
- `post_code`
- `uprn`
- `parent_uprn`
- `block_reference`
- `latitude`
- `longitude`
- `x_coordinate`
- `y_coordinate`
- `sum_insured`
- `property_type`
- `occupancy_type`
- `height_m`
- `storeys`
- `units`
- `year_of_build`
- `wall_construction`
- `roof_construction`
- `readiness_score`
- `readiness_band`
- `missing_fields`

This normalization step was necessary because the frontend dashboard components need predictable field names even when backend rows include mixed naming styles.

### 4. Portfolio dashboard wireframing was rebuilt around backend data

The dashboard page was remodeled to match actual backend functionality rather than generic placeholder UI.

Completed dashboard sections now include:

- portfolio underwriting snapshot banner
- KPI cards for:
  - total insured value
  - number of detected blocks
  - UPRN coverage
  - mappable locations
- confidence and completeness bars
- block analysis map
- selected property/details panel
- block grouping table
- property schedule table
- document/export panel placeholders

This gives the frontend a backend-shaped dashboard even before all enrichment and export functionality is complete.

### 5. Property grouping into blocks was added in the dashboard layer

A grouping pass was added on the frontend so the portfolio rows can be clustered into blocks using:

- `block_reference`
- `parent_uprn`
- `uprn`
- `property_reference`
- fallback `id`

This grouped structure is used to:

- create block-level summary rows
- calculate block-level total value
- calculate block-level average readiness
- estimate block-level height
- create block table entries
- feed the map with grouped block data

### 6. The map component was remodeled for block/property analysis

The `PortfolioMap` component was rewritten to support both:

- property mode
- block mode

It now:
- accepts normalized properties
- accepts grouped blocks
- derives coordinates robustly from multiple possible field names
- ignores invalid `0,0` or missing coordinates
- renders Leaflet markers dynamically
- handles selection callbacks for map interaction
- supports fly-to behavior when selecting a block or property
- supports block popups/tooltips and property popups/tooltips

This is the core wireframing layer for geo packaging and block analysis behavior.

### 7. The property details panel was rebuilt for compatibility with backend fields

`PropertyDetails.jsx` was rewritten to accept normalized property rows and render:

- address
- city/postcode
- UPRN
- parent UPRN
- block reference
- UPRN match score
- readiness band/score
- missing fields
- SoV values
- raw backend fields
- placeholder UPRN confidence results when available

This panel is designed to work with both the current SoV ingestion output and later enrichment output.

### 8. Frontend utility files were updated to support the new flow

Updated utility files include:

- `ingestion.js`
- `uprn.js`
- `readiness.js`
- `leaflet.js`

These now better support:
- backend response normalization
- readiness calculations
- UPRN-related UI compatibility
- Leaflet marker behavior

### 9. App-level state management was updated

`App.jsx` was rewired so that it now handles:

- landing page visibility
- upload page vs overview page navigation
- upload progress state
- upload error state
- pipeline step display
- storage of the backend ingestion result
- computation of the ingestion summary
- handoff of backend-normalized data into the dashboard page

This is what ties the upload page and dashboard page together.

### 10. Local development triage was done

A number of first-run issues were found and fixed during this integration pass, including:

- bad CSS import path from `main.jsx`
- running `npm run dev` in the wrong folder
- missing/incorrect frontend `.env`
- frontend/backend API base URL mismatch
- upload failures due to backend response handling
- selection and map-display mismatches between blocks and properties
- backend enrichment side effects causing noise in local development logs
- block map centering problems from invalid coordinates such as `0,0`

---

## Backend files most involved in this phase

The main backend areas involved in this frontend–backend wireframing pass are:

### Upload and ingestion
- `backend/api/ingestion/upload_router.py`
- `backend/api/ingestion/file_type_detector.py`
- `backend/api/ingestion/upload_models.py`
- `backend/api/ingestion/upload_validator.py`

### SoV processing
- `backend/workers/sov_processor_v2.py`
- `backend/workers/sov_processor.py`

### Enrichment and geo support
- `backend/workers/enrichment_worker.py`
- `backend/geo/uprn_maps/*`

### Core data and storage support
- `backend/core/database/db_pool.py`
- `infrastructure/storage/upload_service.py`

These are the main backend components currently shaping the frontend wireframe behavior.

---

## Frontend files most involved in this phase

### Application flow
- `frontend/src/App.jsx`
- `frontend/src/main.jsx`

### Pages
- `frontend/src/pages/IngestionPage.jsx`
- `frontend/src/pages/PortfolioDashboard.jsx`

### Components
- `frontend/src/components/PortfolioMap.jsx`
- `frontend/src/components/PropertyDetails.jsx`
- `frontend/src/components/RawFieldsTable.jsx`

### Utilities
- `frontend/src/utils/ingestion.js`
- `frontend/src/utils/uprn.js`
- `frontend/src/utils/readiness.js`
- `frontend/src/utils/leaflet.js`

### Styling
- `frontend/src/styles/global.css`

---

## Local setup and run guide

This section gives the current step-by-step local setup flow for running the platform during this wireframing phase.

### 1. Clone the repository

```bash
git clone <repo-url>
cd Platform-dev

### 2. Create and activate the Python virtual environment

From the project root:

```bash
python3 -m venv venv
source venv/bin/activate

Install backend dependencies:

pip install -r requirements.txt

### 3. Install frontend dependencies

Move into the frontend folder:
cd frontend
npm install

Then return to the project root when needed:
cd ..

### 4. Set up the frontend environment file

Inside frontend/.env, set:
VITE_API_BASE_URL=http://127.0.0.1:8000

This is required so the frontend can call the FastAPI backend.

### 5. Start required Docker services

From the project root:
docker compose up

To run in the background:
docker compose up -d

To check running containers:
docker ps

To stop services:
docker compose down

### 6. Start the backend server

From the project root:
source venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000

Health check:
curl http://127.0.0.1:8000/health

### 7. Start the frontend dev server

In a new terminal:
cd frontend
npm run dev

The app will typically run at:
http://localhost:5173

### 8. Open the platform

Open in your browser:
http://localhost:5173

Expected flow:
	•	Landing page loads
	•	Click Get Started
	•	Upload page appears
	•	Upload SoV file
	•	Dashboard renders with backend data

Git workflow for this wireframing phase

Create a new branch:
git checkout -b frontend-backend-wireframing

Stage all changes:
git add .

Commit changes:
git commit -m "frontend-backend wiring: dashboard, map, ingestion, property details, async upload flow"

Push branch to remote:
git push -u origin frontend-backend-wireframing

### Recommended terminal workflow

Use three terminals for smooth development.

Terminal 1 — Docker:
docker compose up

Terminal 2 — Backend:
source venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000

Terminal 3 — Frontend:
cd frontend
npm run dev

What is currently working

Frontend
	•	Landing page unchanged
	•	Upload page connected to backend
	•	Upload request successfully hits backend
	•	Backend response is normalized into frontend state
	•	Portfolio dashboard renders from backend data
	•	Block grouping logic implemented
	•	Property schedule table renders
	•	Property details panel renders
	•	Map structure supports block/property modes

⸻

Backend
	•	SoV upload endpoint is functional
	•	SoV processing writes to database (silver.properties)
	•	Async upload handling is in place (with ongoing fixes)
	•	Enrichment worker exists and is partially integrated
	•	Block detection logic is present

⸻

What still needs to be done

1. Block properties on the map
	•	Ensure correct block centroid calculation
	•	Fix block vs property selection consistency
	•	Ensure details panel updates correctly on click
	•	Allow drill-down from block → properties

⸻

2. Accurate portfolio risk/readiness
	•	Confirm backend as source of truth
	•	Separate readiness vs risk clearly
	•	Replace placeholder/inferred values with backend-calculated metrics
	•	Add proper portfolio-level aggregation

⸻

3. PDF upload (FRA / FRAEW)
	•	Support PDF ingestion from frontend
	•	Improve error handling for extraction failures
	•	Display extracted fire risk data in UI
	•	Link documents to blocks/properties

⸻

4. Doc A / Doc B export
	•	Connect frontend buttons to backend exporters
	•	Generate documents from SoV + fire risk data
	•	Add loading + success states
	•	Enable file download

⸻

5. Evidence Summary & Block Analysis pages
	•	Replace placeholders with real data views
	•	Show per-block evidence and risk insights
	•	Link uploaded documents to analysis

⸻

Known issues
	•	Bedrock / LLM errors without credentials
	•	External API limits (e.g. OS Places)
	•	Some enrichment not fully wired
	•	Map interactions still being refined
	•	Export buttons not yet connected
	•	Some metrics still inferred instead of backend-driven

⸻

Recommended next steps
	1.	Finalize block selection behavior on map
	2.	Lock backend readiness/risk as source of truth
	3.	Stabilize async ingestion responses
	4.	Add PDF ingestion support
	5.	Wire document export (Doc A / Doc B)
	6.	Complete Evidence + Block Analysis pages

⸻

Summary

The platform is now transitioning from a mock UI into a backend-driven system:
	•	uploads are real
	•	data is backend-derived
	•	dashboard is data-driven
	•	map supports block-level analysis
	•	architecture supports enrichment and document workflows

Remaining work focuses on correctness, enrichment, document handling, and export functionality rather than UI structure.
