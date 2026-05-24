# GitHub Actions Agent Deployment

This repo deploys the agent service to the EC2 checkout at `/home/ec2-user/brevixai-agents` after the `Benchmark Quality Gate` workflow succeeds for an internal pull request or a push to `main`.

## Required Secrets

Configure these in GitHub repository settings under `Secrets and variables` -> `Actions`.

| Secret | Required | Value |
| --- | --- | --- |
| `AGENT_EC2_HOST` | yes | Public IP or public DNS name for the agent EC2 instance. |
| `AGENT_EC2_SSH_KEY` | yes | Private SSH key that can log in to the agent EC2 instance. |
| `AGENT_EC2_USER` | no | SSH user. Defaults to `ec2-user`. |
| `AGENT_DEPLOY_PATH` | no | Absolute repo path on EC2. Defaults to `/home/ec2-user/brevixai-agents`. |

Use the EC2 public IP for `AGENT_EC2_HOST` when using GitHub-hosted runners. Private `172.31.x.x` addresses only work from a self-hosted runner inside the VPC.

## EC2 Requirements

The agent EC2 instance must already have:

- The repo cloned at the deploy path.
- A valid `.env` file in the deploy path.
- Docker and Docker Compose available to the SSH user.
- The SSH public key matching `AGENT_EC2_SSH_KEY` in `/home/ec2-user/.ssh/authorized_keys`.

The workflow refuses to deploy if tracked local changes are present in the EC2 checkout. Keep environment-only changes in `.env`, which is not tracked.

## Deployment Behavior

For internal pull requests and pushes to `main`, deployment runs only after `Benchmark Quality Gate` succeeds. The workflow SSHes into EC2, fetches from `origin`, checks out the exact commit in detached HEAD mode, rebuilds the Docker Compose service, recreates the container, and verifies `http://127.0.0.1:8010/health`.

Forked pull requests are not deployed because repository secrets are not safe to expose to untrusted code.

Manual deployments can be run from the `Deploy Agent Service` workflow with an optional branch, tag, or commit SHA.
