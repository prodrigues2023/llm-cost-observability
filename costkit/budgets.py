"""Budgets and anomaly detection — ADR-0005, implemented.

Two independent detectors, as the ADR requires: a budget is a threshold
crossed; an anomaly is a sudden change regardless of threshold. Both watch
cost per outcome, not just total spend, so a retry storm that leaves
spend looking flat still trips something.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class BudgetMetric(str, Enum):
    SPEND = "spend"
    COST_PER_OUTCOME = "cost_per_outcome"


@dataclass(frozen=True)
class Budget:
    """A threshold on one dimension value -- 'this feature should cost about
    this much', per ADR-0005.
    """

    dimension: str  # "feature" or "tenant"
    value: str
    metric: BudgetMetric
    threshold: Decimal
    window: timedelta = timedelta(hours=24)


@dataclass(frozen=True)
class BudgetBreach:
    budget: Budget
    actual: Decimal


def check_budgets(store, budgets: list[Budget], now: datetime) -> list[BudgetBreach]:
    breaches: list[BudgetBreach] = []
    for budget in budgets:
        since = now - budget.window
        rows = store.spend_and_unit_cost_by(budget.dimension, since=since)
        row = next((r for r in rows if r[budget.dimension] == budget.value), None)
        if row is None:
            continue
        actual = row["total_spend"] if budget.metric is BudgetMetric.SPEND else row["cost_per_outcome"]
        if actual is None:
            continue
        actual = Decimal(str(actual))
        if actual > budget.threshold:
            breaches.append(BudgetBreach(budget=budget, actual=actual))
    return breaches


@dataclass(frozen=True)
class Anomaly:
    dimension: str
    value: str
    baseline_cost_per_outcome: float
    recent_cost_per_outcome: float
    ratio: float


def detect_anomalies(
    store,
    dimension: str,
    values: list[str],
    now: datetime,
    recent_window: timedelta = timedelta(hours=1),
    baseline_window: timedelta = timedelta(hours=6),
    ratio_threshold: float = 1.5,
    min_outcomes: int = 3,
) -> list[Anomaly]:
    """Flags a slice whose recent cost-per-outcome has risen sharply versus
    its own immediately-preceding baseline -- independent of any budget,
    per ADR-0005's "anomaly regardless of absolute level."

    This is a ratio-over-a-rolling-baseline detector, not a statistical
    one (no seasonality model, no z-score) -- a deliberate simplification
    for a reference implementation; docs/cost-model.md and ADR-0005 both
    flag that real anomaly detection has to distinguish legitimate traffic
    swings from regressions, which this does not attempt.
    """
    baseline_start = now - recent_window - baseline_window
    recent_start = now - recent_window

    anomalies = []
    for value in values:
        # Baseline is bounded on both sides so it excludes the recent
        # window entirely -- an overlapping baseline would be partly
        # compared against itself and dilute exactly the signal this is
        # meant to catch.
        baseline_rows = store.spend_and_unit_cost_by(dimension, since=baseline_start, until=recent_start)
        recent_rows = store.spend_and_unit_cost_by(dimension, since=recent_start)

        baseline_row = next((r for r in baseline_rows if r[dimension] == value), None)
        recent_row = next((r for r in recent_rows if r[dimension] == value), None)
        if baseline_row is None or recent_row is None:
            continue
        if baseline_row["cost_per_outcome"] is None or recent_row["cost_per_outcome"] is None:
            continue
        if recent_row["succeeded_outcomes"] < min_outcomes:
            continue

        baseline_cost = baseline_row["cost_per_outcome"]
        recent_cost = recent_row["cost_per_outcome"]
        if baseline_cost <= 0:
            continue
        ratio = recent_cost / baseline_cost
        if ratio >= ratio_threshold:
            anomalies.append(
                Anomaly(
                    dimension=dimension,
                    value=value,
                    baseline_cost_per_outcome=baseline_cost,
                    recent_cost_per_outcome=recent_cost,
                    ratio=ratio,
                )
            )
    return anomalies
