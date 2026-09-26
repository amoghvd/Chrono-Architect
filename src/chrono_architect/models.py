from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RunState(StrEnum):
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    PRECONDITIONS_RECHECKED = "PRECONDITIONS_RECHECKED"
    STOP_REQUESTED = "STOP_REQUESTED"
    STOPPED = "STOPPED"
    TYPE_CHANGED = "TYPE_CHANGED"
    START_REQUESTED = "START_REQUESTED"
    RUNNING = "RUNNING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"


class DependencyCheck(StrictModel):
    name: str
    status: CheckStatus
    critical: bool = True
    evidence: dict[str, Any] = Field(default_factory=dict)
    explanation: str


class InstanceSnapshot(StrictModel):
    account_id: str
    region: str
    instance_id: str
    instance_type: str
    state: str
    architecture: str
    lifecycle: str = "on-demand"
    root_device_type: str
    asg_name: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    volume_ids: list[str] = Field(default_factory=list)
    eni_ids: list[str] = Field(default_factory=list)
    security_group_ids: list[str] = Field(default_factory=list)
    public_ip: str | None = None
    has_instance_store_mapping: bool = False
    raw_fingerprint: str


class MetricSummary(StrictModel):
    metric: str
    unit: str
    datapoints: int
    average: Decimal | None = None
    p95: Decimal | None = None
    maximum: Decimal | None = None
    start: datetime
    end: datetime


class CostEvidence(StrictModel):
    source: Literal["Cost Explorer"] = "Cost Explorer"
    metric: str
    start: datetime
    end: datetime
    amount: Decimal
    currency: str
    resource_level: bool
    caveats: list[str] = Field(default_factory=list)


class CostEstimate(StrictModel):
    currency: Literal["USD"] = "USD"
    current_hourly: Decimal
    target_hourly: Decimal
    monthly_hours: Decimal = Decimal(730)
    current_monthly: Decimal
    target_monthly: Decimal
    monthly_savings: Decimal
    savings_percent: Decimal
    basis: str
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = Field(default_factory=list)

    @field_validator("current_hourly", "target_hourly", mode="before")
    @classmethod
    def reject_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise TypeError("Currency values must not be floats")
        return value


class Scenario(StrictModel):
    name: str
    target_instance_type: str
    estimated_cost: CostEstimate
    risk_score: int = Field(ge=0, le=100)
    blast_radius: list[str]
    downtime_required: bool
    reversible: bool
    uncertainty: list[str] = Field(default_factory=list)


class ActionStep(StrictModel):
    service: Literal["ec2"] = "ec2"
    operation: Literal["stop-instances", "modify-instance-attribute", "start-instances"]
    parameters: dict[str, Any]


class Proposal(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    created_at: datetime
    expires_at: datetime
    instance: InstanceSnapshot
    target_instance_type: str
    evidence_window_days: int
    metrics: list[MetricSummary]
    historical_cost: CostEvidence | None = None
    checks: list[DependencyCheck]
    scenarios: list[Scenario]
    selected_scenario: str
    action_plan: list[ActionStep]
    rollback_plan: list[ActionStep]
    health_check_url: str | None = None
    production: bool = False
    proposal_hash: str | None = None


class Approval(StrictModel):
    decision: Literal["approve", "deny"]
    proposal_hash: str
    approver: str = Field(min_length=1)
    approved_at: datetime
    expires_at: datetime
    allow_rollback: bool = False


class AuditEvent(StrictModel):
    sequence: int
    run_id: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: str
    state: RunState | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    previous_event_hash: str | None = None
    event_hash: str | None = None
