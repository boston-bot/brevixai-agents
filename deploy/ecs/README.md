# ECS Deployment

This directory contains ECS/Fargate starter configuration for the private Brevix agent service.

Deployment assumptions:

- The service runs in private subnets.
- The Laravel API reaches the service through an internal load balancer or service discovery.
- `BREVIX_AGENT_SERVICE_KEY` and `BREVIX_LARAVEL_AGENT_TOOL_KEY` are loaded from SSM Parameter Store or Secrets Manager.
- The task role does not need database permissions because the agent service never connects directly to Postgres.

Typical flow:

```bash
aws ecr create-repository --repository-name brevixai-agent-service
docker build -t brevixai-agent-service .
docker tag brevixai-agent-service:latest <account-id>.dkr.ecr.<region>.amazonaws.com/brevixai-agent-service:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/brevixai-agent-service:latest
aws ecs register-task-definition --cli-input-json file://deploy/ecs/task-definition.json
aws ecs create-service --cli-input-json file://deploy/ecs/service.json
```
