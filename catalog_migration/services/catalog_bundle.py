"""Explicit package versions; legacy defaults remain compatible."""

from pathlib import Path

LEGACY_DIRECTORY = 'zvuchno-migration-bundle-v1.3'
V2_DIRECTORY = 'zvuchno-migration-bundle-v2'


def bundle_root(package_root: str | Path) -> Path:
    """Return the supported bundle directory inside a package root."""
    root = Path(package_root)
    # Do not select an arbitrary directory or follow paths from config.
    return root / (
        V2_DIRECTORY if (root / V2_DIRECTORY).is_dir() else LEGACY_DIRECTORY
    )


def bundle_version(package_root: str | Path) -> str:
    """Return the format version selected for a package root."""
    return '2.0' if bundle_root(package_root).name == V2_DIRECTORY else '1.3'


def mapping_version(package_root: str | Path) -> str:
    """Scope DB mappings and audio state to the exact v2 bundle."""
    if bundle_version(package_root) == '1.3':
        return '1.3'
    import hashlib

    path = bundle_root(package_root) / 'bundle.json'
    return '2-' + hashlib.sha256(path.read_bytes()).hexdigest()[:30]
