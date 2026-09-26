# Hackathon demo

## Demo scope

The current implementation is a live, single-instance EC2 right-sizing slice. It
collects AWS evidence and compares a right-size proposal with no change. It does not
currently implement production deletion, idle scheduling, a TrueForge sandbox, or a
multi-agent topology DAG; present those as roadmap requirements, not completed features.

Use newly issued credentials from a local AWS profile. Never paste access keys, secret
keys, or session tokens into chat, `.env`, source control, or a presentation. The web
form's approver field is not authenticated; this local demo is not an identity system.

## Start the AWS Learner Lab demo

Repeat these steps for each lab session; temporary credentials expire. End the current
lab session and issue fresh credentials if they were exposed. Put the fresh values only
in your local AWS shared credentials file under a profile (for example
`[chrono-lab]` in `~/.aws/credentials`) and restrict file access. Do not put the values
in this repository or a command that will be saved in shell history.

Verify which AWS account the local profile uses:

```bash
aws sts get-caller-identity --profile chrono-lab
```

In `.env`, set the matching account ID and region, then point both gateways at the
profile for a full disposable-instance demo:

```dotenv
CHRONO_AWS_REGION=<learner-lab-region>
CHRONO_ALLOWED_ACCOUNT_IDS=["<account-id-from-sts>"]
CHRONO_ANALYZER_AWS_PROFILE=chrono-lab
CHRONO_EXECUTOR_AWS_PROFILE=chrono-lab
```

If you only want to demonstrate investigation and human review, do not configure a
working executor profile and do not click **Approve & execute**. For a full execution
demo, use a running, disposable instance: execution stops it, changes its type, and
restarts it. Use a target type with the same CPU architecture. Do not choose a
production, shared, Auto Scaling Group, Spot, or instance-store instance.

Check for candidate instances (read-only) and verify the opt-in tag:

```bash
aws ec2 describe-instances --profile chrono-lab --region <learner-lab-region> \
  --filters Name=tag:chrono-architect:managed,Values=true Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,Architecture,Tags]' \
  --output table
```

Start the app from the repository root:

```bash
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
uv run uvicorn chrono_architect.api:app --reload
```

Open `http://localhost:8000`, enter the selected instance ID and a compatible target
type, then run the investigation. Review policy checks, telemetry, costs, proposal
hash, and the audit trail. A failed critical check blocks execution. For an execution
demo, confirm the disposable instance and downtime with the team, type your approver
label, and click **Approve & execute**. Watch the instance stop, resize, restart, and
verify; then refresh the audit trail. The approval label is not authenticated by this
app.

To repeat the demo next time, start a new learner-lab session, renew the local profile,
confirm identity and region again, check that the disposable instance still exists and
has the opt-in tag, and restart the application. Never reuse an expired or disclosed
session credential.

## OpenAI and TrueForge status

This repository currently does not call OpenAI and does not use a TrueForge harness.
The AWS API MCP server is used for real AWS CLI evidence and actions; Python code makes
the cost calculations and enforces the approval/policy checks. The UI's `Compare`
stage compares those computed scenarios; it is not a sandbox simulation. Do not present
an LLM analysis, TrueForge run, or simulated blast-radius result as live functionality.

For a future integration, TrueForge would run the proposed change in an isolated
environment and return a verifiable simulation receipt before approval. An OpenAI
model could summarize the collected evidence or explain alternatives, but should not
set prices, bypass policy, select credentials, or execute mutations. Keep those actions
behind the existing deterministic policy and human approval gate.

1. Show the opted-in, disposable EC2 instance and its tags in AWS.
2. Start Chrono-Architect and show `/healthz` reports `real-mcp`.
3. Submit an investigation for a safe, standalone demo instance.
4. Show raw evidence summaries, missing-memory caveat, dependency checks, two scenarios,
   exact action/rollback plans, expiry, and proposal hash.
5. Attempt execution with a wrong hash; show HTTP 403 and zero write calls.
6. Only if the instance is disposable and downtime is acceptable, approve the exact
   plan. Show MCP stop/modify/start calls and EC2 state transitions. Otherwise stop at
   the approval gate and present the reviewed proposal without executing it.
7. Show status-check and optional application-health verification.
8. Show `/audit`, its valid hash chain, timestamps, state transitions, and MCP responses.
9. Show CloudTrail as an independent AWS control-plane record.

Use a non-production, EBS-backed instance tagged `chrono-architect:managed=true`. Never
use a hardcoded response in the live path. If AWS Pricing or metrics are unavailable,
show the fail-closed error instead of switching to demo data.
