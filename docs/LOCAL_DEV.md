# Local development (Option B: real DB + LocalStack)

This guide runs:
- **Postgres 16.9** in Docker (for `asyncpg`)
- **LocalStack** (S3 only) for upload storage

## 1) Start dependencies

From the repo root:

```bash
docker compose up -d
docker compose ps
```

## 2) Apply migrations

Run migrations inside the Postgres container:

```bash
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_bronze_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/002_async_processing_retries.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_silver_layer.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/003_silver_document_features.sql
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/migrations/001_gold_layer.sql
```

## 3) Seed Week 3 data

```bash
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev < database/seeds/week3_seed.sql
```

Optional sanity checks:

```bash
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "select * from gold.portfolio_summary_v1;"
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "select * from gold.portfolio_risk_distribution_v1;"
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "select * from gold.portfolio_readiness_v1;"
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "select * from gold.ha_recent_activity_v1;"
```

## 4) Create the S3 bucket in LocalStack

LocalStack provides `awslocal` inside the container:

```bash
docker exec -i platform-dev-localstack awslocal s3 mb s3://platform-bronze
```

## 5) Run the backend locally

Environment variables (example):

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=platform_dev

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export S3_ENDPOINT_URL=http://localhost:4566
export S3_BUCKET_NAME=platform-bronze

# Optional for local development
export DEV_MODE=true
```

Start the API:

```bash
uvicorn backend.main:app --reload --port 8000
```

## 6) Run the frontend locally (Week 3 dashboard work)

```bash
cd frontend
npm install
npm run dev
```

If you want the frontend to call your local API:

```bash
export VITE_API_BASE_URL=http://localhost:8000
```

## 7) Tear down

```bash
docker compose down
```

