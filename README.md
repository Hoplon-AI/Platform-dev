Platform-dev

Full-stack property portfolio management, ingestion, enrichment, underwriting analytics, and geo-aware portfolio intelligence platform built with React (Vite) + FastAPI + PostgreSQL.

⸻

Overview

Platform-dev is a backend-driven portfolio intelligence platform focused on:

* Property schedule ingestion (SoV / stock schedules)
* Block and property hierarchy modelling
* UPRN enrichment and matching
* FRA / FRAEW document ingestion
* Underwriting analytics
* Readiness and risk scoring
* Block-level mapping and portfolio visualization
* Geo-aware enrichment and polygon analysis
* Document evidence aggregation
* Export generation workflows (Doc A / Doc B)

The platform architecture is organized around a lakehouse-style ingestion model:

* Bronze: raw uploads and source lineage
* Silver: normalized and enriched entities
* Gold: dashboard and underwriting analytics views

The frontend-backend-wireframing branch represents the transition from mostly mock frontend flows and isolated ingestion prototypes into a fully wired frontend/backend integration layer, backend-driven dashboard rendering, block-aware portfolio analytics, document-oriented risk workflows, and geo-aware portfolio analysis.

⸻

Current Development Focus

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

⸻

Repository Structure

Platform-dev/
├── backend/
│   ├── api/
│   ├── workers/
│   ├── geo/
│   ├── enrichment/
│   └── core/
│
├── frontend/
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
├── schemas/
├── docs/
├── scripts/
├── test-files/
└── docker-compose.yml

⸻

Technology Stack

Frontend

* React
* Vite
* TypeScript / JavaScript
* React Router
* Leaflet
* PapaParse

Backend

* FastAPI
* asyncpg
* boto3
* PostgreSQL
* LocalStack
* Pydantic
* Bedrock integration (optional for local work)

Infrastructure

* Docker
* Docker Compose
* S3-style storage
* LocalStack S3 emulation

⸻

Frontend–Backend Wireframing Progress Report

This section summarizes the major integration and wireframing work completed during the current development cycle.

⸻

1. Frontend Application Flow Rework

The frontend application structure was remodeled to align with the backend ingestion and analytics pipeline.

Preserved

* Original landing page
* Original app entry flow

Added/Reworked

* Ingestion-style upload page
* Backend-connected upload workflow
* Backend-driven dashboard flow
* Underwriting-style dashboard layout
* Sidebar/dashboard navigation structure
* Block analysis layout structure
* Evidence summary placeholders
* Document workflow placeholders

Current frontend flow

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

⸻

2. Backend-Connected Upload Pipeline

The frontend upload flow was reworked so uploads now hit the real backend ingestion APIs.

Current Upload Behavior

The frontend now:

* Creates FormData payloads
* Uploads directly to backend endpoints
* Waits for ingestion responses
* Normalizes backend rows
* Stores backend-derived state
* Redirects into dashboard workflows

Main endpoint

POST /api/v1/upload/ingest?document_type=sov

⸻

3. Backend Response Normalization Layer

A normalization layer was added between backend responses and frontend dashboard rendering.

This was necessary because backend rows can contain mixed naming conventions, while frontend dashboard components require stable field names.

Normalized fields include

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

⸻

4. Portfolio Dashboard Wireframing

The portfolio dashboard was rebuilt around backend-derived analytics instead of placeholder UI.

Implemented dashboard sections

Underwriting snapshot

* Portfolio value
* Total blocks
* UPRN coverage
* Mapped properties
* Completeness metrics

Block analysis

* Grouped block table
* Block-level aggregation
* Map-based visualization
* Selected block panel

Property analysis

* Property schedule table
* Detailed property panel
* Readiness indicators
* Fire evidence links

Placeholder workflows

* Evidence Summary
* Block Analysis
* Documents
* Doc A / Doc B exports

⸻

5. Block and Property Hierarchy Work

One of the largest changes in this phase was introducing frontend-aware block/property grouping.

Current grouping logic uses

* block_reference
* parent_uprn
* uprn
* property_reference
* fallback IDs

Purpose

This grouping structure supports:

* Block-level aggregation
* Map clustering
* Underwriting summaries
* Risk analysis
* Evidence association
* Document linking

Current work in progress

* Improving parent-child hierarchy consistency
* Preventing duplicated grouped properties
* Improving grouping when parent UPRN is missing
* Better reconciliation between frontend grouping and backend block models

⸻

6. Portfolio Map Rework

The map layer was substantially rewritten.

Current capabilities

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

Coordinate handling

The map attempts multiple coordinate sources:

* latitude / longitude
* x_coordinate / y_coordinate
* alternative field names
* fallback parsing

Invalid coordinates are ignored, including:

0,0
null
undefined

⸻

FRA / FRAEW Work

Current Implemented Work

Backend

* FRA/FRAEW upload routes exist
* Extraction workers exist
* Async processing exists
* Database persistence exists
* Action item extraction exists
* Risk extraction exists
* Assessment metadata extraction exists

Current extracted fields include

* risk_rating
* rag_status
* assessor_company
* assessor_name
* assessment_date
* next_review_date
* action_items
* significant_findings
* evacuation_strategy
* bsa_2022_applicable

⸻

FRA / FRAEW Colour Banding Mismatch

A major active workstream is standardizing FRA/FRAEW colour banding and risk rendering.

Current mismatch problem

Different areas of the platform currently use different fields for risk colour mapping:

* risk_rating
* rag_status
* inferred readiness
* frontend fallback mappings

This causes:

* Mismatched dashboard colours
* Incorrect red/amber/green chips
* FRA vs FRAEW inconsistencies
* Grey fallback states
* Inconsistent risk summaries

Remaining work

* Standardize backend risk enums
* Remove duplicate frontend risk mappings
* Ensure consistent Red / Amber / Green rendering platform-wide
* Align FRA and FRAEW rendering logic

⸻

UPRN Mismatch Work

UPRN consistency is currently still a work in progress.

Current mismatch areas

The SoV dashboard may currently show:

* Mismatched grouped properties
* Duplicated properties
* Incorrect block associations
* Inconsistent parent_uprn usage

Likely causes

* Mixed source schedule formats
* Inconsistent UPRN enrichment
* Partial OS lookup coverage
* Fallback grouping heuristics
* Duplicate property references
* Parent UPRN inconsistencies

Current work underway

Backend

* Improved enrichment logic
* Stronger hierarchy matching
* UPRN normalization
* Better fallback grouping

Frontend

* Normalized grouping logic
* Improved block display
* Property-to-block drilldown support

⸻

Geo / Polygon Package Workflow

The platform currently focuses mainly on Glasgow during local testing and MVP wireframing. The longer-term target is UK-wide support.

⸻

Geo Data Sources

The platform geo workflows currently rely on UK geospatial and mapping datasets from the following sources:

Boundary / Polygon Sources

* ONS Open Geography Portal
* Ordnance Survey Open Data
* data.gov.uk Geospatial Datasets

These are used for:

* Local authority boundaries
* Ward polygons
* Postcode polygons
* Administrative boundaries
* GIS validation
* Polygon-based enrichment

Mapping Sources

* OpenStreetMap
* LeafletJS

These are used for:

* Base map rendering
* Tile layers
* Coordinate visualization
* Frontend map interaction

UPRN / Address Sources

* OS Open UPRN

Used for:

* UPRN enrichment
* Parent-child matching
* Address normalization
* Block/property hierarchy work

⸻

Current Geo Coverage

Current MVP geo focus:

* Glasgow

Planned expansion order:

1. Glasgow
2. Edinburgh
3. Manchester
4. London
5. Birmingham
6. Leeds
7. Liverpool
8. Bristol

⸻

Recommended Geo Folder Structure

backend/geo/
├── polygons/
│   ├── glasgow/
│   ├── edinburgh/
│   ├── manchester/
│   ├── london/
│   └── README.md
├── uprn_maps/
└── loaders/

⸻

Recommended Polygon Formats

Preferred formats:

* GeoJSON
* Shapefile
* CSV with WKT geometry

Recommended structure:

backend/geo/polygons/<city>/<city>_wards.geojson
backend/geo/polygons/<city>/<city>_local_authority.geojson
backend/geo/polygons/<city>/<city>_postcodes.geojson

⸻

Geo Tooling Dependencies

Recommended local tools:

* GDAL
* geopandas
* shapely
* pyproj
* fiona
* rtree
* jq

⸻

Geo Expansion Workflow

Recommended process for onboarding a new city:

1. Download polygon/boundary datasets from:
    * ONS Open Geography Portal
    * Ordnance Survey Open Data
2. Convert datasets into GeoJSON if needed
3. Add city polygon package under:

backend/geo/polygons/<city>/

4. Add city-specific test SoV files
5. Upload SoV locally
6. Validate:
    * Map rendering
    * UPRN associations
    * Block grouping
    * Polygon matching
    * FRA/FRAEW evidence links
7. Verify colour banding consistency

⸻

Recommended Test File Structure

test-files/
├── sov/
├── fra/
└── fraew/

Example files:

test-files/sov/glasgow_sample_sov.xlsx
test-files/sov/edinburgh_sample_sov.xlsx
test-files/sov/manchester_sample_sov.xlsx
test-files/sov/london_sample_sov.xlsx
test-files/fra/glasgow_sample_fra.pdf
test-files/fraew/glasgow_sample_fraew.pdf

⸻

Local Development Setup

Prerequisites

Install:

* Python 3.11+
* Node.js 18+
* npm
* Docker
* Docker Compose

⸻

Clone Repository

git clone <repo-url>
cd Platform-dev

⸻

Backend Setup

Create Virtual Environment

python3 -m venv venv

Activate Environment

Mac/Linux:

source venv/bin/activate

Windows:

venv\\Scripts\\activate

Install Backend Dependencies

pip install -r requirements.txt

Optional:

pip install -r requirements.local.txt

⸻

Frontend Setup

cd frontend
npm install
cd ..

⸻

Frontend Environment Variables

Create:

frontend/.env

Add:

VITE_API_BASE_URL=http://127.0.0.1:8000

⸻

Start Docker Services

docker compose up -d

⸻

Initialize Database

docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_bronze_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/002_async_processing_retries.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_silver_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_gold_layer.sql

⸻

Seed Local Data

docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/seeds/week3_seed.sql

⸻

Create LocalStack S3 Bucket

docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze

⸻

Start Backend

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

⸻

Backend Health Check

curl http://127.0.0.1:8000/health

⸻

Start Frontend

cd frontend
npm run dev

Frontend usually runs at:

http://localhost:5173

⸻

Recommended Multi-Terminal Workflow

Terminal 1 — Docker

docker compose up

Terminal 2 — Backend

source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

Terminal 3 — Frontend

cd frontend
npm run dev

⸻

Git Workflow

Switch to branch

git checkout frontend-backend-wireframing

Pull latest changes

git pull origin frontend-backend-wireframing

Stage changes

git add .

Commit

git commit -m "frontend-backend wiring updates"

Push

git push origin frontend-backend-wireframing

⸻

Current Working Features

Frontend

* Backend-connected upload flow
* Portfolio dashboard rendering
* Grouped block analysis
* Map interactions
* Property details panel
* Backend normalization
* Underwriting layout structure
* Fire evidence panel

Backend

* SoV ingestion
* Async upload handling
* FRA/FRAEW extraction
* Silver persistence
* Enrichment workers
* Block grouping logic
* FRA/FRAEW persistence

⸻

Major Remaining Work

FRA/FRAEW

* Normalization consistency
* Frontend rendering
* Risk aggregation
* Document linking
* Confidence visualization

UPRN

* Hierarchy correctness
* Grouping stability
* Enrichment consistency
* Duplicate prevention

Block Hierarchy

* Stronger parent-child modelling
* Drilldown navigation
* Aggregation correctness

Dashboard

* Backend source-of-truth enforcement
* Remove inferred frontend metrics
* Consistent aggregation logic

Documents

* PDF upload UI
* Evidence pages
* Document visualization
* Doc A / Doc B generation

Async Infrastructure

* Worker stabilization
* Retry handling
* Processing orchestration

Geo / Polygon Support

* UK-wide city expansion
* Polygon validation
* Coordinate consistency checks
* Improved geo enrichment
* Larger ingestion test dataset coverage

⸻

Summary

The platform has transitioned from isolated ingestion prototypes and partially mocked frontend workflows into a backend-driven portfolio intelligence platform with:

* Block-aware underwriting dashboard architecture
* Document-aware ingestion workflows
* Async processing infrastructure
* Enrichment-aware portfolio visualization
* Early FRA/FRAEW evidence handling
* Geo-aware portfolio analysis foundations

The primary remaining work is now correctness, normalization consistency, enrichment stabilization, document workflows, risk aggregation, export generation, evidence analytics, and geo-validation rather than initial frontend/backend structural integration.

⸻

Development, Deployment & Operations

Branch / Release Workflow

Three-tier flow: feature/* → staging → main → production. Full guide in docs/DEV_WORKFLOW.md.

* feature/*  — branch off staging; local only
* staging    — integration / QA branch
* main       — stable, reviewed; receives squash/merge PRs from staging
* production — release branch; intended to deploy the live site (pipeline pending)

Note: the default branch is main (there is no master).

Local Development

Prerequisites: Docker Desktop running, Python venv, Node 18+.

1. docker compose up -d                                       (Postgres :5432 + LocalStack :4566)
2. .\venv\Scripts\uvicorn.exe backend.main:app --port 8000    (API on :8000; auto-loads .env)
3. cd frontend; npm install; npm run dev                      (UI on :5173)

Frontend API wiring is automatic: npm run dev → http://127.0.0.1:8000 (frontend/.env);
npm run build → the CloudFront URL (frontend/.env.production). Dev mode (DEV_MODE=true)
bypasses login and serves the ha_demo portfolio (~971 properties).

Hosting & Deployment

* Live frontend: https://d16062fpplraah.cloudfront.net (AWS CloudFront).
* IMPORTANT — there is currently NO automated frontend deploy. The live site is updated
  manually (vite build → aws s3 sync → CloudFront invalidation). No branch auto-deploys.
* The CDK workflow (.github/workflows/cdk-deploy-dev.yml) runs on push to main, but its
  deploy job is disabled (if: false, FIXME KAN-463) — only lint + synth run. CDK manages
  backend infra (ECS / networking / data), NOT the CloudFront frontend.
* To wire production → live: build a workflow on push to production (vite build →
  aws s3 sync s3://<bucket> → cloudfront create-invalidation). Needs valid AWS creds for
  account 025215344919 (eu-west-1) plus the frontend S3 bucket name and CloudFront
  distribution ID.

AWS / Bedrock Credentials (important gotcha)

LLM extraction (SoV + FRA/FRAEW) uses AWS Bedrock and needs valid AWS keys. backend/main.py
calls load_dotenv() with override=False, so AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY already
present in the OS environment SHADOW the values in .env. A stale User-scope AWS_ACCESS_KEY_ID
caused "UnrecognizedClientException: The security token included in the request is invalid"
on FRA upload, even though .env held a valid key. If you hit this:

* Check the active identity: aws sts get-caller-identity
* Fix by any of: remove the stale User-scope AWS_* env vars; export AWS_* from .env before
  launching the backend; or set load_dotenv(override=True). Region is eu-west-2.
