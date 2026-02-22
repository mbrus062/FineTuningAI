#!/usr/bin/env python3
import os, sys, json, sqlite3, hashlib, time
from pathlib import Path

APP_DIR = Path("/home/mario/FineTuningAI/bookshelf_app")
DB_PATH = APP_DIR / "catalog.sqlite"
OVERRIDES_PATH = APP_DIR / "overrides.json"

# Master PDF roots (add more later if needed)
PDF_ROOTS = [
    Path("/ai_data/ebooks"),
]


def file_id(p: Path, st: os.stat_result) -> str:
    h = hashlib.sha1()
    h.update(str(p).encode("utf-8", "ignore"))
    h.update(str(st.st_size).encode())
    h.update(str(int(st.st_mtime)).encode())
    return h.hexdigest()


import re

VOL_RE = re.compile(r"(?:\bvol(?:ume)?\.?\s*|[\s._-]v)(\d{1,3})\b", re.IGNORECASE)
PAGES_RE = re.compile(r"\(\s*\d+\s*p(?:ages?)?\s*\)", re.IGNORECASE)


def extract_vol_from_path(p: Path) -> str | None:
    # look in filename + parent folders for vol markers like Vol_12, vol. 3, v04
    parts = [p.stem] + [x.name for x in p.parents][:4]
    for s in parts:
        s = s.replace("_", " ")
        m = VOL_RE.search(s)
        if m:
            return m.group(1)
    return None


def clean_name(s: str) -> str:
    s = s.replace("_", " ").replace("  ", " ").strip()
    s = PAGES_RE.sub("", s).strip()
    # trim common trailing clutter like ", 2015" or " 2015"
    s = re.sub(r"[,\s]+(19|20)\d{2}\b.*$", "", s).strip()
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def guess_title_author_spine(p: Path):
    raw = clean_name(p.stem)

    # split "Title - Author" (use last ' - ' split)
    title = raw
    author = ""
    if " - " in raw:
        left, right = raw.rsplit(" - ", 1)
        left = left.strip()
        right = right.strip()
        # heuristic: if right looks like an author chunk, accept it
        if len(right) <= 80 and not right.lower().startswith(("vol", "volume", "v")):
            title = left
            author = right

    vol = extract_vol_from_path(p)

    # build spine: Title — Author — Vol #
    spine = title
    if author:
        spine = f"{title} — {author}"
    if vol:
        spine = f"{spine} — Vol {int(vol)}"

    return title, author, spine


def load_overrides():
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        return {}


def init_db(conn: sqlite3.Connection):
    conn.execute(
        """
    CREATE TABLE IF NOT EXISTS pdfs (
        id TEXT PRIMARY KEY,
        pdf_path TEXT NOT NULL,
        title TEXT NOT NULL,
        spine_title TEXT NOT NULL,
        mtime INTEGER NOT NULL,
        size INTEGER NOT NULL
    );
    """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_title ON pdfs(title);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON pdfs(pdf_path);")
    conn.commit()


def upsert(conn, row):
    conn.execute(
        """
    INSERT INTO pdfs (id, pdf_path, title, spine_title, mtime, size)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      pdf_path=excluded.pdf_path,
      title=excluded.title,
      spine_title=excluded.spine_title,
      mtime=excluded.mtime,
      size=excluded.size;
    """,
        row,
    )


def scan_pdfs():
    for root in PDF_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.pdf"):
            # ignore hidden/systemy dirs if desired
            if "/.trash" in str(p).lower():
                continue
            yield p


def main():
    incremental = "--incremental" in sys.argv

    APP_DIR.mkdir(parents=True, exist_ok=True)
    overrides = load_overrides()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    existing_ids = set()
    if incremental:
        # Load IDs already known; we’ll still update modified files by new hash
        for r in conn.execute("SELECT id FROM pdfs"):
            existing_ids.add(r["id"])

    added = updated = 0
    t0 = time.time()

    for p in scan_pdfs():
        try:
            st = p.stat()
        except OSError:
            continue

        fid = file_id(p, st)
        title, author, spine = guess_title_author_spine(p)
        spine = title

        # Apply saved override if present
        o = overrides.get(fid) or {}
        if "title" in o and o["title"]:
            title = o["title"]
        if "spine_title" in o and o["spine_title"]:
            spine = o["spine_title"]

        row = (fid, str(p), title, spine, int(st.st_mtime), int(st.st_size))
        upsert(conn, row)

        if incremental and fid in existing_ids:
            updated += 1
        else:
            added += 1

    conn.commit()
    conn.close()

    dt = time.time() - t0
    print(
        f"Reindex complete. added={added} updated={updated} incremental={incremental} seconds={dt:.1f}"
    )


if __name__ == "__main__":
    main()
