"""BGP Antifilter route generation utilities."""

from pathlib import Path


def _read_version():
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


__version__ = _read_version()

