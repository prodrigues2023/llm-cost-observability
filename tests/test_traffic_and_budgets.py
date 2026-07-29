"""Exercises the synthetic traffic generator and the budget/anomaly
detectors against data it actually produced -- not fixtures shaped to
make the assertions pass."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from costkit.budgets import Budget, BudgetMetric, check_budgets, detect_anomalies
from costkit.pricing import PriceBasis, RateTable
from costkit.store import CostStore
from costkit.traffic import FEATURES, RetryStorm, TrafficConfig, generate_traffic


def make_rates() -> RateTable:
    table = RateTable()
    for tier, rate_in, rate_out in (("small", "0.0000005", "0.0000015"), ("large", "0.000003", "0.000015")):
        table.add(
            PriceBasis(
                price_basis_id=f"{tier}-test",
                model_tier=tier,
                currency="USD",
                rate_input=Decimal(rate_in),
                rate_output=Decimal(rate_out),
                rate_cached_input=Decimal(rate_in) / 2,
                effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                effective_to=None,
                source="test",
            )
        )
    return table


def test_generate_traffic_populates_store():
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    config = TrafficConfig(start=now - timedelta(hours=6), end=now, num_tasks=150, seed=1)

    summary = generate_traffic(store, rates, config)

    assert summary["total"] == 150
    assert summary["succeeded"] > 0
    assert summary["failed"] >= 0

    rows = store.spend_and_unit_cost_by("feature")
    assert {r["feature"] for r in rows} <= set(FEATURES)
    assert store.total_spend() > 0
    store.close()


def test_retry_storm_raises_cost_per_outcome_for_that_feature_only():
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=8)

    storm = RetryStorm(
        feature="checkout-assistant",
        starts_at=now - timedelta(hours=1),
        ends_at=now,
        failure_rate=0.9,
    )
    config = TrafficConfig(start=start, end=now, num_tasks=900, seed=3, retry_storm=storm, base_failure_rate=0.02)
    generate_traffic(store, rates, config)

    baseline_rows = store.spend_and_unit_cost_by("feature", since=start)
    recent_rows = store.spend_and_unit_cost_by("feature", since=now - timedelta(hours=1))

    baseline = next(r for r in baseline_rows if r["feature"] == "checkout-assistant")
    recent = next(r for r in recent_rows if r["feature"] == "checkout-assistant")

    assert baseline["cost_per_outcome"] is not None
    assert recent["cost_per_outcome"] is not None
    assert recent["cost_per_outcome"] > baseline["cost_per_outcome"]

    other_baseline = next(r for r in baseline_rows if r["feature"] == "support-triage")
    other_recent = next(r for r in recent_rows if r["feature"] == "support-triage")
    # Unaffected feature should not show the same relative jump.
    assert other_recent["cost_per_outcome"] < recent["cost_per_outcome"]
    assert other_baseline["cost_per_outcome"] is not None

    store.close()


def test_detect_anomalies_flags_the_storm_feature():
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=8)

    storm = RetryStorm(
        feature="doc-summarizer",
        starts_at=now - timedelta(hours=1),
        ends_at=now,
        failure_rate=0.9,
    )
    config = TrafficConfig(start=start, end=now, num_tasks=900, seed=5, retry_storm=storm, base_failure_rate=0.02)
    generate_traffic(store, rates, config)

    anomalies = detect_anomalies(
        store, dimension="feature", values=FEATURES, now=now,
        recent_window=timedelta(hours=1), baseline_window=timedelta(hours=6),
        ratio_threshold=1.3, min_outcomes=3,
    )

    flagged = {a.value for a in anomalies}
    assert "doc-summarizer" in flagged


def test_check_budgets_flags_breach_and_respects_threshold():
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    config = TrafficConfig(start=now - timedelta(hours=6), end=now, num_tasks=300, seed=11)
    generate_traffic(store, rates, config)

    rows = store.spend_and_unit_cost_by("feature")
    spendy = max(rows, key=lambda r: r["total_spend"])

    tight_budget = Budget(
        dimension="feature", value=spendy["feature"], metric=BudgetMetric.SPEND,
        threshold=Decimal(str(spendy["total_spend"])) / 2, window=timedelta(hours=6),
    )
    loose_budget = Budget(
        dimension="feature", value=spendy["feature"], metric=BudgetMetric.SPEND,
        threshold=Decimal(str(spendy["total_spend"])) * 10, window=timedelta(hours=6),
    )

    breaches = check_budgets(store, [tight_budget, loose_budget], now)
    breached_thresholds = {b.budget.threshold for b in breaches}

    assert tight_budget.threshold in breached_thresholds
    assert loose_budget.threshold not in breached_thresholds
    store.close()
