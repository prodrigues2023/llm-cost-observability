"""The outcome contract — docs/contracts/outcome-contract.md, implemented.

An Outcome is resolved exactly once, by the task's owner, never by the
boundary. A sweep (`sweep_abandoned`) is what turns a `pending` outcome
that outlived its resolution window into `abandoned` -- the mechanism
that keeps abandoned work from sitting invisible in the denominator
forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class OutcomeStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


RESOLVED_STATUSES = frozenset({OutcomeStatus.SUCCEEDED, OutcomeStatus.FAILED, OutcomeStatus.ABANDONED})


class AlreadyResolvedError(Exception):
    """An outcome may resolve exactly once."""


@dataclass
class Outcome:
    outcome_id: str
    feature: str
    tenant: str
    opened_at: datetime
    resolution_window: timedelta
    status: OutcomeStatus = OutcomeStatus.PENDING
    resolved_at: datetime | None = None

    def resolve(self, status: OutcomeStatus, at: datetime) -> None:
        if status not in (OutcomeStatus.SUCCEEDED, OutcomeStatus.FAILED):
            raise ValueError("resolve() only accepts succeeded or failed -- abandonment is sweep_abandoned's job")
        if self.status is not OutcomeStatus.PENDING:
            raise AlreadyResolvedError(
                f"outcome {self.outcome_id} already resolved as {self.status.value}"
            )
        self.status = status
        self.resolved_at = at

    def is_past_resolution_window(self, at: datetime) -> bool:
        return self.status is OutcomeStatus.PENDING and at >= self.opened_at + self.resolution_window

    def sweep_abandoned(self, at: datetime) -> bool:
        """Marks the outcome abandoned if it is pending and past its window.

        Returns whether it was swept, so a caller can count how many it
        moved without re-deriving the condition.
        """
        if not self.is_past_resolution_window(at):
            return False
        self.status = OutcomeStatus.ABANDONED
        self.resolved_at = at
        return True

    @property
    def counts_toward_denominator(self) -> bool:
        return self.status is OutcomeStatus.SUCCEEDED
