# Platform-dev (Week 1–2 Scope)

This repo is currently scoped to **Week 1–2 only** of the medallion refactor: the **Bronze layer** foundations (upload → audit → lineage → governance).

## Architecture Overview (Week 1–2)

- **Bronze Layer**: Raw, unprocessed data landing zone (S3/object storage) + audit logging + lineage scaffolding
- **Silver/Gold**: Out of scope for this branch (intentionally not implemented)

## Directory Structure

```
Platform-dev/
├── infrastructure/
│   └── storage/          # S3 configuration and upload services
├── backend/
│   ├── core/
│   │   ├── audit/        # Audit logging and lineage tracking
│   │   ├── gdpr/         # GDPR compliance
│   │   └── tenancy/      # Tenant isolation
│   ├── api/
│   │   ├── ingestion/    # Upload endpoints
│   │   └── v1/           # Minimal v1 (lineage endpoints only)
├── database/
│   └── migrations/       # SQL migration files
└── tests/                # Test suite
```

## Key Features Implemented

### Week 1-2: Bronze Layer
- S3 object storage infrastructure
- Upload service with checksum validation
- Version management
- Audit logging system
- Enhanced lineage tracking (submission + UPRN based)
- GDPR compliance infrastructure
- Tenant isolation middleware

## Running the Application

### Backend

```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

### Database Migrations

```bash
psql -U postgres -d platform_dev -f database/migrations/001_bronze_layer.sql
```

## Next Steps

1. Connect database layer
2. Implement actual database operations in placeholder methods
3. Set up S3 bucket and configure credentials
4. Implement JWT authentication
5. Complete frontend integration
6. Add comprehensive tests
