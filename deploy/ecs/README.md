# ECS Deployment

This directory contains ECS/Fargate starter configuration for the private Brevix agent service.

## Production requirements

The following environment variables **must** be set before starting the service in production.
The service will refuse to start or return 503 if these are absent.

| Variable | Why it is required |
|---|---|
| `ORCHESTRATOR_API_TOKEN` (alias `BREVIX_AGENT_SERVICE_KEY`) | Bearer token for all `/agent/run` calls.  Missing → every request returns 503. |
| `ORCHESTRATOR_ALLOWED_ORIGINS` | Comma-separated CORS origin allowlist.  Missing in `APP_ENV=production\|prod` → service refuses to start rather than fall back to `["*"]`. |

The following variables are **required when the Postgres checkpointer is enabled**:

| Variable | Notes |
|---|---|
| `ORCHESTRATOR_CHECKPOINTER=postgres` | Activates Postgres-backed LangGraph state persistence. |
| `DATABASE_URL` | Postgres connection string (e.g. `postgresql+asyncpg://user:pass@host:5432/db`). |
| psycopg2-binary or psycopg (asyncpg) | Python packages must be installed: `pip install psycopg2-binary` or `pip install psycopg[binary]`. |

## Human-approval gates

The following action types **always require human approval** and will never execute autonomously.
This is enforced by the `action_gate` graph node and cannot be bypassed at runtime:

- `send_email` — outbound email delivery
- `finalize_case` — irreversible case state transition
- `update_case` — case record mutation
- `draft_case` — case creation draft
- `draft_email` — email draft creation
- `flag_transaction` — transaction flag mutation

## Deployment assumptions

- The service runs in private subnets.
- The Laravel API reaches the service through an internal load balancer or service discovery.
- `BREVIX_AGENT_SERVICE_KEY` and `BREVIX_LARAVEL_AGENT_TOOL_KEY` are loaded from SSM Parameter Store or Secrets Manager.
- The task role does not need database permissions because the agent service never connects directly to Postgres (unless `ORCHESTRATOR_CHECKPOINTER=postgres` is set).

Typical flow:

```bash
aws ecr create-repository --repository-name brevixai-agent-service
docker build -t brevixai-agent-service .
docker tag brevixai-agent-service:latest <account-id>.dkr.ecr.<region>.amazonaws.com/brevixai-agent-service:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/brevixai-agent-service:latest
aws ecs register-task-definition --cli-input-json file://deploy/ecs/task-definition.json
aws ecs create-service --cli-input-json file://deploy/ecs/service.json
```
