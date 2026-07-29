"""docs/contracts/pricing-abstraction.md, exercised for real."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from costkit.pricing import NoApplicablePriceBasisError, PriceBasis, RateTable


def make_basis(**overrides):
    defaults = {
        "price_basis_id": "large-2026-01",
        "model_tier": "large",
        "currency": "USD",
        "rate_input": Decimal("0.000003"),
        "rate_output": Decimal("0.000015"),
        "rate_cached_input": Decimal("0.0000015"),
        "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "effective_to": None,
        "source": "test fixture",
    }
    defaults.update(overrides)
    return PriceBasis(**defaults)


def test_compute_cost_formula():
    basis = make_basis()
    cost = basis.compute_cost(input_tokens=1000, output_tokens=200, cached_input_tokens=100)
    expected = (
        Decimal(1000) * Decimal("0.000003")
        + Decimal(200) * Decimal("0.000015")
        + Decimal(100) * Decimal("0.0000015")
    )
    assert cost == expected


def test_rate_table_lookup_by_tier_and_time():
    table = RateTable()
    table.add(make_basis())
    at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    found = table.lookup("large", at)
    assert found.price_basis_id == "large-2026-01"


def test_rate_table_no_applicable_basis_raises():
    table = RateTable()
    table.add(make_basis())
    with pytest.raises(NoApplicablePriceBasisError):
        table.lookup("small", datetime(2026, 6, 1, tzinfo=timezone.utc))


def test_rate_table_respects_effective_window():
    table = RateTable()
    old = make_basis(
        price_basis_id="large-old",
        effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
        rate_input=Decimal("0.000005"),
    )
    new = make_basis(price_basis_id="large-new", effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc))
    table.add(old)
    table.add(new)

    before = table.lookup("large", datetime(2025, 6, 1, tzinfo=timezone.utc))
    after = table.lookup("large", datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert before.price_basis_id == "large-old"
    assert after.price_basis_id == "large-new"


def test_historical_cost_reproducible_after_price_change():
    """A price change must not alter a historical event's already-computed cost."""
    table = RateTable()
    old = make_basis(
        price_basis_id="large-old",
        effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
        rate_input=Decimal("0.000005"),
    )
    table.add(old)
    historical_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    basis_then = table.lookup("large", historical_at)
    cost_then = basis_then.compute_cost(1000, 0, 0)

    # A new rate is added later -- the append-only contract.
    table.add(make_basis(price_basis_id="large-new", effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc)))

    # Re-fetching the *same* price_basis_id by id (as a stored event would)
    # still returns the original rate.
    assert table.get("large-old").compute_cost(1000, 0, 0) == cost_then


def test_overlapping_rows_for_same_tier_raise():
    table = RateTable()
    table.add(make_basis(price_basis_id="a"))
    table.add(make_basis(price_basis_id="b"))  # same tier, same open-ended window
    with pytest.raises(ValueError):
        table.lookup("large", datetime(2026, 6, 1, tzinfo=timezone.utc))
