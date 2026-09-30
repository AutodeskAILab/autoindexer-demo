#!/usr/bin/env python3
"""Scan assets/gallery for GIFs and write manifest.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

OUTCOME_PREFIX = {
    "exact_repair": re.compile(r"^exact_repair[_-]", re.I),
    "improved": re.compile(r"^improved[_-]", re.I),
    "no_edit": re.compile(r"^no_edit[_-]", re.I),
    "wrong_position": re.compile(r"^wrong_position[_-]", re.I),
    "worse": re.compile(r"^worse[_-]", re.I),
}

VALID_OUTCOMES = frozenset(OUTCOME_PREFIX.keys())
MODES = ("teacher_forced", "free_generation")
EDIT_TYPES = ("insert", "delete", "substitute", "none")


def outcome_from_name(stem: str) -> str | None:
    for key, pat in OUTCOME_PREFIX.items():
        if pat.match(stem):
            return key
    return None


def read_sidecar(gif_path: Path) -> dict:
    sidecar = gif_path.with_suffix(gif_path.suffix + ".meta.json")
    if not sidecar.is_file():
        return {}
    return json.loads(sidecar.read_text(encoding="utf-8"))


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    gallery_root = root / "assets" / "gallery"
    items: list[dict[str, str]] = []

    for mode in MODES:
        for edit_type in EDIT_TYPES:
            folder = gallery_root / mode / edit_type
            if not folder.is_dir():
                continue
            for gif_path in sorted(folder.glob("*.gif")):
                rel = gif_path.relative_to(root).as_posix()
                meta = read_sidecar(gif_path)
                outcome = meta.get("outcome") or outcome_from_name(gif_path.stem) or "improved"
                if outcome not in VALID_OUTCOMES:
                    outcome = "improved"
                items.append(
                    {
                        "path": rel,
                        "mode": mode,
                        "edit_type": edit_type,
                        "outcome": outcome,
                        "caption": meta.get("caption") or "",
                    }
                )

    payload = {"items": items}
    manifest_path = gallery_root / "manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    js_path = gallery_root / "manifest.js"
    fetch_shim = """
(function () {
  var manifest = window.GALLERY_MANIFEST;
  if (!manifest || !manifest.items || !window.fetch) return;
  var nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf("manifest.json") !== -1) {
      return Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve(manifest); },
      });
    }
    return nativeFetch(input, init);
  };
})();
"""
    js_path.write_text(
        "window.GALLERY_MANIFEST=" + json.dumps(payload, separators=(",", ":")) + ";\n" + fetch_shim,
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} item(s) to {manifest_path} and {js_path}")


if __name__ == "__main__":
    main()
