"""Dimension propagation — attribution.md's "captured, not inferred."

Call sites set dimensions into context before calling the boundary; the
boundary reads them from here. This is the mechanism, not a suggestion:
a call made with the context unset reads UNKNOWN/UNATTRIBUTED_OUTCOME
sentinels, per cost-event-schema.md's rule that a missing dimension is
always an explicit, countable value, never a silent blank.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from costkit.schema import UNATTRIBUTED_OUTCOME, UNKNOWN

_feature: ContextVar[str] = ContextVar("feature", default=UNKNOWN)
_tenant: ContextVar[str] = ContextVar("tenant", default=UNKNOWN)
_route: ContextVar[str] = ContextVar("route", default=UNKNOWN)
_prompt_version: ContextVar[str] = ContextVar("prompt_version", default=UNKNOWN)
_outcome_id: ContextVar[str] = ContextVar("outcome_id", default=UNATTRIBUTED_OUTCOME)


@dataclass(frozen=True)
class Dimensions:
    feature: str
    tenant: str
    route: str
    prompt_version: str
    outcome_id: str


def current() -> Dimensions:
    return Dimensions(
        feature=_feature.get(),
        tenant=_tenant.get(),
        route=_route.get(),
        prompt_version=_prompt_version.get(),
        outcome_id=_outcome_id.get(),
    )


@contextmanager
def dimensions(
    *,
    feature: str | None = None,
    tenant: str | None = None,
    route: str | None = None,
    prompt_version: str | None = None,
    outcome_id: str | None = None,
):
    """Sets attribution dimensions for the duration of the block.

    Every model call the boundary makes within this block reads these
    values from context -- the call site never passes them to the
    boundary directly, per ADR-0004's "call sites propagate, they don't
    compute."
    """
    tokens = []
    if feature is not None:
        tokens.append((_feature, _feature.set(feature)))
    if tenant is not None:
        tokens.append((_tenant, _tenant.set(tenant)))
    if route is not None:
        tokens.append((_route, _route.set(route)))
    if prompt_version is not None:
        tokens.append((_prompt_version, _prompt_version.set(prompt_version)))
    if outcome_id is not None:
        tokens.append((_outcome_id, _outcome_id.set(outcome_id)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
