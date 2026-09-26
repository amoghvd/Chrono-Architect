# Chrono-Architect

**A time machine for your cloud bill:** an evidence-driven AWS FinOps agent that can
investigate a real EC2 instance, compare futures, pause at a cryptographically bound
human checkpoint, act through the official AWS API MCP server, and verify the result.

For a comprehensive project presentation, see [Chrono-Architect Architecture Overview](docs/ARCHITECTURE.md) and the [Demo Runbook](docs/DEMO.md).

**Live deployment:** <https://chrono-architect.onrender.com> — see [`deployment.txt`](../deployment.txt) for the URL.


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

## Run locally

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/) (including `uvx`),
Node.js 20.19+ (or 22.12+) with npm, and AWS credentials. Live investigations need AWS
permissions for STS, EC2, CloudWatch, AWS Pricing, and Cost Explorer where enabled.
The backend launches `awslabs.aws-api-mcp-server` with `uvx`, so first use needs
network access to download that MCP server.

From the `Chrono-Architect` directory, install the Python backend and development
dependencies, then configure the environment:

```bash
uv sync --extra dev
cp .env.example .env
```

Edit `.env`: set your actual AWS region and account allowlist. The example account ID is
a placeholder and must be replaced. Configure the AWS profiles named by
`CHRONO_ANALYZER_AWS_PROFILE` and `CHRONO_EXECUTOR_AWS_PROFILE` in your AWS shared
config/credentials (or use your approved AWS SSO/workload identity setup). Apply the
read and write IAM policies under `infra/iam/` to their respective identities. Never
commit `.env` or put AWS access keys in source. The execution identity can change EC2
resources, so use a dedicated opted-in demo instance.

Install and build the React/Tailwind frontend. The build output is written into the
Python package and served by FastAPI on the same origin:

```bash
cd frontend
npm ci
npm run build
cd ..
uv run uvicorn chrono_architect.api:app --reload
```

Open [http://localhost:8000](http://localhost:8000). Check [http://localhost:8000/healthz](http://localhost:8000/healthz)
for API health. The first investigation must use a standalone, EBS-backed On-Demand
instance tagged `chrono-architect:managed=true`. Production-tagged resources also need
an HTTPS application health check. The UI shows actual returned evidence; it does not
mock savings or telemetry.

For frontend development with hot reload, leave the API running on port 8000 and use a
second terminal:

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/v1` and `/healthz`
to FastAPI. Re-run `npm run build` before starting the packaged FastAPI UI.

## Run tests

Run the complete Python suite (the project currently has 10 tests):

```bash
uv run pytest -q
```

Run an individual test module or all the current test modules explicitly:

```bash
uv run pytest tests/test_workflow_gate.py -q
uv run pytest tests/test_audit.py tests/test_gateway.py tests/test_policy.py tests/test_workflow_gate.py -q
```

Tests use fake/recording AWS gateways; they do not mutate cloud resources. A live UI
investigation is separate and talks to AWS. Do not approve a production or valuable
resource just to smoke-test the interface.

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

- `frontend/` — React, Vite, and Tailwind operator console source; build output is served by FastAPI
- `src/chrono_architect/` — MCP gateway, evidence agents, policy, workflow, API, audit
- `infra/iam/` — separate read/write policies
- `infra/mcp/` — MCP defense-in-depth policy
- `vendored-skills/` — AWS billing and compute skills, preserving upstream layout
- `tests/` — safety and deterministic-calculation tests
- `docs/DEMO.md` — hackathon demo runbook

## License note

Vendored AWS skill files originate from `aws/agent-toolkit-for-aws`; retain their
upstream Apache-2.0 license and NOTICE when redistributing.
