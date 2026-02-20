#!/usr/bin/env python3
"""
verm_extractor.py

Safely extract per-work blocks from a Vermes DSS "txt" that may contain HTML,
OCR artifacts, control characters, and malformed sigla. Never streams raw file
bytes directly to terminal; writes outputs to disk.

Primary modes:
  1) Manual extraction by line range (recommended for early passes):
       verm_extractor.py extract --start 14505 --end 14556 --title "Register of Rebukes" --sigla "4Q477"

  2) Assisted boundary scan (prints only sanitized metadata, not raw text):
       verm_extractor.py scan --after 14000 --limit 30
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_TXT = "/ai_data/ebooks/Jewish/Second_Temple/DSS/Translations/Vermes/Dead_Sea_Scrolls_Vermes_Complete_English.txt"
DEFAULT_OUTROOT = "/ai_data/ebooks/Jewish/Second_Temple/DSS"

# ---- helpers ----

CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # keep \t and \n
WS_RE = re.compile(r"\s+")

def sanitize_line(s: str) -> str:
    # Replace control chars that can crash terminals/editors
    s = CTRL_RE.sub(" ", s)
    # Normalize weird whitespace
    s = s.replace("\u00a0", " ")
    return s

def slugify(s: str) -> str:
    s = sanitize_line(s)
    s = s.strip().lower()
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "untitled"

def read_lines(path: str) -> list[str]:
    # errors="replace" prevents decode exceptions; sanitize later
    with open(path, "r", errors="replace") as f:
        return [sanitize_line(x) for x in f.readlines()]

@dataclass
class ExtractSpec:
    title: str
    sigla: str
    start: int
    end: int
    corpus_subdir: str = "Sectarian"  # default bucket under DSS

def write_extract(lines: list[str], spec: ExtractSpec, outroot: str) -> Path:
    outroot_p = Path(outroot)
    folder = f"{slugify(spec.title)}_{slugify(spec.sigla) if spec.sigla else ''}".strip("_")
    base = outroot_p / spec.corpus_subdir / folder
    eng = base / "english"
    meta = base / "metadata"
    eng.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)

    out_txt = eng / f"{folder}_vermes_english.txt"
    out_json = meta / f"{folder}_vermes.json"

    header = [
        f"# {spec.title} ({spec.sigla}) - English (Vermes)".replace(" ()", ""),
        "# Source: Geza Vermes, Complete Dead Sea Scrolls in English",
        f"# Witness: {DEFAULT_TXT}",
        f"# Extraction: lines {spec.start}-{spec.end}",
        "",
    ]

    with open(out_txt, "w") as g:
        g.write("\n".join(header))
        # write the selected range exactly as lines (already sanitized)
        g.writelines(lines[spec.start - 1 : spec.end])

    meta_obj = {
        "work": spec.title,
        "sigla": spec.sigla,
        "corpus": f"DSS/{spec.corpus_subdir}",
        "source_volume": "Geza Vermes, Complete Dead Sea Scrolls in English",
        "witness_txt": DEFAULT_TXT,
        "line_range": f"{spec.start}-{spec.end}",
        "language": "English",
        "notes": "Extracted by line range; source witness contains HTML/OCR artifacts; output sanitized for control chars.",
    }
    with open(out_json, "w") as g:
        json.dump(meta_obj, g, indent=2)

    return out_txt

# ---- scanning (assisted) ----
# We avoid printing raw content; we only print candidate boundary metadata.

SIGLA_HINT = re.compile(r"\(\s*[^)]*Q[^)]*\)\s*$", re.IGNORECASE)  # flexible: anything with 'Q' inside (...)
PAREN_LINE = re.compile(r"^\s*\([^)]{2,80}\)\s*$")                 # generic parenthetical line

def looks_like_title(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # Exclude obvious non-titles
    if s.startswith("<") or s.startswith("http") or s.startswith("For the editio"):
        return False
    # Titles tend to be short-ish and mostly letters/punct
    if len(s) > 80:
        return False
    # Avoid sentences (lots of punctuation)
    if s.count(".") >= 2:
        return False
    # Must contain at least one letter
    return any(c.isalpha() for c in s)

def scan_candidates(lines: list[str], after: int, limit: int) -> list[tuple[int, str, str]]:
    """
    Returns list of (title_line_no, title, sigla_or_paren) for candidates.
    Heuristic: a title line followed within 1..6 lines by a parenthetical,
    preferably containing 'Q' (e.g., (4Q274), (1QS), etc.).
    """
    out = []
    n = len(lines)
    i = max(1, after)
    while i <= n and len(out) < limit:
        title = lines[i - 1].strip()
        if looks_like_title(title):
            window = lines[i : min(n, i + 7)]  # next 1..7 lines
            paren = ""
            for w in window:
                ww = w.strip()
                if not ww:
                    continue
                if PAREN_LINE.match(ww):
                    paren = ww
                    break
            if paren:
                # Don't spam duplicates for same title block
                out.append((i, title, paren))
                i += 1
                continue
        i += 1
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt", default=DEFAULT_TXT, help="Path to Vermes witness TXT")
    ap.add_argument("--outroot", default=DEFAULT_OUTROOT, help="Root DSS directory for outputs")

    sub = ap.add_subparsers(dest="cmd", required=True)

    s_scan = sub.add_parser("scan", help="Scan for candidate title/sigla blocks (prints metadata only)")
    s_scan.add_argument("--after", type=int, default=1, help="Start scanning after this line number")
    s_scan.add_argument("--limit", type=int, default=30, help="How many candidates to print")

    s_ext = sub.add_parser("extract", help="Extract a single work by explicit line range")
    s_ext.add_argument("--start", type=int, required=True)
    s_ext.add_argument("--end", type=int, required=True)
    s_ext.add_argument("--title", required=True)
    s_ext.add_argument("--sigla", default="")
    s_ext.add_argument("--bucket", default="Sectarian", help="Subdir under DSS (e.g., Sectarian, Calendars, Apocalyptic)")

    args = ap.parse_args()
    lines = read_lines(args.txt)

    if args.cmd == "scan":
        cands = scan_candidates(lines, args.after, args.limit)
        for ln, title, paren in cands:
            # Print safely: sanitize again and compress spaces
            t = WS_RE.sub(" ", sanitize_line(title)).strip()
            p = WS_RE.sub(" ", sanitize_line(paren)).strip()
            print(f"{ln}\t{t}\t{p}")
        return

    if args.cmd == "extract":
        spec = ExtractSpec(
            title=args.title,
            sigla=args.sigla,
            start=args.start,
            end=args.end,
            corpus_subdir=args.bucket,
        )
        out_txt = write_extract(lines, spec, args.outroot)
        print(f"DONE: {out_txt}")

if __name__ == "__main__":
    main()

