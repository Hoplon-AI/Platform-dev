# EquiRisk Platform — Local Setup Guide

Branch: `frontend-backend-wireframing`

---

## Prerequisites

Install the following before starting:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| Docker Desktop | Latest | https://docker.com |
| Git | Latest | https://git-scm.com |

You will also need **real AWS credentials** with access to:
- AWS Bedrock (Claude Haiku) in `eu-west-2`
- (LocalStack handles S3 locally — no real S3 needed)

---

## 1. Clone and Switch to Branch

```bash
git clone <repo-url>
cd Platform-dev
git checkout frontend-backend-wireframing
git pull origin frontend-backend-wireframing
```

---

## 2. Start Docker Services

Docker must be running before anything else.

```bash
docker compose up -d
```

This starts:
- `platform-dev-postgres` — PostgreSQL on port 5432
- `platform-dev-localstack` — LocalStack S3 on port 4566

Verify both are up:

```bash
docker ps
```

---

## 3. Run Database Migrations

Run all migrations in order. **Do not skip any.**

**Windows (PowerShell) — apply each file:**

```powershell
Get-Content database\migrations\001a_bronze_layer.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\001b_silver_layer.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\001c_gold_layer.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\002_async_processing_retries.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\003_silver_document_features.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\004_add_uprn_postcode_to_fraew.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\005_add_frsa_specific_fields.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\006_add_agentic_building_safety_features.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\007_add_gold_agentic_features_views.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\008_test_data.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\009_expand_scr_features.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\010_add_scr_uprn_fields.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\011_schema_reorganization.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\012_underwriter_dashboard.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\013_fra_features.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\014_fra_risk_scoring.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\015_fraew_features_rebuild.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\016_sov_doc_a_b_fields.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\017_sov_missing_fields.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\019_sov_enrichment_columns.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\020_enrichment.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\021_renewal_date.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\022_auth.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\024_add_submission_id_to_properties.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
```

**Mac/Linux:**

```bash
for f in \
  database/migrations/001a_bronze_layer.sql \
  database/migrations/001b_silver_layer.sql \
  database/migrations/001c_gold_layer.sql \
  database/migrations/002_async_processing_retries.sql \
  database/migrations/003_silver_document_features.sql \
  database/migrations/004_add_uprn_postcode_to_fraew.sql \
  database/migrations/005_add_frsa_specific_fields.sql \
  database/migrations/006_add_agentic_building_safety_features.sql \
  database/migrations/007_add_gold_agentic_features_views.sql \
  database/migrations/008_test_data.sql \
  database/migrations/009_expand_scr_features.sql \
  database/migrations/010_add_scr_uprn_fields.sql \
  database/migrations/011_schema_reorganization.sql \
  database/migrations/012_underwriter_dashboard.sql \
  database/migrations/013_fra_features.sql \
  database/migrations/014_fra_risk_scoring.sql \
  database/migrations/015_fraew_features_rebuild.sql \
  database/migrations/016_sov_doc_a_b_fields.sql \
  database/migrations/017_sov_missing_fields.sql \
  database/migrations/019_sov_enrichment_columns.sql \
  database/migrations/020_enrichment.sql \
  database/migrations/021_renewal_date.sql \
  database/migrations/022_auth.sql \
  database/migrations/024_add_submission_id_to_properties.sql
do
  echo "Applying $f..."
  cat "$f" | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
done
```

> **Note:** Migration 018 does not exist. Migration 023 is on a separate branch (`sov-improvements`) and is not required for this branch.

> **Important:** Migration 024 adds `submission_id` to `silver.properties`. The backend will error without it.

Verify migrations applied:

```bash
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "\dt silver.*"
```

---

## 4. Create LocalStack S3 Bucket

```bash
docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze
```

Verify:

```bash
docker exec -i platform-dev-localstack awslocal s3 ls
```

---

## 5. Backend Setup

### Create and activate virtual environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

**Mac/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

Key backend dependencies:
- `fastapi` + `uvicorn` — web server
- `asyncpg` — async PostgreSQL
- `boto3` — AWS SDK (Bedrock + S3)
- `pandas` + `openpyxl` — SoV Excel processing
- `pdfplumber` — PDF extraction
- `PyJWT` + `bcrypt` — auth
- `python-dotenv` — env loading

---

## 6. Set Environment Variables

**Windows (PowerShell):**

```powershell
$env:DEV_MODE = "true"
$env:DEV_HA_ID = "ha_demo"
$env:LOCAL_DEV = "true"
$env:LLM_PROVIDER = "bedrock"
$env:AWS_ACCESS_KEY_ID = "<your-real-aws-key>"
$env:AWS_SECRET_ACCESS_KEY = "<your-real-aws-secret>"
$env:AWS_DEFAULT_REGION = "eu-west-2"
$env:S3_ENDPOINT_URL = "http://localhost:4566"
$env:S3_BUCKET_NAME = "platform-bronze"
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/platform_dev"
$env:OS_PLACES_API_KEY = "7VakhnbibvboaY9eE0385zORrBJAc2sw"
$env:OS_NGD_API_KEY = "7VakhnbibvboaY9eE0385zORrBJAc2sw"
$env:EPC_EMAIL = "igorshuvalov23@gmail.com"
$env:EPC_API_KEY = "9213b51f9af85ba4700865191700778f0cc7f3fc"
$env:JWT_SECRET = "equirisk-local-dev-secret"
```

**Mac/Linux:**

```bash
export DEV_MODE=true
export DEV_HA_ID=ha_demo
export LOCAL_DEV=true
export LLM_PROVIDER=bedrock
export AWS_ACCESS_KEY_ID=<your-real-aws-key>
export AWS_SECRET_ACCESS_KEY=<your-real-aws-secret>
export AWS_DEFAULT_REGION=eu-west-2
export S3_ENDPOINT_URL=http://localhost:4566
export S3_BUCKET_NAME=platform-bronze
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/platform_dev
export OS_PLACES_API_KEY=1cNGEE0jL0R5pXlDpPd55wyEXnIBCF2J
export OS_NGD_API_KEY=1cNGEE0jL0R5pXlDpPd55wyEXnIBCF2J
export EPC_EMAIL=igorshuvalov23@gmail.com
export EPC_API_KEY=9213b51f9af85ba4700865191700778f0cc7f3fc
export JWT_SECRET=equirisk-local-dev-secret
```

> `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` must be real AWS credentials — Bedrock (LLM extraction) calls real AWS.

---

## 7. Start the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Verify it's running:

```bash
curl http://127.0.0.1:8000/health
```

API docs available at: `http://127.0.0.1:8000/docs`

---

## 8. Frontend Setup

```bash
cd frontend
npm install
```

The `frontend/.env` file should contain:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

This is already committed. Do not change it for local dev.

Start the frontend:

```bash
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## 9. Test Login

Use these credentials to log in:

```
Email:    saraswatgovind70@gmail.com
Password: EquiRisk@123
```

---

## Recommended Terminal Layout

Run each in a separate terminal:

**Terminal 1 — Docker**
```bash
docker compose up
```

**Terminal 2 — Backend**
```bash
# activate venv first, set env vars, then:
uvicorn backend.main:app --reload --port 8000
```

**Terminal 3 — Frontend**
```bash
cd frontend
npm run dev
```

---

## Quick Health Checks

```bash
# Postgres is up
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT COUNT(*) FROM silver.properties WHERE ha_id = 'ha_demo';"

# LocalStack S3 is up
docker exec -i platform-dev-localstack awslocal s3 ls

# Backend is up
curl http://127.0.0.1:8000/health

# Frontend is up
# Open http://localhost:5173 in browser
```

---

## Branching from This Branch

If you are working on a new feature, branch off from here:

```bash
git checkout frontend-backend-wireframing
git pull origin frontend-backend-wireframing
git checkout -b your-feature-branch
```

Push your branch when ready:

```bash
git push -u origin your-feature-branch
```

---

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/auth/login` | POST | Login (returns JWT) |
| `/api/v1/auth/me` | GET | Current user info |
| `/api/v1/upload/ingest` | POST | Upload SoV Excel |
| `/api/v1/enrich/{ha_id}` | POST | Run enrichment |
| `/api/v1/portfolios/{id}/export/doc-a` | GET | Download Doc A |
| `/api/v1/portfolios/{id}/export/doc-b` | GET | Download Doc B |

Demo portfolio ID: `11111111-1111-1111-1111-111111111111`

---

## Troubleshooting

**Backend fails to start — `relation silver.properties does not exist`**
- Migrations have not been applied. Run step 3.

**Backend fails — `column submission_id does not exist`**
- Migration 024 is missing. Run:
  ```powershell
  Get-Content database\migrations\024_add_submission_id_to_properties.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
  ```

**Bedrock errors — `Could not connect to the endpoint URL`**
- Check `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION=eu-west-2`.

**Frontend shows blank / can't reach API**
- Confirm `VITE_API_BASE_URL=http://127.0.0.1:8000` in `frontend/.env`
- Confirm backend is running on port 8000

**LocalStack S3 bucket missing**
- Re-run step 4: `docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze`
