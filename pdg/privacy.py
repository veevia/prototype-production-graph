"""Select the local privacy policy without distributing private vocabulary."""

from pathlib import Path

from .util import PKG_ROOT


def privacy_path(root: Path = PKG_ROOT) -> Path:
    return root / "knowledge/public/privacy.json"
