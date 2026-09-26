from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from chrono_architect.analysis import estimate_cost
from chrono_architect.models import (
    ActionStep,
    Approval,
    CheckStatus,
    CostEstimate,
    DependencyCheck,
    InstanceSnapshot,
    Proposal,
    Scenario,
)
from chrono_architect.policy import PolicyViolation, bind_hash, validate_approval, validate_proposal

NOW = datetime.now(UTC)

def make_proposal(**updates):
    snap = InstanceSnapshot(account_id="123456789012", region="us-east-1", instance_id="i-12345678",
        instance_type="m5.large", state="running", architecture="x86_64", root_device_type="ebs",
        tags={"chrono-architect:managed":"true"}, raw_fingerprint="abc")
    cost = estimate_cost(Decimal("0.096"), Decimal("0.048"), basis="test", confidence="medium", caveats=[])
    values = {
        "run_id": "run-1", "created_at": NOW, "expires_at": NOW + timedelta(minutes=20),
        "instance": snap, "target_instance_type": "m5.medium", "evidence_window_days": 14,
        "metrics": [],
        "checks": [DependencyCheck(name="eligible", status=CheckStatus.PASS, explanation="ok")],
        "scenarios": [Scenario(name="right-size", target_instance_type="m5.medium", estimated_cost=cost,
            risk_score=20, blast_radius=[snap.instance_id], downtime_required=True, reversible=True)],
        "selected_scenario": "right-size",
        "action_plan": [ActionStep(operation="stop-instances", parameters={}),
            ActionStep(operation="modify-instance-attribute", parameters={}),
            ActionStep(operation="start-instances", parameters={})],
        "rollback_plan": [], "production": False,
    }
    values.update(updates)
    return bind_hash(Proposal(**values))

def test_hash_is_stable_and_material_change_changes_hash():
    a, b = make_proposal(), make_proposal()
    assert a.proposal_hash == b.proposal_hash
    changed = bind_hash(a.model_copy(update={"target_instance_type":"m5.small", "proposal_hash":None}))
    assert changed.proposal_hash != a.proposal_hash

def test_expired_approval_denied():
    p = make_proposal()
    approval = Approval(decision="approve", proposal_hash=p.proposal_hash, approver="alice",
        approved_at=NOW-timedelta(minutes=2), expires_at=NOW-timedelta(minutes=1))
    with pytest.raises(PolicyViolation, match="expired"):
        validate_approval(p, approval, NOW)

def test_wrong_hash_denied():
    p = make_proposal()
    approval = Approval(decision="approve", proposal_hash="0"*64, approver="alice",
        approved_at=NOW, expires_at=NOW+timedelta(minutes=5))
    with pytest.raises(PolicyViolation, match="not bound"):
        validate_approval(p, approval, NOW+timedelta(seconds=1))

def test_production_requires_health_check():
    p = make_proposal(production=True)
    with pytest.raises(PolicyViolation, match="health check"):
        validate_proposal(p, NOW)

def test_critical_unknown_or_failure_blocks_execution():
    p = make_proposal(checks=[DependencyCheck(name="asg", status=CheckStatus.FAIL, explanation="managed")])
    with pytest.raises(PolicyViolation, match="Critical checks"):
        validate_proposal(p, NOW)

def test_cost_math_is_decimal_and_exact():
    c = estimate_cost(Decimal("0.30"), Decimal("0.10"), basis="test", confidence="high", caveats=[])
    assert c.monthly_savings == Decimal("146.00")
    assert isinstance(c.monthly_savings, Decimal)
    with pytest.raises(TypeError):
        CostEstimate(current_hourly=0.3, target_hourly="0.1", current_monthly="1", target_monthly="1",
            monthly_savings="0", savings_percent="0", basis="x", confidence="low")

def test_non_allowlisted_mutation_is_impossible_at_schema_boundary():
    with pytest.raises(ValueError):
        ActionStep(operation="terminate-instances", parameters={})
