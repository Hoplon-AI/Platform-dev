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

6. AI Assistant Instructions (Cursor)
	•	This file is the source of truth
	•	Match existing architectural patterns
	•	Do not introduce new frameworks or paradigms
	•	Do not refactor unrelated code
	•	Ask for clarification only if requirements are ambiguous

If any conflict exists, this document takes precedence.
