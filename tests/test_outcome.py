"""docs/contracts/outcome-contract.md, exercised for real."""

from datetime import datetime, timedelta, timezone

import pytest

from costkit.outcome import AlreadyResolvedError, Outcome, OutcomeStatus


def make_outcome(**overrides):
    defaults = {
        "outcome_id": "task-1",
        "feature": "checkout-assistant",
        "tenant": "acme",
        "opened_at": datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        "resolution_window": timedelta(minutes=10),
    }
    defaults.update(overrides)
    return Outcome(**defaults)


def test_starts_pending():
    outcome = make_outcome()
    assert outcome.status is OutcomeStatus.PENDING
    assert outcome.resolved_at is None
    assert outcome.counts_toward_denominator is False


def test_resolve_succeeded():
    outcome = make_outcome()
    at = outcome.opened_at + timedelta(minutes=1)
    outcome.resolve(OutcomeStatus.SUCCEEDED, at)
    assert outcome.status is OutcomeStatus.SUCCEEDED
    assert outcome.resolved_at == at
    assert outcome.counts_toward_denominator is True


def test_resolve_failed_does_not_count_toward_denominator():
    outcome = make_outcome()
    outcome.resolve(OutcomeStatus.FAILED, outcome.opened_at + timedelta(minutes=1))
    assert outcome.counts_toward_denominator is False


def test_cannot_resolve_twice():
    outcome = make_outcome()
    outcome.resolve(OutcomeStatus.SUCCEEDED, outcome.opened_at + timedelta(minutes=1))
    with pytest.raises(AlreadyResolvedError):
        outcome.resolve(OutcomeStatus.FAILED, outcome.opened_at + timedelta(minutes=2))


def test_resolve_rejects_abandoned_status():
    outcome = make_outcome()
    with pytest.raises(ValueError):
        outcome.resolve(OutcomeStatus.ABANDONED, outcome.opened_at + timedelta(minutes=1))


def test_sweep_does_not_abandon_within_window():
    outcome = make_outcome()
    swept = outcome.sweep_abandoned(outcome.opened_at + timedelta(minutes=5))
    assert swept is False
    assert outcome.status is OutcomeStatus.PENDING


def test_sweep_abandons_past_window():
    outcome = make_outcome()
    at = outcome.opened_at + timedelta(minutes=11)
    swept = outcome.sweep_abandoned(at)
    assert swept is True
    assert outcome.status is OutcomeStatus.ABANDONED
    assert outcome.resolved_at == at
    assert outcome.counts_toward_denominator is False


def test_sweep_does_not_touch_already_resolved_outcome():
    outcome = make_outcome()
    resolved_at = outcome.opened_at + timedelta(minutes=1)
    outcome.resolve(OutcomeStatus.SUCCEEDED, resolved_at)
    swept = outcome.sweep_abandoned(outcome.opened_at + timedelta(minutes=20))
    assert swept is False
    assert outcome.status is OutcomeStatus.SUCCEEDED
    assert outcome.resolved_at == resolved_at


def test_long_running_task_within_window_is_still_pending_not_abandoned():
    """A legitimately long task is pending, not abandoned, until its window elapses."""
    outcome = make_outcome(resolution_window=timedelta(hours=1))
    at = outcome.opened_at + timedelta(minutes=45)
    assert outcome.is_past_resolution_window(at) is False
