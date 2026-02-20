#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

AI_EBOOKS = Path("/ai_data/ebooks")
BIN = Path.home() / "FineTuningAI" / "bin"

# Your existing tools (assumed present based on your setup)
CORPUS_INGEST_PDF = BIN / "corpus_ingest_pdf.py"
CORPUS_INGEST_TXT = BIN / "corpus_ingest_txt.py"   # if you don't have this, script will skip txt ingest step gracefully
WORK_LINK = BIN / "work_link.py"

# Controlled taxonomy: fixed, no “new categories on accident”
TAXONOMY = {
    "christian_theology": "Christian/Theology",
    "christian_commentary": "Christian/Commentary",
    "christian_history": "Christian/History",
    "jewish": "Jewish",
    "history": "History",
    "philosophy": "Philosophy",
    "science": "Science",
    "medicine": "Medicine",
    "reference": "Reference",
    "literature": "Literature",
    "unsorted": "_Unsorted",
}

TEXT_EXTS = {".txt", ".html", ".htm", ".epub", ".md"}
PDF_EXTS = {".pdf"}

@dataclass
class IngestItem:
    src: str               # url or local path
    local_path: Path       # downloaded/copied destination path
    kind: str              # "text" or "pdf"
    vol_idx: int | None    # parsed volume index if any

def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit(p.returncode)

def slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:120] if len(s) > 120 else s

def guess_category(title: str, author: str) -> str:
    t = (title + " " + author).lower()

    # High-signal buckets
    if any(k in t for k in ["talmud", "midrash", "sefaria", "tanakh", "mishnah", "gemara"]):
        return "jewish"

    if any(k in t for k in ["calvin", "luther", "reformation", "institutes", "confession", "catechism", "sermon", "theology"]):
        # commentaries vs theology
        if "commentary" in t or "commentaries" in t or "exposition" in t:
            return "christian_commentary"
        return "christian_theology"

    if any(k in t for k in ["encyclopedia", "dictionary", "handbook", "reference"]):
        return "reference"

    if any(k in t for k in ["medicine", "pediatr", "clinical", "pharmac", "anatom", "physiology"]):
        return "medicine"

    if any(k in t for k in ["physics", "chemistry", "biology", "astronomy", "electronics", "engineering"]):
        return "science"

    if any(k in t for k in ["plato", "aristotle", "kant", "hegel", "philosophy", "metaphysics", "ethics"]):
        return "philosophy"

    if any(k in t for k in ["history", "war", "empire", "revolution", "chronicle"]):
        return "history"

    return "unsorted"

def parse_vol_idx(s: str) -> int | None:
    x = s.lower()
    # vol 2 / volume 2 / vol. ii / v2 etc.
    m = re.search(r"(?:vol(?:ume)?\.?\s*)(\d+)\b", x)
    if m:
        try: return int(m.group(1))
        except: return None
    # roman numerals (ii, iii, iv)
    m = re.search(r"(?:vol(?:ume)?\.?\s*)(i{1,3}|iv|v)\b", x)
    if m:
        roman = m.group(1)
        return {"i":1,"ii":2,"iii":3,"iv":4,"v":5}.get(roman)
    # _01_ / _02_ patterns in IA stream filenames
    m = re.search(r"(?:chr|calv|vol)[^\d]{0,3}0?(\d)\b", x)
    if m:
        try: return int(m.group(1))
        except: return None
    return None

def download_url(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Prefer curl; fall back to wget if needed
    curl = shutil.which("curl")
    wget = shutil.which("wget")
    if curl:
        run([curl, "-L", "--retry", "5", "--retry-delay", "2", "-o", str(out_path), url])
    elif wget:
        run([wget, "-O", str(out_path), url])
    else:
        raise SystemExit("Need curl or wget installed to download URLs.")

def ingest_text_dir(work_dir: Path) -> None:
    if CORPUS_INGEST_TXT.exists():
        run(["python3", str(CORPUS_INGEST_TXT), "--root", str(work_dir), "--limit", "2000000"])
    else:
        print(f"NOTE: {CORPUS_INGEST_TXT} not found; skipping txt ingest.")

def ingest_pdf_dir(work_dir: Path) -> None:
    if CORPUS_INGEST_PDF.exists():
        run(["python3", str(CORPUS_INGEST_PDF), "--root", str(work_dir), "--limit", "2000000"])
    else:
        raise SystemExit(f"Missing: {CORPUS_INGEST_PDF}")

def main():
    ap = argparse.ArgumentParser(description="One-fell-swoop ingestion: download/copy sources, place in controlled taxonomy, ingest TXT then PDF, run work_link.")
    ap.add_argument("--title", required=True, help="Work title (used for folder naming).")
    ap.add_argument("--author", default="Unknown", help="Author/editor (used for folder naming).")
    ap.add_argument("--category", default="", help=f"Optional forced category key: one of {', '.join(TAXONOMY.keys())}")
    ap.add_argument("--src", action="append", required=True, help="Source URL or local filepath. Repeat --src for multiple volumes/files.")
    ap.add_argument("--ingest", action="store_true", help="Actually run corpus ingestion after staging files.")
    ap.add_argument("--link", action="store_true", help="Run work_link.py after ingestion.")
    args = ap.parse_args()

    if args.category:
        if args.category not in TAXONOMY:
            raise SystemExit(f"--category must be one of: {', '.join(TAXONOMY.keys())}")

    category_key = args.category or guess_category(args.title, args.author)
    category_path = Path(TAXONOMY.get(category_key, TAXONOMY["unsorted"]))

    work_folder = f"{args.title} - {args.author}".strip()
    work_dir = AI_EBOOKS / category_path / work_folder

    # Stage destinations by type
    txt_dir = work_dir / "TXT"
    pdf_dir = work_dir / "PDF"

    items: list[IngestItem] = []
    for src in args.src:
        vol = parse_vol_idx(src) or parse_vol_idx(args.title)
        is_url = bool(urlparse(src).scheme in ("http", "https"))

        if is_url:
            # infer filename from URL path
            name = Path(urlparse(src).path).name or "downloaded_file"
            ext = Path(name).suffix.lower()
            if ext == "":
                ext = ".txt"  # default guess
            kind = "pdf" if ext in PDF_EXTS else "text"
            base = txt_dir if kind == "text" else pdf_dir

            if vol is not None:
                out_name = f"{slug(args.title)}_vol{vol:02d}{ext}"
            else:
                out_name = f"{slug(args.title)}{ext}"

            out_path = base / out_name
            download_url(src, out_path)
            items.append(IngestItem(src=src, local_path=out_path, kind=kind, vol_idx=vol))
        else:
            p = Path(src).expanduser().resolve()
            if not p.exists():
                raise SystemExit(f"Local source not found: {p}")
            ext = p.suffix.lower()
            kind = "pdf" if ext in PDF_EXTS else "text"
            base = txt_dir if kind == "text" else pdf_dir

            if vol is not None:
                out_name = f"{slug(args.title)}_vol{vol:02d}{ext}"
            else:
                out_name = p.name

            out_path = base / out_name
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out_path)
            items.append(IngestItem(src=str(p), local_path=out_path, kind=kind, vol_idx=vol))

    # Write sources manifest
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "title": args.title,
        "author": args.author,
        "category_key": category_key,
        "category_path": str(category_path),
        "work_dir": str(work_dir),
        "items": [
            {"src": it.src, "local_path": str(it.local_path), "kind": it.kind, "vol_idx": it.vol_idx}
            for it in items
        ],
    }
    (work_dir / "sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nPlaced work at:\n  {work_dir}\nCategory:\n  {category_key} -> {category_path}\n")
    print("Files staged:")
    for it in items:
        print(f"  - {it.kind:4s} vol={it.vol_idx if it.vol_idx else '-'}  {it.local_path.name}")

    if args.ingest:
        # TXT priority
        if txt_dir.exists():
            print("\nIngesting TEXT (priority)...")
            ingest_text_dir(work_dir)
        # PDF fallback
        if pdf_dir.exists():
            print("\nIngesting PDF...")
            ingest_pdf_dir(work_dir)

    if args.link:
        print("\nLinking multi-volume works...")
        run(["python3", str(WORK_LINK)])

    print("\nDone.")

if __name__ == "__main__":
    main()
