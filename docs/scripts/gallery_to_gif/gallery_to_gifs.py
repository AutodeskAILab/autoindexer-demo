#!/usr/bin/env python3
"""Convert GALLERY.md evaluation cases into animated GIFs and a JSON manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from parse_gallery import parse_gallery
from publish_paths import (
    DEFAULT_GALLERY_ROOT,
    DOCS_ROOT,
    gallery_gif_path,
    gallery_outcome_tag,
    sidecar_path,
)
from render_gif import _layout_px, build_metadata, render_case_gif, set_render_scale

DEFAULT_GALLERY = SCRIPT_DIR.parent.parent / "results" / "GALLERY.md"
LEGACY_OUT = SCRIPT_DIR.parent.parent / "results" / "gallery_gifs"
MANIFEST_SCRIPT = DOCS_ROOT / "scripts" / "generate_gallery_manifest.py"


def _write_sidecar(gif_path: Path, case_meta: dict) -> None:
    payload = {
        "outcome": gallery_outcome_tag(case_meta["outcome"]),
        "caption": case_meta.get("description", ""),
    }
    sidecar_path(gif_path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _regenerate_page_manifest() -> None:
    if not MANIFEST_SCRIPT.is_file():
        return
    subprocess.run(
        [sys.executable, str(MANIFEST_SCRIPT)],
        check=True,
        cwd=DOCS_ROOT,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gallery",
        type=Path,
        default=DEFAULT_GALLERY,
        help="Path to GALLERY.md",
    )
    parser.add_argument(
        "--gallery-root",
        type=Path,
        default=DEFAULT_GALLERY_ROOT,
        help="Project page gallery root (assets/gallery)",
    )
    parser.add_argument(
        "--mode",
        choices=("free_generation", "teacher_forced"),
        default="free_generation",
        help="Gallery mode folder (GALLERY.md cases are free_generation)",
    )
    parser.add_argument(
        "--legacy-flat-dir",
        type=Path,
        default=None,
        help="Also write flat copies here (e.g. results/gallery_gifs)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max cases to render")
    parser.add_argument("--fps", type=int, default=8, help="Animation frames per second")
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="Render scale for resolution (2.0 = 2200px wide canvas)",
    )
    parser.add_argument(
        "--skip-page-manifest",
        action="store_true",
        help="Do not run docs/scripts/generate_gallery_manifest.py",
    )
    args = parser.parse_args(argv)

    gallery_path = args.gallery.resolve()
    if not gallery_path.is_file():
        print(f"Gallery not found: {gallery_path}", file=sys.stderr)
        return 1

    cases = parse_gallery(gallery_path)
    if args.limit is not None:
        cases = cases[: args.limit]

    gallery_root = args.gallery_root.resolve()
    set_render_scale(args.scale)
    _layout_px()
    entries: list[dict] = []

    for case in tqdm(cases, desc="Rendering GIFs", unit="case"):
        gif_path = gallery_gif_path(case, gallery_root, mode=args.mode)
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            render_case_gif(case, gif_path, fps=args.fps)
        except Exception as exc:  # noqa: BLE001 — collect per-case failures
            entries.append(
                {
                    "path": gif_path.relative_to(DOCS_ROOT).as_posix(),
                    "case_index": case.index,
                    "error": str(exc),
                    "op": case.op,
                    "outcome": case.outcome,
                }
            )
            tqdm.write(f"Failed case {case.index}: {exc}")
            continue

        meta = build_metadata(case, gif_path.name)
        meta_dict = asdict(meta)
        meta_dict["path"] = gif_path.relative_to(DOCS_ROOT).as_posix()
        meta_dict["gallery_outcome"] = gallery_outcome_tag(case.outcome)
        meta_dict["mode"] = args.mode
        entries.append(meta_dict)
        _write_sidecar(gif_path, meta_dict)

        if args.legacy_flat_dir is not None:
            legacy = args.legacy_flat_dir.resolve() / gif_path.name
            legacy.write_bytes(gif_path.read_bytes())
            _write_sidecar(legacy, meta_dict)

    build_manifest_path = gallery_root / "build_manifest.json"
    gallery_ref = gallery_path
    try:
        gallery_ref = gallery_path.relative_to(DOCS_ROOT.parent)
    except ValueError:
        gallery_ref = gallery_path.name
    gallery_root_ref = gallery_root
    try:
        gallery_root_ref = gallery_root.relative_to(DOCS_ROOT)
    except ValueError:
        gallery_root_ref = Path("assets/gallery")
    build_manifest = {
        "gallery": gallery_ref.as_posix(),
        "gallery_root": gallery_root_ref.as_posix(),
        "mode": args.mode,
        "render_scale": args.scale,
        "case_count": len(cases),
        "rendered": sum(1 for e in entries if "error" not in e),
        "cases": entries,
    }
    build_manifest_path.write_text(
        json.dumps(build_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not args.skip_page_manifest:
        try:
            _regenerate_page_manifest()
        except subprocess.CalledProcessError as exc:
            print(f"Page manifest script failed: {exc}", file=sys.stderr)
            return 1

    tqdm.write(f"Build manifest: {build_manifest_path}")
    tqdm.write(f"Page manifest: {gallery_root / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
