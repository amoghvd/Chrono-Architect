# Hackathon demo

1. Show the opted-in EC2 instance and its tags in AWS.
2. Start Chrono-Architect and show `/healthz` reports `real-mcp`.
3. Submit an investigation for a safe, standalone demo instance.
4. Show raw evidence summaries, missing-memory caveat, dependency checks, two scenarios,
   exact action/rollback plans, expiry, and proposal hash.
5. Attempt execution with a wrong hash; show HTTP 403 and zero write calls.
6. Approve the exact plan. Show MCP stop/modify/start calls and EC2 state transitions.
7. Show status-check and optional application-health verification.
8. Show `/audit`, its valid hash chain, timestamps, state transitions, and MCP responses.
9. Show CloudTrail as an independent AWS control-plane record.

Use a non-production, EBS-backed instance tagged `chrono-architect:managed=true`. Never
use a hardcoded response in the live path. If AWS Pricing or metrics are unavailable,
show the fail-closed error instead of switching to demo data.
