# Cursor Rules — FastAPI + React + SQL Project

This document defines **mandatory coding standards, architectural constraints, and best practices**
for this repository.

Cursor (and other AI assistants) must **follow these rules by default** when generating,
editing, or refactoring code.

---

## 1. Project Philosophy

- Prefer **clarity over cleverness**
- Prefer **explicit over implicit**
- Optimize for **maintainability, correctness, and performance**
- Follow **industry-standard conventions**
- Minimize magic and hidden side effects

---

## 2. Backend — Python / FastAPI

### 2.1 General Python Standards

- Python version: **3.11+**
- Follow **PEP 8**
- Use **type hints everywhere**
- Prefer `pydantic` models over raw dicts
- Avoid global mutable state

Required tools:
- `ruff` (linting)
- `black` (formatting)
- `mypy` (type checking)

---

### 2.2 FastAPI Architecture

**Canonical directory structure:**

backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routes/
│   │   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── db/
│   │   ├── session.py
│   │   ├── migrations/
│   │   └── sql/
└── tests/

**Rules:**
- Routes must be **thin**
- Business logic belongs in **services**
- Database access belongs in **repositories**
- No SQL or ORM logic inside routes
- No HTTP concerns inside services

---

### 2.3 API Design

- RESTful endpoints
- Version all APIs (`/api/v1`)
- Use plural nouns for resources
- Consistent error envelopes
- Correct HTTP status codes

Standard error format:
```json
{
  "error": "validation_error",
  "message": "Invalid input",
  "details": {}
}


⸻

2.4 Dependency Injection
	•	Use FastAPI Depends
	•	Dependencies must be:
	•	Stateless
	•	Explicit
	•	Easily mockable in tests

Avoid:
	•	Implicit singletons
	•	Hidden imports
	•	Runtime service wiring

⸻

3. SQL & Database Standards

3.1 Database Engine
	•	Primary DB: PostgreSQL
	•	SQL dialect must be PostgreSQL-compatible
	•	Use asyncpg, SQLAlchemy (async), or equivalent

⸻

3.2 Schema Design
	•	Snake_case for:
	•	Table names
	•	Column names
	•	Plural table names (users, orders)
	•	Primary keys:
	•	id BIGSERIAL or UUID
	•	Foreign keys must be explicit
	•	Use NOT NULL by default
	•	Avoid nullable columns unless semantically required

⸻

3.3 Indexing & Performance
	•	Index all:
	•	Foreign keys
	•	Frequently filtered columns
	•	Composite indexes must reflect query patterns
	•	No premature optimization, but:
	•	Avoid full table scans
	•	Avoid SELECT *

⸻

3.4 SQL Query Rules
	•	Prefer parameterized queries
	•	Never concatenate user input into SQL
	•	Explicit column selection only
	•	Avoid implicit joins

Example (good):

SELECT id, email, created_at
FROM users
WHERE email = :email;

Example (bad):

SELECT *
FROM users
WHERE email = '${email}';


⸻

3.5 Migrations
	•	All schema changes must go through migrations
	•	Use Alembic
	•	Migrations must be:
	•	Reversible
	•	Idempotent
	•	No manual DB changes

Migration rules:
	•	One logical change per migration
	•	No data + schema changes mixed unless unavoidable

⸻

3.6 SQL Placement
	•	Raw SQL files go in:

backend/app/db/sql/


	•	Repositories may:
	•	Load SQL from files, or
	•	Use query builders / ORM
	•	Business logic must never live in SQL

⸻

3.7 Transactions
	•	Transactions must be:
	•	Explicit
	•	Scoped
	•	No implicit autocommit logic
	•	Services define transactional boundaries, not routes

⸻

3.8 Testing (Database)
	•	Use a separate test database
	•	Apply migrations in test setup
	•	Roll back after each test where possible
	•	No shared mutable state across tests

⸻

4. Frontend — React

4.1 General Standards
	•	React 18+
	•	TypeScript only
	•	Functional components only
	•	No class components

Required tools:
	•	ESLint
	•	Prettier
	•	TypeScript strict mode

⸻

4.2 Frontend Architecture

Canonical directory structure:

frontend/
├── src/
│   ├── components/
│   ├── features/
│   ├── hooks/
│   ├── services/
│   ├── pages/
│   ├── styles/
│   ├── utils/
│   └── types/

Rules:
	•	Shared UI in components
	•	Domain logic in features
	•	API calls in services
	•	No API calls in React components

⸻

4.3 State Management
	•	Server state:
	•	React Query / TanStack Query
	•	UI state:
	•	Local component state
	•	Avoid global state unless necessary

⸻

4.4 API Communication
	•	Single API client abstraction
	•	Typed request/response contracts
	•	Centralized error handling
	•	No direct fetch usage in components

⸻

4.5 Styling
	•	CSS Modules or styled-components
	•	No complex inline styles
	•	Centralized design tokens

⸻

4.6 Testing (Frontend)
	•	Unit tests: vitest or jest
	•	Component tests: @testing-library/react
	•	Test behavior, not implementation details

⸻

5. Cross-Cutting Concerns

5.1 Naming
	•	Domain-driven names
	•	No meaningless abstractions
	•	Avoid utils without domain context

⸻

5.2 Error Handling
	•	Fail fast
	•	Never swallow errors
	•	Log with structured context
	•	User-safe messages at system boundaries

⸻

5.3 Security
	•	No secrets in source code
	•	Environment variables via config layer
	•	Validate all external inputs
	•	Assume client input is hostile

⸻

6. AWS Architecture & Infrastructure as Code (AWS CDK in Python)

6.1 Reference Standard
	•	Align infrastructure decisions with the AWS Well-Architected Framework pillars:
	•	Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization
	•	Prefer managed services over self-managed infrastructure where possible

⸻

6.2 Environments & Accounts
	•	Use separate AWS accounts (recommended) for: dev / staging / prod
	•	Never deploy dev resources into prod accounts (and vice versa)
	•	Environment parity: same architecture across envs, only configuration differs
	•	All resources must be tagged (at minimum):
	•	app, env, owner, cost_center, data_classification

⸻

6.3 Networking (VPC) & Edge
	•	Prefer a single VPC per environment with clear subnet separation:
	•	Public subnets: edge/ingress only (ALB/NLB, NAT if required)
	•	Private subnets: application compute (ECS/Lambda if VPC-attached), internal services
	•	Isolate databases into private subnets; no public database access
	•	Prefer VPC endpoints (S3, ECR, CloudWatch, Secrets Manager, etc.) to reduce NAT reliance
	•	Inbound traffic should be protected by AWS WAF (when Internet-exposed)
	•	Use Security Groups as the primary east-west firewall; keep rules minimal and explicit

⸻

6.4 Identity, Secrets, and Encryption
	•	Least privilege IAM everywhere (no wildcard actions/resources unless unavoidable)
	•	No long-lived AWS access keys for CI/CD:
	•	Use OIDC to assume roles from GitHub Actions (or equivalent) into AWS
	•	All secrets in AWS Secrets Manager (preferred) or SSM Parameter Store:
	•	Never store secrets in Git, in `.env` committed files, or in CDK context
	•	Encrypt data at rest using AWS KMS (S3, RDS, logs where supported)
	•	Encrypt in transit (TLS) for all service-to-service and client-to-service communication

⸻

6.5 Compute & Integration Patterns
	•	Default hosting options for the API:
	•	ECS Fargate behind an ALB (recommended for FastAPI services)
	•	Lambda + API Gateway (only if the workload fits Lambda constraints)
	•	Use queues and events for decoupling:
	•	SQS for asynchronous processing and backpressure
	•	EventBridge for event routing and fan-out
	•	Avoid tight coupling via synchronous service-to-service calls
	•	Auto-scaling must be enabled for production compute (CPU/memory/queue depth-based)

⸻

6.6 Data Stores, Backups, and Durability
	•	PostgreSQL on Amazon RDS (Multi-AZ in staging/prod)
	•	Backups are mandatory:
	•	Automated backups enabled, with retention appropriate to the environment
	•	Enable PITR where applicable/required
	•	S3 buckets:
	•	Block public access enabled
	•	Default encryption enabled
	•	Lifecycle policies for cost management (archival/expiration as appropriate)
	•	Treat schema migrations as part of the release process (CI/CD), not a manual step

⸻

6.7 Observability & Operations
	•	All services must emit structured logs and metrics:
	•	CloudWatch Logs for logs, CloudWatch metrics/alarms for key signals
	•	Standardize on request IDs / correlation IDs across services
	•	Define SLO-relevant alarms (availability, latency, error rate) for production
	•	Prefer OpenTelemetry-compatible instrumentation for tracing (when used)

⸻

6.8 Infrastructure as Code Rules (AWS CDK — Python)
	•	All AWS resources must be created and changed via CDK (no console-driven drift)
	•	CDK code quality:
	•	Use typed constructs and explicit names where it improves operability
	•	Prefer composable Constructs over monolithic Stacks
	•	One stack per deployable boundary (e.g., networking, data, compute, observability)
	•	Configuration:
	•	Use per-environment config (accounts/regions, toggles, sizes) outside code
	•	Do not hardcode account IDs, ARNs, or secrets into CDK source
	•	Safety:
	•	Run `cdk diff` in CI for every change; require approval for prod deployments
	•	Enable termination protection for critical prod stacks (as appropriate)
	•	Guardrails:
	•	Use `cdk-nag` (or equivalent) to enforce security best practices and catch unsafe defaults
	•	Prefer explicit IAM policies over broad managed policies
	•	Testing:
	•	Use CDK assertions tests for key resources (e.g., encryption, public access, logging)

⸻

6.9 CI/CD Expectations for Infra
	•	CI must include (at minimum):
	•	CDK synth
	•	Static checks (lint/type-check)
	•	Unit tests (including CDK assertions tests)
	•	CDK diff (recorded as build output)
	•	CDK deploy to dev/staging can be automated; production requires a manual approval gate

⸻

7. AI Assistant Instructions (Cursor)
	•	This file is the source of truth
	•	Match existing architectural patterns
	•	Do not introduce new frameworks or paradigms
	•	Do not refactor unrelated code
	•	Ask for clarification only if requirements are ambiguous

If any conflict exists, this document takes precedence.
