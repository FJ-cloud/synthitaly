"""Shared HTML helpers — inlining an SVG and reading the caption file.

Split out of ``build_deck.py`` so ``scripts/build_results_page.py`` can build a
self-contained page the same way without importing the whole deck (whose module body
base64-encodes forty images at import time).
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"


def data_uri(svg: Path) -> str:
    """An <img src=…> data-URI for ``svg`` — no external request at render time."""
    b64 = base64.b64encode(svg.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def captions(fig_dir: Path | None = None) -> dict[str, str]:
    """``{figure_stem: caption}`` parsed from ``figures/CAPTIONS.md``."""
    path = (fig_dir or FIG_DIR) / "CAPTIONS.md"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \*\*(.+?)\*\* — (.+)", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out
