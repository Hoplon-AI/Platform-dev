# Platform-dev

Full-stack property portfolio management, ingestion, enrichment, and underwriting analytics platform built with **React (Vite) + FastAPI + PostgreSQL**.

---

# Overview

Platform-dev is a backend-driven portfolio intelligence platform focused on:

* Property schedule ingestion (SoV / stock schedules)
* Block and property hierarchy modelling
* UPRN enrichment and matching
* FRA / FRAEW document ingestion
* Underwriting analytics
* Readiness and risk scoring
* Block-level mapping and portfolio visualization
* Document evidence aggregation
* Export generation workflows (Doc A / Doc B)

The platform architecture is organized around a lakehouse-style ingestion model:

* **Bronze**: raw uploads and source lineage
* **Silver**: normalized and enriched entities
* **Gold**: dashboard and underwriting analytics views

The current branch, `frontend-backend-wireframing`, represents the transition from mostly mock frontend flows and isolated ingestion prototypes into a fully wired frontend/backend integration layer, backend-driven dashboard rendering, block-aware portfolio analytics, and document-oriented risk workflows.

---

# Current Development Focus

The current development phase focuses on:

* Frontend/backend ingestion wiring
* SoV ingestion stabilization
* Block/property hierarchy modelling
* UPRN enrichment consistency
* FRA/FRAEW extraction and dashboard integration
* Map-based underwriting analysis
* Dashboard aggregation correctness
* Async ingestion orchestration
* Evidence summary and document analysis flows
* Geo/polygon support for UK-wide expansion
* Fire evidence visualization and colour banding consistency

---

# Repository Structure

```text
Platform-dev/
├── backend/                        # FastAPI backend
│   ├── api/
│   ├── workers/
│   ├── geo/
│   ├── enrichment/
│   └── core/
│
├── frontend/                       # React + Vite frontend
│   ├── src/
│   ├── public/
│   └── package.json
│
├── database/
│   ├── migrations/
│   ├── seeds/
│   └── views/
│
├── infrastructure/
│   └── storage/
│
├── schemas/                        # JSON schemas
├── docs/                           # Architecture + roadmap docs
├── scripts/
├── test-files/                     # Recommended SoV/FRA/FRAEW test uploads
└── docker-compose.yml
```

---

# Technology Stack

## Frontend

* React
* Vite
* TypeScript / JavaScript
* React Router
* Leaflet
* PapaParse

## Backend

* FastAPI
* asyncpg
* boto3
* PostgreSQL
* LocalStack
* Pydantic
* Bedrock integration (optional for local work)

## Infrastructure

* Docker
* Docker Compose
* S3-style storage
* LocalStack S3 emulation

---

# Frontend–Backend Wireframing Progress Report

This section summarizes the major integration and wireframing work completed during the current development cycle.

---

## 1. Frontend Application Flow Rework

The frontend application structure was remodeled to align with the backend ingestion and analytics pipeline.

### Preserved

* Original landing page
* Original app entry flow

### Added/Reworked

* Ingestion-style upload page
* Backend-connected upload workflow
* Backend-driven dashboard flow
* Underwriting-style dashboard layout
* Sidebar/dashboard navigation structure
* Block analysis layout structure
* Evidence summary placeholders
* Document workflow placeholders

### Current frontend flow

```text
Landing Page
    ↓
Upload SoV / Document
    ↓
Backend ingestion pipeline
    ↓
Frontend normalization layer
    ↓
Portfolio dashboard
    ↓
Block analysis / Evidence workflows
```

---

## 2. Backend-Connected Upload Pipeline

The frontend upload flow was reworked so uploads now hit the real backend ingestion APIs.

### Current Upload Behavior

The frontend now:

* Creates FormData payloads
* Uploads directly to backend endpoints
* Waits for ingestion responses
* Normalizes backend rows
* Stores backend-derived state
* Redirects into dashboard workflows

### Main endpoint

```text
POST /api/v1/upload/ingest?document_type=sov
```

---

## 3. Backend Response Normalization Layer

A normalization layer was added between backend responses and frontend dashboard rendering.

This was necessary because backend rows can contain mixed naming conventions, while frontend dashboard components require stable field names.

### Normalized fields include

```text
property_id
property_reference
uprn
parent_uprn
block_reference
latitude
longitude
sum_insured
property_type
occupancy_type
height_m
storeys
units
readiness_score
readiness_band
missing_fields
```

---

## 4. Portfolio Dashboard Wireframing

The portfolio dashboard was rebuilt around backend-derived analytics instead of placeholder UI.

### Implemented dashboard sections

#### Underwriting snapshot

* Portfolio value
* Total blocks
* UPRN coverage
* Mapped properties
* Completeness metrics

#### Block analysis

* Grouped block table
* Block-level aggregation
* Map-based visualization
* Selected block panel

#### Property analysis

* Property schedule table
* Detailed property panel
* Readiness indicators
* Fire evidence links

#### Placeholder workflows

* Evidence Summary
* Block Analysis
* Documents
* Doc A / Doc B exports

---

## 5. Block and Property Hierarchy Work

One of the largest changes in this phase was introducing frontend-aware block/property grouping.

### Current grouping logic uses

* `block_reference`
* `parent_uprn`
* `uprn`
* `property_reference`
* fallback IDs

### Purpose

This grouping structure supports:

* Block-level aggregation
* Map clustering
* Underwriting summaries
* Risk analysis
* Evidence association
* Document linking

### Current work in progress

* Improving parent-child hierarchy consistency
* Preventing duplicated grouped properties
* Improving grouping when parent UPRN is missing
* Better reconciliation between frontend grouping and backend block models

---

## 6. Portfolio Map Rework

The map layer was substantially rewritten.

### Current capabilities

The map currently supports:

* Block mode
* Property mode
* Dynamic marker rendering
* Fly-to interactions
* Block selection
* Property selection
* Invalid coordinate filtering
* Tooltip rendering
* Popup rendering
* Grouped block display

### Coordinate handling

The map attempts multiple coordinate sources:

* `latitude` / `longitude`
* `x_coordinate` / `y_coordinate`
* alternative field names
* fallback parsing

Invalid coordinates are ignored, including:

```text
0,0
null
undefined
```

---

## 7. Property Details Panel Rebuild

The property details panel was rebuilt to support backend-driven rendering.

### Current displayed fields

* Address
* Postcode
* UPRN
* Parent UPRN
* Block reference
* Readiness band
* Readiness score
* Missing fields
* Sum insured
* Raw backend fields
* Fire evidence fields
* Placeholder enrichment fields

---

## 8. FRA / FRAEW Ingestion Work

FRA/FRAEW ingestion is currently one of the largest active workstreams.

### Current implemented work

#### Backend

* FRA/FRAEW upload routes exist
* Extraction workers exist
* Async processing exists
* Database persistence exists
* Action item extraction exists
* Risk extraction exists
* Assessment metadata extraction exists

### Current extracted fields include

* `risk_rating`
* `rag_status`
* `assessor_company`
* `assessor_name`
* `assessment_date`
* `next_review_date`
* `action_items`
* `significant_findings`
* `evacuation_strategy`
* `bsa_2022_applicable`
* fire safety system indicators

### Database persistence

FRA/FRAEW-related data is currently written into:

* `silver.document_features`
* `silver.fra_features`

---

## 9. FRA/FRAEW Colour Banding Work

A major issue currently being worked on is colour banding consistency.

### Current mismatch problem

Different areas of the platform currently use different fields for risk colour mapping:

* `risk_rating`
* `rag_status`
* inferred readiness
* local frontend mappings

This causes:

* Mismatched dashboard colours
* Incorrect amber/red/green chips
* FRA vs FRAEW inconsistencies
* Grey fallback states
* Inconsistent risk summaries

### Current normalization work

Normalization logic has recently been added in the backend write pipeline so frontend dashboard rendering receives more consistent values.

### Current colour banding issue areas

#### FRA/FRAEW

* Inconsistent risk scales
* Missing standardization
* Frontend fallback colours

#### Dashboard

* Some widgets use `risk_rating`
* Some widgets use `rag_status`
* Some widgets infer risk locally

#### Map markers

* Some markers derive colours from readiness
* Some markers derive colours from inferred risk

### Remaining work

* Standardize backend risk enums
* Remove duplicate frontend risk mappings
* Ensure consistent Red / Amber / Green rendering platform-wide
* Align FRA and FRAEW rendering logic

---

## 10. UPRN Mismatch Work

UPRN consistency is currently still a work in progress.

### Current mismatch areas

The SoV dashboard may currently show:

* Mismatched grouped properties
* Duplicated properties
* Incorrect block associations
* Inconsistent `parent_uprn` usage

### Likely causes

* Mixed source schedule formats
* Inconsistent UPRN enrichment
* Partial OS lookup coverage
* Fallback grouping heuristics
* Duplicate property references
* Parent UPRN inconsistencies

### Current work underway

#### Backend

* Improved enrichment logic
* Stronger hierarchy matching
* UPRN normalization
* Better fallback grouping

#### Frontend

* Normalized grouping logic
* Improved block display
* Property-to-block drilldown support

---

## 11. PDF Upload and Document Analysis Work

PDF upload and document analysis are currently partially integrated.

### Existing capabilities

#### Upload

* PDF upload routes exist
* Async processing exists
* Extraction workers exist

#### Parsing

Current extraction attempts:

* Metadata extraction
* Fire risk extraction
* Action item extraction
* Findings extraction
* Confidence scoring

### Still in progress

#### UI integration

Still needed:

* Frontend PDF upload flow
* Document analysis pages
* Evidence summary rendering
* Extraction visualization
* Extraction confidence display
* Block/property document linking

---

## 12. Evidence Summary and Block Analysis Pages

These pages are currently partially wired.

### Existing

* Frontend placeholders exist
* Dashboard routing exists
* Layout scaffolding exists

### Still needed

* Backend-driven evidence aggregation
* Linked documents
* Risk timelines
* Extracted action items
* Block-level fire evidence summaries
* Property-level document summaries

---

## 13. Async Ingestion and Worker Integration

Async ingestion architecture exists but is still being stabilized.

### Current architecture includes

#### Workers

* `sov_processor`
* `sov_processor_v2`
* `fra_processor`
* `fraew_processor`
* `enrichment_worker`

### Processing flow

```text
Upload
    ↓
Bronze storage
    ↓
Async worker
    ↓
Extraction
    ↓
Silver persistence
    ↓
Gold aggregation
```

---

## 14. Geo / Polygon Package Setup for City Coverage

The platform currently focuses mainly on **Glasgow** during local testing and MVP wireframing. The longer-term target is UK-wide support.

### Next priority cities

* Glasgow
* Edinburgh
* Manchester
* London
* Birmingham
* Liverpool
* Leeds
* Bristol

### Why geo/polygon support matters

The geo/polygon package work supports:

* block/property location matching
* map rendering
* UPRN enrichment checks
* local authority filtering
* geographic portfolio analysis
* polygon-based property grouping
* future exposure/risk aggregation

### Current status

* Glasgow-focused geo support has been used for testing
* The frontend map supports grouped block markers
* The platform still needs broader city polygon imports for MVP coverage
* UPRN and block/property hierarchy issues still need validation against richer geo datasets

### Recommended geo structure

```text
backend/geo/
├── polygons/
│   ├── glasgow/
│   ├── edinburgh/
│   ├── manchester/
│   ├── london/
│   └── README.md
├── uprn_maps/
└── loaders/
```

### Recommended polygon formats

Preferred formats:

* GeoJSON
* Shapefile (convert to GeoJSON where possible)
* CSV with WKT geometry

Recommended MVP file structure:

```text
backend/geo/polygons/<city>/<city>_wards.geojson
backend/geo/polygons/<city>/<city>_local_authority.geojson
backend/geo/polygons/<city>/<city>_postcodes.geojson
```

### Geo tooling dependencies

Recommended local tools:

* GDAL
* jq
* geopandas
* shapely
* pyproj
* fiona
* rtree

### Recommended MVP expansion order

1. Glasgow
2. Edinburgh
3. Manchester
4. London
5. Birmingham / Leeds / Liverpool / Bristol

### Recommended ingestion test files

```text
test-files/
├── sov/
├── fra/
└── fraew/
```

Suggested files:

```text
test-files/sov/glasgow_sample_sov.xlsx
test-files/sov/edinburgh_sample_sov.xlsx
test-files/sov/manchester_sample_sov.xlsx
test-files/sov/london_sample_sov.xlsx
```

```text
test-files/fra/glasgow_sample_fra.pdf
test-files/fraew/glasgow_sample_fraew.pdf
```

### Validation checklist after adding a city

After adding a city polygon package and SoV:

1. Upload the city SoV
2. Confirm dashboard loads
3. Confirm map locations render correctly
4. Confirm grouped blocks are sensible
5. Confirm UPRN associations look correct
6. Upload FRA/FRAEW documents
7. Confirm evidence links correctly to blocks/properties
8. Confirm colour banding renders consistently

### Remaining geo work

* Add geo loader scripts
* Add coordinate-to-polygon validation
* Improve geo-based UPRN mismatch detection
* Add frontend geo validation warnings
* Expand city-level test coverage
* Potential future PostGIS support

---

## 15. Current Known Issues

### FRA/FRAEW

* Colour banding mismatch
* Inconsistent normalization
* Frontend/backend risk mismatch

### UPRN

* Grouping inconsistencies
* Parent UPRN mismatch
* Duplicated grouping
* Incomplete enrichment

### Map

* Block selection edge cases
* Invalid coordinate handling
* Cluster consistency

### Backend

* Bedrock credential issues locally
* Async retry edge cases
* Some worker instability

### Frontend

* Some placeholder analytics
* Some locally inferred metrics
* Incomplete export workflows

---

# Local Development Setup

## Prerequisites

Install:

* Python 3.11+
* Node.js 18+
* npm
* Docker
* Docker Compose

---

## Clone the Repository

```bash
git clone <repo-url>
cd Platform-dev
```

---

## Backend Setup

### Create virtual environment

```bash
python3 -m venv venv
```

### Activate environment

Mac/Linux:

```bash
source venv/bin/activate
```

Windows:

```bash
venv\Scripts\activate
```

### Install backend dependencies

```bash
pip install -r requirements.txt
```

Optional local runtime:

```bash
pip install -r requirements.local.txt
```

---

## Frontend Setup

```bash
cd frontend
npm install
cd ..
```

---

## Frontend Environment Variables

Create:

```text
frontend/.env
```

Add:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## Start Docker Services

```bash
docker compose up -d
```

---

## Initialize Database

```bash
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_bronze_layer.sql

docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/002_async_processing_retries.sql

docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_silver_layer.sql

docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_gold_layer.sql
```

---

## Seed Local Data

```bash
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/seeds/week3_seed.sql
```

---

## Create LocalStack S3 Bucket

```bash
docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze
```

---

## Start Backend

```bash
source venv/bin/activate

DB_HOST=localhost \
DB_PORT=5432 \
DB_USER=postgres \
DB_PASSWORD=postgres \
DB_NAME=platform_dev \
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=us-east-1 \
S3_ENDPOINT_URL=http://localhost:4566 \
S3_BUCKET_NAME=platform-bronze \
DEV_MODE=true \
DEV_HA_ID=ha_demo \
uvicorn backend.main:app --reload --port 8000
```

---

## Backend Health Check

```bash
curl http://127.0.0.1:8000/health
```

---

## Start Frontend

```bash
cd frontend
npm run dev
```

Frontend typically runs at:

```text
http://localhost:5173
```

---

# Recommended Multi-Terminal Workflow

## Terminal 1 — Docker

```bash
docker compose up
```

## Terminal 2 — Backend

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

## Terminal 3 — Frontend

```bash
cd frontend
npm run dev
```

---

# Git Workflow

## Switch to branch

```bash
git checkout frontend-backend-wireframing
```

## Pull latest changes

```bash
git pull origin frontend-backend-wireframing
```

## Stage changes

```bash
git add .
```

## Commit

```bash
git commit -m "frontend-backend wiring updates"
```

## Push

```bash
git push origin frontend-backend-wireframing
```

---

# Current Working Features

## Frontend

* Backend-connected upload flow
* Portfolio dashboard rendering
* Grouped block analysis
* Map interactions
* Property details panel
* Backend normalization
* Underwriting layout structure
* Fire evidence panel

## Backend

* SoV ingestion
* Async upload handling
* FRA/FRAEW extraction
* Silver-layer persistence
* Enrichment workers
* Block grouping logic
* FRA/FRAEW persistence

---

# Major Remaining Work

## FRA/FRAEW

* Normalization consistency
* Frontend rendering
* Risk aggregation
* Document linking
* Confidence visualization

## UPRN

* Hierarchy correctness
* Grouping stability
* Enrichment consistency
* Duplicate prevention

## Block Hierarchy

* Stronger parent-child modelling
* Drilldown navigation
* Aggregation correctness

## Dashboard

* Backend source-of-truth enforcement
* Remove inferred frontend metrics
* Consistent aggregation logic

## Documents

* PDF upload UI
* Evidence pages
* Document visualization
* Doc A / Doc B generation

## Async Infrastructure

* Worker stabilization
* Retry handling
* Ingestion status polling
* Processing orchestration

## Geo / Polygon Support

* UK-wide city expansion
* Polygon validation
* Coordinate consistency checks
* Improved geo enrichment
* Larger ingestion test dataset coverage

---

# Summary

The platform has transitioned from isolated ingestion prototypes and partially mocked frontend workflows into a backend-driven portfolio intelligence platform with:

* Block-aware underwriting dashboard architecture
* Document-aware ingestion workflows
* Async processing infrastructure
* Enrichment-aware portfolio visualization
* Early FRA/FRAEW evidence handling
* Geo-aware portfolio analysis foundations

The primary remaining work is now correctness, normalization consistency, enrichment stabilization, document workflows, risk aggregation, export generation, evidence analytics, and geo-validation rather than initial frontend/backend structural integration.
