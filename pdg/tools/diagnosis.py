"""N16 hook: the tri-state review gate (see pdg.gating.review_gate)."""

from ..context import CheckResult, NodeContext
from ..gating import review_gate


def gate(ctx: NodeContext) -> CheckResult:
    return review_gate(ctx)
