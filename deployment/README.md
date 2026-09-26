# TrueFoundry / TrueForge deployment

Deploy the repository as a containerized service using the root `Dockerfile` and port
`8000`. The runtime command is already defined. Configure a persistent volume at
`/app/audit-data` or replace the file stores with your approved durable database/object
store before a production deployment.

Required non-secret environment variables are listed in `.env.example`. Supply AWS
identity via a TrueFoundry workspace integration/workload identity or mounted AWS
profile configuration; do not inject long-lived keys into source or image layers.

Recommended topology:

1. **Analyzer service/identity** — read-only IAM and `READ_OPERATIONS_ONLY=true`.
2. **Executor service/identity** — separately authenticated internal service with the
   executor policy. The current single-container hackathon slice supports separate AWS
   profiles; split services before multi-user production use.
3. **Approval identity** — put the `/execute` endpoint behind TrueFoundry authentication
   and propagate an authenticated approver identity. Do not trust a caller-supplied email
   as identity in production.
4. **Audit storage** — persistent and access-controlled; ship application logs and retain
   CloudTrail independently.
5. **MCP** — pin the tested AWS API MCP server revision corresponding to awslabs/mcp
   commit `1941e37b5d4d16c07814cbc340f6692e92ca1ee2` instead of `@latest` for the final demo.

A platform-specific service manifest is intentionally not fabricated because workspace,
cluster, image registry, and current TrueFoundry manifest schema are installation-specific.
Use the Dockerfile through your workspace UI/CLI and set `/healthz` as the health probe.
