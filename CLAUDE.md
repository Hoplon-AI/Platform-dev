# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**EquiRisk** — UK social housing insurance risk assessment platform for housing associations (HAs) and underwriters. Ingests three document types (SoV Excel, FRA PDFs, FRAEW PDFs), processes through medallion architecture (Bronze S3 → Silver PostgreSQL → Gold views), enriches with OS/EPC APIs, and outputs Doc A (per-unit schedule) + Doc B (per-block schedule) for underwriters.

**Stack:** FastAPI + asyncpg backend (Windows, Python venv) | PostgreSQL in Docker | LocalStack S3 | AWS Bedrock (Claude Haiku for LLM extraction) | React 18 + TypeScript + Vite frontend

**Test portfolio:** `ha_demo` (Cathcart Demo, portfolio ID `11111111-1111-1111-1111-111111111111`, ~971 units, ~156 blocks)

**Key people:** Ewan (founder, Ewan@equirisk.ai), Kanishka (priorities), Igor (enrichment pipeline)

---

## Windows Development Environment

This project runs on **Windows with PowerShell**. Not Unix/WSL.

```powershell
# Activate venv
cd C:\EquiRiskAI\Platform-dev
.\venv\Scripts\Activate

# Start backend (set all env vars first — see Environment Variables section)
uvicorn backend.main:app --reload --port 8000

# Docker services
docker compose up -d
docker compose down
```

**Important:** Use PowerShell `Get-Content` patterns for migrations, not Unix redirects:
```powershell
# Apply migration
Get-Content database\migrations\020_enrichment.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev

# Or direct exec
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT COUNT(*) FROM silver.properties;"
```

---

## Environment Variables (PowerShell)

```powershell
$env:DEV_MODE = "true"
$env:DEV_HA_ID = "ha_demo"
$env:LOCAL_DEV = "true"
$env:LLM_PROVIDER = "bedrock"
$env:AWS_ACCESS_KEY_ID = "<real AWS key for Bedrock>"
$env:AWS_SECRET_ACCESS_KEY = "<real AWS secret>"
$env:AWS_DEFAULT_REGION = "eu-west-2"
$env:S3_ENDPOINT_URL = "http://localhost:4566"
$env:S3_BUCKET_NAME = "platform-bronze"
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/platform_dev"
$env:OS_PLACES_API_KEY = "1cNGEE0jL0R5pXlDpPd55wyEXnIBCF2J"
$env:OS_NGD_API_KEY = "1cNGEE0jL0R5pXlDpPd55wyEXnIBCF2J"
$env:EPC_EMAIL = "igorshuvalov23@gmail.com"
$env:EPC_API_KEY = "9213b51f9af85ba4700865191700778f0cc7f3fc"
```

---

## Common Commands

### Backend
```powershell
uvicorn backend.main:app --reload --port 8000
```
API docs: http://127.0.0.1:8000/docs

### Frontend
```powershell
cd frontend
npm install
npm run dev          # Dev server
npm run build        # Production build
npm run lint         # ESLint
```

### Database
```powershell
# Check row counts
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT COUNT(*) FROM silver.properties WHERE ha_id = 'ha_demo';"

# Check enrichment status
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT enrichment_status, COUNT(*) FROM silver.properties WHERE ha_id = 'ha_demo' GROUP BY enrichment_status;"

# Check blocks
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT COUNT(*) as blocks, SUM(unit_count) as units FROM silver.blocks WHERE ha_id = 'ha_demo';"

# Check FRA/FRAEW
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT fra_id, block_id, risk_rating, rag_status FROM silver.fra_features WHERE ha_id = 'ha_demo';"
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT fraew_id, block_id, building_risk_rating, rag_status FROM silver.fraew_features WHERE ha_id = 'ha_demo';"
```

### Testing
```powershell
python -m pytest tests/ -v
python -m pytest tests/test_silver_processor.py -v
```

---

## Architecture

### Data Flow
```
SoV Excel upload → LocalStack S3 Bronze → sov_processor_v3.py → silver.properties
                                                                      ↓
                                                          enrichment_worker.py
                                                    (OS Places → UPRN → EPC + NGD + Listed)
                                                                      ↓
                                                          silver.properties (enriched)
                                                          silver.blocks (block detection)
                                                                      ↓
FRA PDF upload → Bedrock Haiku → fra_processor.py → silver.fra_features
FRAEW PDF upload → Bedrock Haiku → fraew_processor.py → silver.fraew_features
                                                                      ↓
                                                    Doc A exporter (per-unit, 35+ cols)
                                                    Doc B exporter (per-block, 64 cols, LATERAL JOINs to FRA/FRAEW)
```

### Database Schemas

- **public**: Reference tables (`housing_associations`, `upload_audit`)
- **silver**: Entity tables (`properties`, `blocks`, `portfolios`, `document_features`, `fra_features`, `fraew_features`)
- **gold**: Analytics views (`portfolio_summary_v1`, `portfolio_composition_v1`, `doc_a_enriched`, `doc_b_enriched`, `enrichment_summary`)

### Key Tables

**silver.properties** (~35 SoV cols + ~20 enrichment cols):
- SoV: property_reference, block_reference, address, postcode, sum_insured, wall/roof/floor_construction, build_year, occupancy_type, etc.
- Enrichment: uprn, parent_uprn, x/y_coordinate, height_max_m, building_footprint_m2, epc_rating, listed_grade, enrichment_status, enrichment_source

**silver.blocks**: ha_id, name, block_id, parent_uprn, unit_count, total_sum_insured, max_storeys, height_max_m, is_listed, listed_grade

**silver.fra_features** (43 cols): risk_rating, rag_status, assessment_date, evacuation_strategy, has_sprinkler_system, has_fire_alarm_system, has_fire_doors, action_items (JSONB), etc.

**silver.fraew_features** (50 cols): building_risk_rating, rag_status, wall_types (JSONB), has_combustible_cladding, eps_insulation_present, has_remedial_actions, cavity_barriers_present, etc.

---

## Backend Structure

```
backend/
├── main.py                          # FastAPI app, lifespan, router registration
├── api/
│   ├── upload/upload_router.py      # SoV + PDF upload endpoints
│   ├── enrichment/enrichment_router.py  # POST /api/v1/enrich/{ha_id}
│   ├── v1/
│   │   ├── portfolio_router.py      # Portfolio queries, Doc A/B export
│   │   └── pdf_test_router.py       # FRA/FRAEW PDF test extraction
│   └── auth/                        # JWT utilities (pending)
├── core/
│   ├── exporters/
│   │   ├── doc_a_exporter.py        # Per-unit Excel (35+ cols + enrichment)
│   │   └── doc_b_exporter.py        # Per-block Excel (64 cols, FRA/FRAEW LATERAL JOINs)
│   ├── database/db_pool.py          # asyncpg connection pool
│   └── sov/sov_processor_v3.py      # Single-LLM-call SoV processor
├── workers/
│   ├── enrichment_worker.py         # OS Places + EPC + NGD + Listed + block detection
│   ├── fra_processor.py             # Two-pass FRA extraction (Bedrock)
│   ├── fraew_processor.py           # Two-pass FRAEW extraction (Bedrock)
│   └── llm_client.py                # Bedrock/Groq LLM client
└── geo/
    └── uprn_maps/                   # OS Places, EPC, NGD, Listed API wrappers
```

### Frontend Structure
```
frontend/src/
├── pages/                           # IngestionLandingPage, PortfolioOverviewPage
├── services/apiClient.ts            # API communication
└── components/                      # Shared UI components
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/upload/property-schedule` | POST | Upload SoV Excel |
| `/api/v1/enrich/{ha_id}` | POST | Run enrichment (body: `{"limit": 50}`) |
| `/api/v1/test/extract-pdf?document_type=fra` | POST | Extract FRA PDF |
| `/api/v1/test/extract-pdf?document_type=fraew` | POST | Extract FRAEW PDF |
| `/api/v1/portfolios/{id}/export/doc-a` | GET | Download Doc A Excel |
| `/api/v1/portfolios/{id}/export/doc-b` | GET | Download Doc B Excel |

Demo portfolio ID: `11111111-1111-1111-1111-111111111111`

---

## Key Patterns

### SQL — Always use schema prefix
```python
await conn.execute("INSERT INTO silver.properties ...")
await conn.fetch("SELECT * FROM gold.portfolio_summary_v1 WHERE ha_id = $1", ha_id)
```

### Tenant isolation — All queries scoped by ha_id
```python
WHERE p.ha_id = $1
```

### Database connection
```python
async with db_pool.acquire() as conn:
    result = await conn.fetch(query, *params)
```

### SoV-priority merge — Enrichment NEVER overwrites SoV data
```python
# enrichment_worker.py: _merge_sov_priority() only writes to NULL columns
if existing_val is None or (isinstance(existing_val, str) and not existing_val.strip()):
    updates[db_col] = api_val
```

### LLM extraction — Bedrock model configurable via env var
```python
# llm_client.py — model read from env, falls back to Sonnet
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
```

### FRA/FRAEW RAG derivation — always computed in Python, never from LLM
```python
# _normalise_rag_status() in fra_processor.py and fraew_processor.py
# Do NOT ask LLM to output rag_status — it causes ambiguity for edge cases like "Tolerable"
# RAG is always derived deterministically from risk_rating / building_risk_rating keyword matching
rag_status = self._normalise_rag_status(features.risk_rating)
```

### FRA overdue_action_count — computed from due_date, not LLM status text
```python
# _count_actions() in fra_processor.py
# LLM never sets status="overdue" in practice — documents use "outstanding"
# Fix (branch fra-fraew-fixes, Apr 2026): compare due_date < date.today()
overdue = sum(
    1 for a in action_items
    if a.due_date is not None
    and a.due_date < today
    and a.status != "completed"
)
```

### Doc B FRA/FRAEW — LATERAL JOINs through silver.blocks
```sql
LEFT JOIN LATERAL (
    SELECT f.* FROM silver.fra_features f
    JOIN silver.blocks b ON f.block_id = b.block_id
    WHERE b.ha_id = $1 AND b.name = a.block_reference
    ORDER BY f.assessment_date DESC NULLS LAST LIMIT 1
) fra ON true
```

---

## Migrations (applied in order)

001–012: Core schema (properties, blocks, portfolios, uploads, gold views)
013–015: FRA features (43 cols), FRAEW features (50 cols), document_features
016–019: Various fixes
020: Enrichment columns + gold views (doc_a_enriched, doc_b_enriched, enrichment_summary)
018: Underwriter dashboard (WRITTEN, NOT YET APPLIED)

---

## Current State

- **SoV pipeline:** Working. sov_processor_v3.py validated across 8 example files.
- **Enrichment:** Working. 250/971 properties enriched. OS Places postcode batching implemented but cache hit rate needs improvement (156 calls for 250 rows instead of ~25).
- **FRA/FRAEW extraction:** Working via Bedrock Haiku. Data populates Doc B Q32–Q58.
- **Doc A:** Working. 35 SoV cols + 7 enrichment cols.
- **Doc B:** Working. 64 cols with FRA/FRAEW LATERAL JOINs.
- **Known issue:** FRA/FRAEW uploads don't auto-assign block_id (requires manual SQL).
- **Fixed (fra-fraew-fixes, Apr 2026):** `overdue_action_count` was always zero — now computed from `due_date < today AND status != completed` in `_count_actions()`.
- **Fixed (fra-fraew-fixes, Apr 2026):** Removed duplicate `rag_status` derivation from FRA/FRAEW prompts — RAG now derived solely by `_normalise_rag_status()` keyword matching.
- **Pending:** Underwriter dashboard (migration 018 + jwt_utils.py written, React UI not started).
- **Pending:** `assessment_valid_until` fallback — populate from `next_review_date` when null (02BR example: `assessment_valid_until=null`, `next_review_date=2025-06-18`).
- **Pending MVP:** FRA/FRAEW upload UI, per-block action drill-down endpoint (`GET /fra-blocks/{block_id}/actions`), RED block summary endpoint.

---

## Code Standards

- Python: Type hints, thin routes, business logic in workers/services
- TypeScript: Strict mode, functional components, API calls in services layer
- SQL: Parameterized queries ($1, $2), explicit columns, snake_case, schema prefix
- All new columns added to existing tables must have DEFAULT or be nullable
- Enrichment columns follow SoV-priority rule (never overwrite)