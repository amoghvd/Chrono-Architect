from __future__ import annotations

import asyncio
import ipaddress
import socket
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .analysis import estimate_cost
from .audit import AuditLog
from .aws_evidence import EvidenceCollector
from .config import Settings
from .mcp_gateway import AwsGateway, McpError
from .models import ActionStep, Approval, CheckStatus, DependencyCheck, Proposal, RunState, Scenario
from .policy import (
    PolicyViolation,
    assert_no_drift,
    bind_hash,
    validate_approval,
)


class ProposalStore:
    def __init__(self, directory: Path):
        self.directory = directory / "proposals"
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, proposal: Proposal) -> None:
        (self.directory / f"{proposal.run_id}.json").write_text(proposal.model_dump_json(indent=2))

    def get(self, run_id: str) -> Proposal:
        path = self.directory / f"{run_id}.json"
        if not path.exists():
            raise KeyError(run_id)
        return Proposal.model_validate_json(path.read_text())


class ChronoArchitect:
    def __init__(self, read_gateway: AwsGateway, write_gateway: AwsGateway, settings: Settings):
        self.settings = settings
        self.reader = EvidenceCollector(read_gateway, settings.aws_region)
        self.writer = write_gateway
        self.audit = AuditLog(settings.audit_dir)
        self.store = ProposalStore(settings.audit_dir)

    async def investigate(self, instance_id: str, target_type: str,
                          health_check_url: str | None = None) -> Proposal:
        run_id = str(uuid.uuid4())
        self.audit.append(run_id, "investigation_started", {"instance_id": instance_id}, RunState.INVESTIGATING)
        snap = await self.reader.snapshot(instance_id)
        if self.settings.allowed_account_ids and snap.account_id not in self.settings.allowed_account_ids:
            raise PolicyViolation("AWS account is not allowlisted")
        production = snap.tags.get("Environment", "").lower() in {"prod", "production"}
        checks = await self.reader.checks(snap, target_type, self.settings.managed_tag_key, self.settings.managed_tag_value)
        checks.append(DependencyCheck(
            name="production-health-check",
            status=CheckStatus.PASS if (not production or health_check_url) else CheckStatus.FAIL,
            explanation="Production workloads require an external application health check",
        ))
        metrics = await self.reader.metrics(instance_id, self.settings.analysis_days)
        historical_cost = None
        cost_history_caveat = None
        try:
            historical_cost = await self.reader.resource_cost(instance_id, self.settings.analysis_days)
        except McpError as exc:
            cost_history_caveat = f"Cost Explorer resource evidence unavailable: {exc}"
            self.audit.append(run_id, "cost_explorer_unavailable", {"error": str(exc)})
        current_price, target_price = await asyncio.gather(
            self.reader.hourly_price(snap.instance_type, snap.architecture),
            self.reader.hourly_price(target_type, snap.architecture),
        )
        caveats = [
            "Public On-Demand price; realized savings may differ under Savings Plans, RIs, credits, or private pricing.",
            "Memory utilization is unknown unless CloudWatch Agent metrics are separately configured.",
            "Cost Explorer billing data is delayed; immediate verification proves configuration, not realized savings.",
        ]
        if cost_history_caveat:
            caveats.append(cost_history_caveat)
        cost = estimate_cost(current_price, target_price, basis="AWS Price List API", confidence="medium", caveats=caveats)
        uncertainty = [c.explanation for c in checks if c.status == CheckStatus.UNKNOWN] + caveats
        risk = min(100, 20 + 20 * len([c for c in checks if c.status != CheckStatus.PASS]) + (20 if production else 0))
        no_change_cost = estimate_cost(current_price, current_price, basis="AWS Price List API", confidence="medium", caveats=caveats)
        scenarios = [
            Scenario(name="no-change", target_instance_type=snap.instance_type, estimated_cost=no_change_cost,
                     risk_score=0, blast_radius=[], downtime_required=False, reversible=True),
            Scenario(name="right-size", target_instance_type=target_type, estimated_cost=cost,
                     risk_score=risk, blast_radius=[snap.instance_id, *snap.eni_ids, *snap.volume_ids],
                     downtime_required=True, reversible=True, uncertainty=uncertainty),
        ]
        actions = [
            ActionStep(operation="stop-instances", parameters={"instance_ids": [instance_id]}),
            ActionStep(operation="modify-instance-attribute", parameters={"instance_id": instance_id, "instance_type": target_type}),
            ActionStep(operation="start-instances", parameters={"instance_ids": [instance_id]}),
        ]
        rollback = [
            ActionStep(operation="stop-instances", parameters={"instance_ids": [instance_id]}),
            ActionStep(operation="modify-instance-attribute", parameters={"instance_id": instance_id, "instance_type": snap.instance_type}),
            ActionStep(operation="start-instances", parameters={"instance_ids": [instance_id]}),
        ]
        now = datetime.now(UTC)
        proposal = bind_hash(Proposal(
            run_id=run_id, created_at=now,
            expires_at=now + timedelta(minutes=self.settings.approval_ttl_minutes),
            instance=snap, target_instance_type=target_type,
            evidence_window_days=self.settings.analysis_days, metrics=metrics,
            historical_cost=historical_cost, checks=checks,
            scenarios=scenarios, selected_scenario="right-size", action_plan=actions,
            rollback_plan=rollback, health_check_url=health_check_url, production=production,
        ))
        self.store.save(proposal)
        self.audit.append(run_id, "proposal_created", {"proposal_hash": proposal.proposal_hash}, RunState.AWAITING_APPROVAL)
        return proposal

    async def execute(self, run_id: str, approval: Approval) -> dict:
        proposal = self.store.get(run_id)
        validate_approval(proposal, approval)
        self.audit.append(run_id, "approval_validated", approval.model_dump(mode="json"), RunState.APPROVED)
        current = await self.reader.snapshot(proposal.instance.instance_id)
        assert_no_drift(proposal.instance.raw_fingerprint, current.raw_fingerprint)
        self.audit.append(run_id, "preconditions_rechecked", {}, RunState.PRECONDITIONS_RECHECKED)
        instance_id = proposal.instance.instance_id
        try:
            await self._mutate(run_id, f"aws ec2 stop-instances --instance-ids {instance_id} --region {proposal.instance.region}", RunState.STOP_REQUESTED)
            await self._wait_state(instance_id, "stopped")
            self.audit.append(run_id, "instance_stopped", {}, RunState.STOPPED)
            await self._mutate(run_id, f"aws ec2 modify-instance-attribute --instance-id {instance_id} --instance-type Value={proposal.target_instance_type} --region {proposal.instance.region}", RunState.TYPE_CHANGED)
            await self._mutate(run_id, f"aws ec2 start-instances --instance-ids {instance_id} --region {proposal.instance.region}", RunState.START_REQUESTED)
            await self._wait_state(instance_id, "running")
            self.audit.append(run_id, "instance_running", {}, RunState.RUNNING)
            verified = await self._verify(proposal)
            if not verified:
                raise RuntimeError("Post-change verification failed")
            self.audit.append(run_id, "verified", {"target_type": proposal.target_instance_type}, RunState.VERIFIED)
            return {"run_id": run_id, "state": RunState.VERIFIED, "audit_chain_valid": self.audit.verify(run_id)}
        except Exception as exc:
            self.audit.append(run_id, "execution_failed", {"error": str(exc)}, RunState.FAILED)
            if approval.allow_rollback:
                await self._rollback(proposal)
                self.audit.append(run_id, "rolled_back", {}, RunState.ROLLED_BACK)
                return {"run_id": run_id, "state": RunState.ROLLED_BACK, "error": str(exc)}
            self.audit.append(run_id, "manual_intervention_required", {"rollback_approved": False}, RunState.MANUAL_INTERVENTION)
            raise

    async def _mutate(self, run_id: str, command: str, state: RunState) -> None:
        allowed = ("aws ec2 stop-instances ", "aws ec2 modify-instance-attribute ", "aws ec2 start-instances ")
        if not command.startswith(allowed):
            raise PolicyViolation("Executor rejected non-allowlisted command")
        result = await self.writer.call_cli(command)
        self.audit.append(run_id, "mcp_mutation", {"command": command.split(" --")[0], "response": result}, state)

    async def _wait_state(self, instance_id: str, desired: str, attempts: int = 40) -> None:
        for _ in range(attempts):
            snap = await self.reader.snapshot(instance_id)
            if snap.state == desired:
                return
            await asyncio.sleep(15)
        raise TimeoutError(f"Instance did not reach {desired}")

    async def _verify(self, proposal: Proposal) -> bool:
        snap = await self.reader.snapshot(proposal.instance.instance_id)
        if snap.state != "running" or snap.instance_type != proposal.target_instance_type:
            return False
        cmd = f"aws ec2 describe-instance-status --instance-ids {snap.instance_id} --include-all-instances --region {snap.region}"
        status = await self.reader.gateway.call_cli(cmd)
        items = status.get("InstanceStatuses", [])
        if not items:
            return False
        checks_ok = all(items[0].get(k, {}).get("Status") == "ok" for k in ("InstanceStatus", "SystemStatus"))
        if not checks_ok:
            return False
        if proposal.health_check_url:
            return await self._safe_health_check(proposal.health_check_url)
        return True

    async def _safe_health_check(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise PolicyViolation("Health check must be an HTTPS URL")
        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443)
        for entry in addresses:
            ip = ipaddress.ip_address(entry[4][0])
            if not ip.is_global:
                raise PolicyViolation("Health check must resolve only to public addresses")
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
                response = await client.get(url)
            return 200 <= response.status_code < 400
        except httpx.HTTPError:
            return False

    async def _rollback(self, proposal: Proposal) -> None:
        iid, region, original = proposal.instance.instance_id, proposal.instance.region, proposal.instance.instance_type
        await self.writer.call_cli(f"aws ec2 stop-instances --instance-ids {iid} --region {region}")
        await self._wait_state(iid, "stopped")
        await self.writer.call_cli(f"aws ec2 modify-instance-attribute --instance-id {iid} --instance-type Value={original} --region {region}")
        await self.writer.call_cli(f"aws ec2 start-instances --instance-ids {iid} --region {region}")
        await self._wait_state(iid, "running")
