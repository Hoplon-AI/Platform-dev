#!/usr/bin/env python3
"""
Create a single Jira issue (no external dependencies).

Auth: Jira Cloud API token (Basic auth with email + token).
Uses Jira REST API v2: POST /rest/api/2/issue

Required env vars:
- JIRA_SERVER (e.g. https://equirisk.atlassian.net)
- JIRA_EMAIL
- JIRA_API_TOKEN
- JIRA_PROJECT_KEY (e.g. KAN)

Optional env vars:
- JIRA_ISSUE_TYPE (default: Task)
- JIRA_PRIORITY (default: High)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _basic_auth_header(email: str, api_token: str) -> str:
    raw = f"{email}:{api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def create_issue(*, server: str, email: str, api_token: str, project_key: str) -> tuple[str, str]:
    issue_type = os.getenv("JIRA_ISSUE_TYPE", "Task")
    priority = os.getenv("JIRA_PRIORITY", "High")

    summary = "Bootstrap initial AWS infrastructure (CDK, networking, security, CI/CD)"
    description = "\n".join(
        [
            "## Goal",
            "Bootstrap the initial AWS infrastructure using AWS CDK (Python) so the platform can deploy safely across environments.",
            "",
            "## Scope (high level)",
            "- Account/environment strategy (dev/staging/prod) and tagging standard",
            "- VPC baseline (public/private subnets), routing, VPC endpoints where appropriate",
            "- Security baseline: IAM roles, least privilege, KMS, Secrets Manager, S3 bucket policies",
            "- Compute baseline for backend (ECS Fargate + ALB) or equivalent agreed pattern",
            "- Data baseline (RDS Postgres) with backups and encryption",
            "- Observability baseline (CloudWatch logs/metrics/alarms), structured logging expectations",
            "- CI/CD for infrastructure: synth, diff, deploy with approval gate for prod",
            "",
            "## Acceptance criteria",
            "- CDK app exists and can `synth` and `diff` cleanly in CI",
            "- Dev environment deploy works end-to-end from CI/CD with no console steps",
            "- Core resources created with encryption at rest and least-privilege IAM",
            "- Logging and basic alarms are in place for deployed services",
            "- Documented runbook: deploy, rollback, and break-glass access process",
            "",
            "## Notes",
            "- Follow repo rules: AWS Well-Architected + IaC guardrails (cdk-nag, no secrets in code).",
        ]
    )

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "labels": ["aws", "infrastructure", "cdk", "iac"],
        }
    }

    url = server.rstrip("/") + "/rest/api/2/issue"
    req = urllib.request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": _basic_auth_header(email, api_token),
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            issue_key = data["key"]
            browse_url = server.rstrip("/") + "/browse/" + issue_key
            return issue_key, browse_url
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira API error: HTTP {e.code}\n{detail}") from e


def main() -> int:
    try:
        server = _require_env("JIRA_SERVER")
        email = _require_env("JIRA_EMAIL")
        api_token = _require_env("JIRA_API_TOKEN")
        project_key = _require_env("JIRA_PROJECT_KEY")
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 2

    issue_key, browse_url = create_issue(
        server=server, email=email, api_token=api_token, project_key=project_key
    )
    print(issue_key)
    print(browse_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

