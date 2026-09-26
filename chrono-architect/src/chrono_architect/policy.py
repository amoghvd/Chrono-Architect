from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from .models import Approval, CheckStatus, Proposal

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+=,@-]{0,255}$")
ALLOWED_MUTATIONS = {
    "ec2 stop-instances",
    "ec2 modify-instance-attribute",
    "ec2 start-instances",
}

class PolicyViolation(RuntimeError):
    pass


def canonical_data(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude={"proposal_hash"})
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_data(value)).hexdigest()


def bind_hash(proposal: Proposal) -> Proposal:
    return proposal.model_copy(update={"proposal_hash": sha256(proposal)})


def validate_identifier(value: str, label: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise PolicyViolation(f"Unsafe {label}")
    return value


def validate_proposal(proposal: Proposal, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if proposal.expires_at <= now:
        raise PolicyViolation("Proposal has expired")
    if proposal.production and not proposal.health_check_url:
        raise PolicyViolation("Production changes require an application health check")
    blocking = [c for c in proposal.checks if c.critical and c.status != CheckStatus.PASS]
    if blocking:
        raise PolicyViolation("Critical checks unresolved: " + ", ".join(c.name for c in blocking))
    for step in proposal.action_plan:
        if f"{step.service} {step.operation}" not in ALLOWED_MUTATIONS:
            raise PolicyViolation(f"Mutation not allowlisted: {step.service} {step.operation}")
    expected = sha256(proposal)
    if proposal.proposal_hash != expected:
        raise PolicyViolation("Proposal hash is absent or invalid")


def validate_approval(proposal: Proposal, approval: Approval, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    validate_proposal(proposal, now)
    if approval.decision != "approve":
        raise PolicyViolation("Proposal was not approved")
    if approval.expires_at <= now or approval.approved_at > now:
        raise PolicyViolation("Approval is expired or not yet valid")
    if approval.expires_at > proposal.expires_at:
        raise PolicyViolation("Approval cannot outlive proposal")
    if approval.proposal_hash != proposal.proposal_hash:
        raise PolicyViolation("Approval is not bound to this proposal")


def assert_no_drift(before_fingerprint: str, current_fingerprint: str) -> None:
    if before_fingerprint != current_fingerprint:
        raise PolicyViolation("Resource state drifted after approval")
