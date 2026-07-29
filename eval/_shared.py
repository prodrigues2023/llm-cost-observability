"""Shared setup for the Milestone 4 drill scripts -- not a test module,
just the rate table every drill needs and a tiny report-writing helper.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from costkit.pricing import PriceBasis, RateTable

REPORT_DIR = Path(__file__).resolve().parent.parent / "docs" / "validation"


def make_rates() -> RateTable:
    table = RateTable()
    for tier, rate_in, rate_out in (
        ("small", "0.0000005", "0.0000015"),
        ("large", "0.000003", "0.000015"),
    ):
        table.add(
            PriceBasis(
                price_basis_id=f"{tier}-2026",
                model_tier=tier,
                currency="USD",
                rate_input=Decimal(rate_in),
                rate_output=Decimal(rate_out),
                rate_cached_input=Decimal(rate_in) / 2,
                effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                effective_to=None,
                source="reference rate table, docs/contracts/pricing-abstraction.md example",
            )
        )
    return table


def write_report(filename: str, content: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path
