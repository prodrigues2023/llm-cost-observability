"""The pricing abstraction — docs/contracts/pricing-abstraction.md, implemented.

A price basis is a versioned, dated rate-table row keyed by an abstract
`model_tier`. Rates are append-only: a price change adds a new row and
closes the previous one's `effective_to`, so a historical event's cost
stays reproducible after the table changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


class NoApplicablePriceBasisError(Exception):
    """Raised when no price basis covers a (model_tier, timestamp) pair."""


@dataclass(frozen=True)
class PriceBasis:
    price_basis_id: str
    model_tier: str
    currency: str
    rate_input: Decimal
    rate_output: Decimal
    rate_cached_input: Decimal
    effective_from: datetime
    effective_to: datetime | None
    source: str

    def covers(self, model_tier: str, at: datetime) -> bool:
        if self.model_tier != model_tier:
            return False
        if at < self.effective_from:
            return False
        return not (self.effective_to is not None and at >= self.effective_to)

    def compute_cost(
        self, input_tokens: int, output_tokens: int, cached_input_tokens: int
    ) -> Decimal:
        return (
            Decimal(input_tokens) * self.rate_input
            + Decimal(output_tokens) * self.rate_output
            + Decimal(cached_input_tokens) * self.rate_cached_input
        )


class RateTable:
    """An append-only collection of PriceBasis rows.

    `add` never mutates an existing row -- per pricing-abstraction.md, a
    rate correction closes the old row's effective_to and adds a new one.
    """

    def __init__(self) -> None:
        self._rows: list[PriceBasis] = []

    def add(self, basis: PriceBasis) -> None:
        self._rows.append(basis)

    def lookup(self, model_tier: str, at: datetime) -> PriceBasis:
        matches = [row for row in self._rows if row.covers(model_tier, at)]
        if not matches:
            raise NoApplicablePriceBasisError(
                f"no price basis covers model_tier={model_tier!r} at {at.isoformat()}"
            )
        if len(matches) > 1:
            # Overlapping effective windows for the same tier is a data
            # error in the table, not something to silently resolve by
            # picking one -- surfacing it is the point of an append-only,
            # non-overlapping contract.
            raise ValueError(
                f"overlapping price basis rows for model_tier={model_tier!r} at {at.isoformat()}: "
                f"{[row.price_basis_id for row in matches]}"
            )
        return matches[0]

    def get(self, price_basis_id: str) -> PriceBasis:
        for row in self._rows:
            if row.price_basis_id == price_basis_id:
                return row
        raise KeyError(price_basis_id)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
