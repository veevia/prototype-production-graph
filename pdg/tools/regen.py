"""N17: the targeted regeneration plan and its check (see pdg.gating)."""

from ..context import CheckResult, NodeContext
from ..gating import check_targeted as _check, regeneration_plan


def plan(ctx: NodeContext) -> CheckResult:
    return regeneration_plan(ctx)


def check_targeted(ctx: NodeContext) -> CheckResult:
    return _check(ctx)
