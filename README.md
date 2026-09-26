# Chrono-Architect

**A time machine for your cloud bill:** an evidence-driven AWS FinOps agent that can
investigate a real EC2 instance, compare futures, pause at a cryptographically bound
human checkpoint, act through the official AWS API MCP server, and verify the result.

## What is real

No AWS response, price, metric, or action is hardcoded. The production gateway launches
`awslabs.aws-api-mcp-server` and invokes its `call_aws` tool. Test fixtures use an
explicit `RecordingGateway` that fails closed when a response is absent.

The first vertical slice safely right-sizes one explicitly selected, standalone,
EBS-backed On-Demand EC2 instance:

`investigate → evidence → scenarios → approval → drift recheck → stop → modify → start → verify`

## Safety invariants

- Read worker has `READ_OPERATIONS_ONLY=true`; write worker starts only for execution.
- Resource requires `chrono-architect:managed=true`.
- ASG, Spot, instance-store, architecture mismatch, and unresolved critical checks block action.
- Production resources require an external health URL.
- Approval is bound to the canonical proposal SHA-256 and expires.
- Resource fingerprint is re-read after approval; drift invalidates it.
- Only stop, modify instance type, and start are represented by the action schema.
- Rollback occurs only when the approver sets `allow_rollback=true`.
- Audit records are append-only JSONL with a hash chain.
- Prices and calculations use AWS evidence and Python `Decimal`; the model does no arithmetic.

## Quick start

Prerequisites: Python 3.11+, `uvx`, AWS credentials, and access to AWS Pricing,
CloudWatch, EC2, Auto Scaling, STS, and Cost Explorer/Compute Optimizer as enabled.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn chrono_architect.api:app --reload
```

Analyze an opted-in instance:

```bash
curl -X POST http://localhost:8000/v1/investigations \
  -H 'content-type: application/json' \
  -d '{"instance_id":"i-0123456789abcdef0","target_instance_type":"m6i.large","health_check_url":"https://service.example/health"}'
```

Review the complete proposal. Then submit an independently authenticated approval whose
`proposal_hash` exactly matches the proposal and whose expiry does not exceed it:

```bash
curl -X POST http://localhost:8000/v1/runs/RUN_ID/execute \
  -H 'content-type: application/json' \
  -d '{"decision":"approve","proposal_hash":"HASH","approver":"alice@example.com","approved_at":"2026-01-01T12:00:00Z","expires_at":"2026-01-01T12:15:00Z","allow_rollback":false}'
```

## AWS setup

1. Apply `infra/iam/analyzer-policy.json` to the analyzer identity.
2. Customize region/account in `infra/iam/executor-policy.json`, then apply it to a
   separate executor identity.
3. Install `infra/mcp/mcp-security-policy.json` for the MCP server.
4. Set the two profile names in `.env`; never put access keys in this repository.
5. Tag only demo resources intentionally placed under agent control.

## Evidence limitations

List pricing is not guaranteed realized savings. Savings Plans, Reserved Instances,
private rates, credits, and billing allocation can change the result. Native EC2 metrics
do not include memory. Chrono-Architect records both limitations and blocks rather than
inventing missing evidence. Immediate verification cannot prove billing savings because
Cost Explorer is delayed.

## Repository map

- `src/chrono_architect/` — MCP gateway, evidence agents, policy, workflow, API, audit
- `infra/iam/` — separate read/write policies
- `infra/mcp/` — MCP defense-in-depth policy
- `vendored-skills/` — AWS billing and compute skills, preserving upstream layout
- `tests/` — safety and deterministic-calculation tests
- `docs/DEMO.md` — hackathon demo runbook

## License note

Vendored AWS skill files originate from `aws/agent-toolkit-for-aws`; retain their
upstream Apache-2.0 license and NOTICE when redistributing.
