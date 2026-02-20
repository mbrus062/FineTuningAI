#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_ROOT = Path("/ai_data/ebooks/_text_unified")
DEFAULT_DB   = Path("/ai_data/ebooks/_corpus_index/unified_fts.sqlite")

ALLOWED_EXTS = {".txt"}  # keep it simple/safe for Bookshelf reader


def init_db(con: sqlite3.Connection):
    con.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;

    DROP TABLE IF EXISTS docs;
    DROP TABLE IF EXISTS docs_fts;
    DROP TABLE IF EXISTS docs_fts_data;
    DROP TABLE IF EXISTS docs_fts_idx;
    DROP TABLE IF EXISTS docs_fts_content;
    DROP TABLE IF EXISTS docs_fts_docsize;
    DROP TABLE IF EXISTS docs_fts_config;

    CREATE TABLE docs (
      doc_id INTEGER PRIMARY KEY,
      rel_path TEXT UNIQUE,
      bytes INTEGER,
      mtime REAL
    );

    CREATE VIRTUAL TABLE docs_fts
    USING fts5(
      rel_path UNINDEXED,
      content,
      tokenize = 'unicode61'
    );
    CREATE INDEX idx_docs_rel ON docs(rel_path);
    """)


def iter_files(root: Path, exclude_dirs: set[str]):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTS:
            continue
        # exclude by any path part
        parts = set(p.parts)
        if parts & exclude_dirs:
            continue
        yield p


def main():
    ap = argparse.ArgumentParser(description="Build Bookshelf unified_fts.sqlite from /ai_data/ebooks/_text_unified")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help=f"Root to scan (default: {DEFAULT_ROOT})")
    ap.add_argument("--db", default=str(DEFAULT_DB), help=f"Output DB path (default: {DEFAULT_DB})")
    ap.add_argument("--exclude-dir", action="append", default=[], help="Directory name to exclude (repeatable)")
    ap.add_argument("--exclude-old", action="store_true", help="Exclude any directory named _old")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    db_path = Path(args.db).resolve()

    if not root.exists():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        sys.exit(2)

    exclude = set(args.exclude_dir)
    if args.exclude_old:
        exclude.add("_old")

    tmp_db = db_path.with_suffix(db_path.suffix + ".tmp")

    tmp_db.parent.mkdir(parents=True, exist_ok=True)
    if tmp_db.exists():
        tmp_db.unlink()

    con = sqlite3.connect(str(tmp_db))
    try:
        init_db(con)
        con.commit()

        t0 = time.time()
        n = 0
        con.execute("BEGIN;")

        for p in iter_files(root, exclude):
            rel = p.relative_to(root).as_posix()  # ex: clean_txt/Christian/...
            st = p.stat()
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            con.execute(
                "INSERT INTO docs(rel_path, bytes, mtime) VALUES (?,?,?)",
                (rel, st.st_size, st.st_mtime),
            )
            # rowid matches docs.doc_id because docs.doc_id is INTEGER PRIMARY KEY
            doc_id = con.execute("SELECT doc_id FROM docs WHERE rel_path=?", (rel,)).fetchone()[0]
            con.execute(
                "INSERT INTO docs_fts(rowid, rel_path, content) VALUES (?,?,?)",
                (doc_id, rel, txt),
            )

            n += 1
            if n % 250 == 0:
                con.commit()
                con.execute("BEGIN;")
                dt = time.time() - t0
                print(f"indexed: {n} files  ({dt:.1f}s)")

        con.commit()
        dt = time.time() - t0
        print(f"DONE: indexed {n} files into {tmp_db}  ({dt:.1f}s)")

    finally:
        con.close()

    # atomic replace
    bak = db_path.with_suffix(db_path.suffix + ".bak")
    if db_path.exists():
        try:
            if bak.exists():
                bak.unlink()
        except Exception:
            pass
        db_path.rename(bak)

    tmp_db.rename(db_path)
    print(f"ACTIVE DB: {db_path}")
    print("(Previous DB saved as .bak)")

if __name__ == "__main__":
    main()
