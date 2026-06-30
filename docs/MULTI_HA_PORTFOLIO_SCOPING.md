# Multi-HA / Portfolio Scoping + FRA/FRAEW Polish

Branch: `feature/multi-ha-portfolio-scoping`
Base: `govind_sov_improvement_integration`

This branch makes the platform correctly multi-tenant at the **portfolio** level and
finishes the FRA/FRAEW evidence experience (remedial actions, source-PDF viewing,
auto block-linking). It is **25 commits / 17 files** ahead of the base branch.

---

## 1. What this branch delivers

### Multi-HA / multi-portfolio scoping
- One underwriter can access multiple Housing Associations; one HA can hold multiple
  portfolios (one per SoV upload / renewal year).
- Every property and block is now scoped by `portfolio_id`, not just `ha_id`.
- SoV re-upload **replaces** a portfolio's rows instead of accumulating duplicates.
- Doc A, Doc B, the underwriter dashboard, enrichment and block detection are all
  portfolio-scoped.
- **Security fix:** `_resolve_portfolio` previously had no tenant check — a guessed
  portfolio UUID exposed another tenant's data. Now enforces `ha_id`.
- **Data-integrity fix:** the unique constraint changed so the same property/block
  reference can exist in different portfolios without overwriting the first.

### FRA / FRAEW evidence
- **Auto block-linking** from the filename (`FRA_04CR_…pdf` → block `04CR`) — no more
  manual block-reference entry on every upload.
- Remedial actions drill-down (FRA `action_items` + FRAEW `remedial_actions`) as
  expandable cards on Block Analysis.
- **View source PDF** from the Data Provenance section (streams the original from S3).
- Properties in a block inherit the block-level FRA/FRAEW band.
- New FRA/FRAEW appears **without a page refresh**.

---

## 2. Database migrations — MUST be applied after pull

This branch adds **three migrations** that change live table structure. After merging
and pulling, apply them **in order** to your local Postgres (Docker):

```powershell
Get-Content database\migrations\025_portfolio_id_backfill.sql            | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\026_portfolio_property_unique_constraint.sql | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
Get-Content database\migrations\027_blocks_portfolio_unique_constraint.sql   | docker exec -i platform-dev-postgres psql -U postgres -d platform_dev
```

| Migration | Effect |
|---|---|
| 025 | Backfills `portfolio_id` on `silver.properties` + `silver.blocks`; replaces single-col indexes with composite `(ha_id, portfolio_id)` |
| 026 | `silver.properties`: drop `UNIQUE(ha_id, property_reference)` → add `UNIQUE(ha_id, portfolio_id, property_reference)` |
| 027 | `silver.blocks`: drop `UNIQUE(ha_id, name)` → add `UNIQUE(ha_id, portfolio_id, name)` |

All three are **idempotent / safe to re-run** (guarded with `IF EXISTS` / `IF NOT EXISTS`
and `WHERE portfolio_id IS NULL`).

> If a migration warns that rows still have `NULL portfolio_id`, it means that HA has
> no row in `silver.portfolios`. Create the portfolio first, then re-run 025.

---

## 3. Post-pull checklist (the steps "the other guy" follows)

After `govind_sov_improvement_integration` has been merged with this branch:

```powershell
# 1. Pull
git checkout govind_sov_improvement_integration
git pull origin govind_sov_improvement_integration

# 2. Make sure Docker services are up
docker compose up -d                 # postgres + localstack

# 3. Apply the three migrations (section 2 above) — REQUIRED

# 4. Backend — activate venv and set env BEFORE launching (see CLAUDE.md / .env)
.\venv\Scripts\Activate
#   IMPORTANT: a stale User-scope OS_PLACES_API_KEY / AWS_ACCESS_KEY_ID in the OS
#   environment SHADOWS .env (load_dotenv override=False). If enrichment 401s or
#   the OS key looks wrong, export them explicitly first:
$env:OS_PLACES_API_KEY = "<valid OS key from .env>"
$env:OS_NGD_API_KEY    = "<same key>"
uvicorn backend.main:app --reload --port 8000

# 5. Frontend
cd frontend
npm install                          # package.json may have changed
npm run dev                          # http://localhost:5173
```

### Quick verification
```powershell
# Backend health
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing

# Constraints applied?
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "SELECT conname FROM pg_constraint WHERE conname IN ('uq_properties_ha_portfolio_ref','uq_blocks_ha_portfolio_name');"

# Demo portfolio scoped export works
#   GET /api/v1/portfolios/<portfolio_id>/export/doc-a
```

---

## 4. Known gotchas (carried from project memory)

- **OS Places API key shadowing** — a stale OS-environment `OS_PLACES_API_KEY`
  overrides `.env`. Symptom: enrichment fails / 401. Fix: export the key before
  launching uvicorn, or remove the stale User-scope env var.
- **Bedrock key shadowing** — same pattern with `AWS_ACCESS_KEY_ID`
  (`UnrecognizedClientException` on LLM extraction). Same fix.
- **`API_BASE_URL`** — `App.jsx` and `apiClient.js` must share one default
  (`http://localhost:8000`). `App.jsx` now imports it from apiClient — do not
  reintroduce a separate `|| ""` default or fire-documents loading silently breaks.
- **Enrichment is slow on the OS free tier** (~8 properties/min, can rate-limit).
  Auto-enrichment after SoV upload is capped at **50** properties
  (`upload_router.py`). For a demo, pre-enrich the data beforehand — don't run it live.
- **FRA/FRAEW auto-linking needs the block to exist** — the block must already be in
  `silver.blocks` (i.e. SoV uploaded + enrichment/block-detection run) for the
  filename match to resolve. Upload SoV → let enrichment finish → upload FRA/FRAEW.

---

## 5. Fresh-data reset (for testing/demo)

```powershell
docker exec -i platform-dev-postgres psql -U postgres -d platform_dev -c "BEGIN; TRUNCATE silver.fraew_features, silver.fra_features, silver.properties, silver.blocks, silver.portfolios CASCADE; COMMIT;"
```
Then upload a fresh SoV (auto-creates one clean portfolio) → wait for enrichment →
upload FRA/FRAEW PDFs (they self-link by filename).
