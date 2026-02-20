#!/usr/bin/env python3
import argparse
import os
import sqlite3
import subprocess
from pathlib import Path

DB_DEFAULT = "/ai_data/ebooks/_corpus_index/corpus_index.sqlite"
DIGEST_DEFAULT = "/ai_data/ebooks/_digested"
LOG_DEFAULT = "/ai_data/ebooks/_corpus_index/digest_errors.log"

def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def write_text(out_path: Path, text: str) -> None:
    ensure_parent(out_path)
    out_path.write_text(text, encoding="utf-8", errors="replace")

def digest_pdf(src: Path) -> str:
    # pdftotext must be installed (poppler-utils)
    cp = run(["pdftotext", str(src), "-"])
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "pdftotext failed")
    return cp.stdout

def digest_epub(src: Path) -> str:
    # Requires: unzip + lynx installed
    tmp = Path("/tmp") / f"epub_{os.getpid()}_{src.stem}"
    if tmp.exists():
        subprocess.run(["rm", "-rf", str(tmp)], check=False)
    tmp.mkdir(parents=True, exist_ok=True)

    try:
        cp = run(["unzip", "-q", str(src), "-d", str(tmp)])
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "unzip failed")

        # Collect html/xhtml anywhere, stable order
        files = sorted([p for p in tmp.rglob("*") if p.suffix.lower() in (".html", ".htm", ".xhtml")])
        if not files:
            raise RuntimeError("No HTML/XHTML found inside EPUB")

        parts = []
        for f in files:
            cp2 = run(["lynx", "-dump", "-nolist", str(f)])
            if cp2.returncode == 0 and cp2.stdout.strip():
                parts.append(cp2.stdout)
        return "\n\n".join(parts)
    finally:
        subprocess.run(["rm", "-rf", str(tmp)], check=False)

def digest_xml(src: Path) -> str:
    # Try “best effort” xml-to-text:
    # Prefer lynx if XML is actually XHTML-ish; otherwise fall back to stripping tags crudely.
    # (We can improve later with xsltproc/BeautifulSoup if you want.)
    cp = run(["lynx", "-dump", "-nolist", str(src)])
    if cp.returncode == 0 and cp.stdout.strip():
        return cp.stdout

    # crude tag-strip fallback:
    data = src.read_text(encoding="utf-8", errors="replace")
    import re
    data = re.sub(r"<[^>]+>", " ", data)
    data = re.sub(r"[ \t]+", " ", data)
    data = re.sub(r"\n\s+\n", "\n\n", data)
    return data

def digest_html(src: Path) -> str:
    cp = run(["lynx", "-dump", "-nolist", str(src)])
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "lynx failed")
    return cp.stdout

def normalize_text(t: str) -> str:
    t = t.replace("\r", "")
    # strip trailing whitespace per line
    t = "\n".join(line.rstrip() for line in t.splitlines())
    return t.strip() + "\n"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--root", default="/ai_data/ebooks", help="Base path for rel_path resolution")
    ap.add_argument("--out", default=DIGEST_DEFAULT)
    ap.add_argument("--log", default=LOG_DEFAULT)
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit (use for testing)")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row

    out_root = Path(args.out)
    src_root = Path(args.root)
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    q = """
    select sha256, rel_path, ext
    from corpus_items
    where status='RAW'
      and ext in ('.pdf','.epub','.xml','.html','.htm','.xhtml')
    order by ext, rel_path
    """
    rows = list(db.execute(q))
    if args.limit and args.limit > 0:
        rows = rows[:args.limit]

    ok = 0
    fail = 0

    for r in rows:
        item_id = r["sha256"]
        rel_path = r["rel_path"]
        ext = (r["ext"] or "").lower()

        src = src_root / rel_path
        out_path = out_root / (rel_path + ".txt")

        try:
            if not src.exists():
                raise FileNotFoundError(f"missing source: {src}")

            if ext == ".pdf":
                text = digest_pdf(src)
            elif ext == ".epub":
                text = digest_epub(src)
            elif ext == ".xml":
                text = digest_xml(src)
            elif ext in (".html", ".htm", ".xhtml"):
                text = digest_html(src)
            else:
                raise RuntimeError(f"unsupported ext: {ext}")

            text = normalize_text(text)
            write_text(out_path, text)

            db.execute(
                "update corpus_items set status='DIGESTED' where sha256=?",
                (item_id,)
            )
            db.commit()
            ok += 1

        except Exception as e:
            db.execute(
                "update corpus_items set status='FAILED', notes=coalesce(notes,'') || '\nDIGEST_FAIL: ' || ? where sha256=?",
                (str(e), item_id)
            )
            db.commit()
            fail += 1

            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"FAIL\t{rel_path}\t{ext}\t{e}\n")

    print(f"DIGEST DONE ok={ok} fail={fail} out={out_root} log={log_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
