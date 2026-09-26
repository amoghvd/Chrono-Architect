from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from math import ceil

from .models import CostEstimate, MetricSummary

D = Decimal


def percentile(values: list[Decimal], p: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, ceil((p / D("100")) * len(ordered)) - 1)
    return ordered[index]


def summarize(metric: str, unit: str, datapoints: Iterable[tuple], start, end) -> MetricSummary:
    values = [D(str(value)) for _, value in datapoints]
    return MetricSummary(
        metric=metric, unit=unit, datapoints=len(values),
        average=(sum(values) / D(len(values))).quantize(D("0.0001")) if values else None,
        p95=percentile(values, D("95")), maximum=max(values) if values else None,
        start=start, end=end,
    )


def estimate_cost(current_hourly: Decimal, target_hourly: Decimal, *,
                  basis: str, confidence: str, caveats: list[str]) -> CostEstimate:
    hours = D("730")
    current = (current_hourly * hours).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    target = (target_hourly * hours).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    savings = current - target
    pct = ((savings / current) * D("100")).quantize(D("0.01")) if current else D("0")
    return CostEstimate(
        current_hourly=current_hourly, target_hourly=target_hourly,
        current_monthly=current, target_monthly=target,
        monthly_savings=savings, savings_percent=pct,
        basis=basis, confidence=confidence, caveats=caveats,
    )
