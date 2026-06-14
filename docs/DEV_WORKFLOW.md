# Development & Release Workflow

Branch model: **`feature/*` → `staging` → `main` → `production`**. Changes only ever flow
upward; each tier is more stable than the one below it.

| Branch        | Role                                          | Deploys to            |
|---------------|-----------------------------------------------|-----------------------|
| `feature/*`   | One branch per change. Branch off `staging`.  | nothing (local only)  |
| `staging`     | Integration / QA. PRs land here first.        | nothing yet (local)   |
| `main`        | Stable, reviewed. Squash-merged from staging. | nothing (CI only)     |
| `production`  | Release branch.                               | live CloudFront (TODO)|

> The `production` → CloudFront auto-deploy pipeline is **not built yet** — see
> [Production deploy (pending)](#production-deploy-pending). Until then, the live site is
> updated by a manual build + upload.

---

## 1. Start a feature

```powershell
git checkout staging
git pull
git checkout -b feature/short-description
```

## 2. Run locally

**Services + backend** (set env vars first — see `CLAUDE.md` › Environment Variables):

```powershell
cd C:\EquiRiskAI\Platform-dev
docker compose up -d                 # Postgres + LocalStack
.\venv\Scripts\Activate
uvicorn backend.main:app --reload --port 8000
```
API docs: http://127.0.0.1:8000/docs

**Frontend** (separate terminal):

```powershell
cd C:\EquiRiskAI\Platform-dev\frontend
npm install                          # first time / after dep changes
npm run dev                          # http://localhost:5173
```

Local API wiring is automatic:
- `npm run dev` reads `frontend/.env` → `VITE_API_BASE_URL=http://127.0.0.1:8000` (local backend).
- `npm run build` reads `frontend/.env.production` → the CloudFront URL (prod backend).

You do **not** need to edit env files to test locally.

## 3. Test before pushing

```powershell
# Frontend
cd frontend
npm run lint
npm run build                        # catches prod build errors early

# Backend
cd ..
python -m pytest tests/ -v
```

Manual smoke test: log in, upload a SoV, check the map renders, export Doc A / Doc B.

## 4. Promote upward

```powershell
# feature -> staging
git push -u origin feature/short-description
gh pr create --base staging --head feature/short-description
# review, then merge (squash)

# staging -> main  (clean, single commit)
gh pr create --base main --head staging --title "Promote staging to main: <summary>"
# wait for "Lint and Test" CI to pass, review, then SQUASH MERGE

# main -> production  (release; fast-forward only)
git checkout production
git pull
git merge --ff-only main
git push
git tag -a v1.x.x -m "Release v1.x.x"   # optional but recommended
git push --tags
```

**Rules**
- Never commit directly to `main` or `production`.
- `main` only receives squash PRs from `staging`.
- `production` only fast-forwards from `main`.

---

## Production deploy (pending)

There is currently **no automated frontend deploy**. To wire it up later (push to
`production` → live CloudFront), we need:

1. Valid AWS credentials for the deploy account `025215344919` (eu-west-1) — the keys in
   `.env` are Bedrock-only (eu-west-2) and were invalid at last check.
2. The frontend **S3 bucket name** and **CloudFront distribution ID** behind
   `d16062fpplraah.cloudfront.net` (`aws cloudfront list-distributions`).

Planned pipeline (`.github/workflows/frontend-deploy.yml`, triggers on push to `production`):
`npm ci` → `npm run build` → `aws s3 sync dist/ s3://<bucket> --delete` →
`aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`.

Until that exists, deploy manually:

```powershell
cd frontend
npm run build
aws s3 sync dist/ s3://<bucket> --delete
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```
