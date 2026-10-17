"""Select the local privacy policy without distributing private vocabulary."""

from pathlib import Path

from .util import PKG_ROOT


def privacy_path(root: Path = PKG_ROOT) -> Path:
    private = root / "knowledge/case-studies/hub-programmes-2026/deidentify_TENANT.json"
    if private.exists():
        return private
    return root / "knowledge/public/privacy.json"
