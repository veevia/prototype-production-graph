"""N18: recompute every release condition at release (prototype, ledger and control documents re-hashed from disk;
gate, defects, reviews and node status from the engine's saved state, never an agent's report) and package the build
with a sha256 manifest (see pdg.gating)."""

from ..context import CheckResult, NodeContext
from ..gating import release_verify


def verify(ctx: NodeContext) -> CheckResult:
    return release_verify(ctx)
