"""Output paths for docs/assets/gallery layout."""

from __future__ import annotations

import re
from pathlib import Path

from parse_gallery import GalleryCase

SCRIPT_DIR = Path(__file__).resolve().parent
DOCS_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_GALLERY_ROOT = DOCS_ROOT / "assets" / "gallery"

OUTCOME_PREFIX: dict[str, str] = {
    "repaired": "exact_repair",
    "partial_repair": "improved",
    "no_edit": "no_edit",
    "wrong_position": "wrong_position",
    "made_worse": "worse",
    "wrong_content": "worse",
    "over_delete": "worse",
    "under_delete": "improved",
    "spurious_damaging": "worse",
    "spurious_harmless": "no_edit",
}


def _sanitize(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_") or "unknown"


def gallery_outcome_tag(outcome: str) -> str:
    return OUTCOME_PREFIX.get(outcome, "improved")


def gallery_gif_basename(case: GalleryCase) -> str:
    tag = gallery_outcome_tag(case.outcome)
    return f"{tag}_{case.index:03d}_{_sanitize(case.source)}.gif"


def gallery_gif_path(
    case: GalleryCase,
    gallery_root: Path,
    mode: str = "free_generation",
) -> Path:
    return gallery_root / mode / case.op / gallery_gif_basename(case)


def sidecar_path(gif_path: Path) -> Path:
    return gif_path.with_suffix(gif_path.suffix + ".meta.json")
