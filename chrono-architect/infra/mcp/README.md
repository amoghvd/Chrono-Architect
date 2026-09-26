# AWS MCP boundary

Chrono-Architect launches `awslabs.aws-api-mcp-server` over stdio and invokes only its
`call_aws` tool. The analyzer process sets `READ_OPERATIONS_ONLY=true`; the executor
sets it to `false` only after application-level approval validation.

Install `mcp-security-policy.json` at
`~/.aws/aws-api-mcp/mcp-security-policy.json`. IAM remains the authoritative boundary.
For API-driven execution, MCP elicitation may be unsupported by the client; therefore
the immutable proposal-hash approval is enforced by Chrono-Architect before the write
MCP process starts. Use separate `chrono-analyzer` and `chrono-executor` AWS profiles or
separate workload identities in production.
