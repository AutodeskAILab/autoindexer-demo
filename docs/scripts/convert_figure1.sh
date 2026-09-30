#!/usr/bin/env bash
# Rasterize writeup/figures/fig1.pdf for the project page (macOS qlmanage).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$(cd "${ROOT}/../writeup/figures" && pwd)/fig1.pdf"
OUT_DIR="${ROOT}/assets"
TMP="${OUT_DIR}/fig1.pdf.png"

cp "$SRC" "${OUT_DIR}/figure1.pdf"
qlmanage -t -s 2400 -o "$OUT_DIR" "${OUT_DIR}/figure1.pdf" >/dev/null 2>&1
mv "$TMP" "${OUT_DIR}/figure1.png"
echo "Wrote ${OUT_DIR}/figure1.png and ${OUT_DIR}/figure1.pdf"
