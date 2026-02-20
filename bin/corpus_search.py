#!/usr/bin/env python3
import argparse
import re
import sqlite3
from pathlib import Path

DB = Path("/ai_data/ai_corpus/manifest.sqlite")

BOILERPLATE = (
  "project gutenberg",
  "start of the project gutenberg ebook",
  "transcriber's note",
  "gutenberg license",
)

def pick_focus_term(query: str) -> str:
  q = query.replace('"', " ").replace("'", " ")
  tokens = re.split(r"\s+", q.strip())
  for t in tokens:
    up = t.upper()
    if up in ("AND", "OR", "NOT"):
      continue
    t = re.sub(r"[^0-9A-Za-z_-]", "", t)
    if len(t) >= 3:
      return t
  return ""

def extract_window(text: str, term: str, width: int = 220) -> str:
  if not text:
    return ""
  clean = " ".join(text.split())
  if not term:
    return clean[: (2 * width)] + ("…" if len(clean) > 2 * width else "")
  m = re.search(re.escape(term), clean, flags=re.IGNORECASE)
  if not m:
    return clean[: (2 * width)] + ("…" if len(clean) > 2 * width else "")

  start = max(0, m.start() - width)
  end = min(len(clean), m.end() + width)
  left_ellipsis = "…" if start > 0 else ""
  right_ellipsis = "…" if end < len(clean) else ""
  window = clean[start:end]

  window = re.sub(
    re.escape(term),
    lambda mm: f"[[{mm.group(0)}]]",
    window,
    flags=re.IGNORECASE,
  )
  return f"{left_ellipsis}{window}{right_ellipsis}"

def main():
  ap = argparse.ArgumentParser(
    description="Search the AI corpus (SQLite FTS) and print top matching chunks."
  )
  ap.add_argument("query", nargs="+", help='FTS query (quotes for phrases; AND/OR/NOT supported).')
  ap.add_argument("--limit", type=int, default=10, help="Number of results to show (default: 10).")
  ap.add_argument("--ext", default="", help="Restrict to a file extension, e.g. pdf or txt.")
  ap.add_argument("--like", default="", help="Restrict to docs whose rel_path contains this substring (case-insensitive).")
  ap.add_argument("--path-eq", default="", help="Restrict to an exact rel_path match (single file).")
  ap.add_argument("--work-id", default="", help="Restrict to a linked work_id (multi-volume sets).")
  ap.add_argument("--work-like", default="", help="Restrict to work_title containing this substring (case-insensitive).")
  ap.add_argument("--window", type=int, default=220, help="Context window size (chars on each side of match). Default 220.")
  ap.add_argument("--no-boilerplate-skip", action="store_true", help="Do not skip common boilerplate chunks.")
  args = ap.parse_args()

  q = " ".join(args.query).strip()
  if not q:
    ap.error("query is required")

  focus = pick_focus_term(q)
  con = sqlite3.connect(str(DB))

  where_meta = []
  params_meta = []

  if args.ext:
    where_meta.append("ext = ?")
    params_meta.append(args.ext.lower())

  if args.like:
    where_meta.append("lower(rel_path) like ?")
    params_meta.append(f"%{args.like.lower()}%")

  if args.path_eq:
    where_meta.append("rel_path = ?")
    params_meta.append(args.path_eq)

  if args.work_id:
    where_meta.append("work_id = ?")
    params_meta.append(args.work_id)

  if args.work_like:
    where_meta.append("lower(work_title) like ?")
    params_meta.append(f"%{args.work_like.lower()}%")

  meta_clause = ("WHERE " + " AND ".join(where_meta)) if where_meta else ""
  fetch_n = max(args.limit * 8, args.limit)

  sql = f"""
    SELECT
      bm25(chunks_fts) AS score,
      chunks_fts.chunk_id,
      chunks_fts.doc_id
    FROM chunks_fts
    JOIN (
      SELECT doc_id
      FROM docs
      {meta_clause}
    ) d ON d.doc_id = chunks_fts.doc_id
    WHERE chunks_fts MATCH ?
    ORDER BY score
    LIMIT ?
  """

  rows = con.execute(sql, (*params_meta, q, fetch_n)).fetchall()
  if not rows:
    print("No results.")
    con.close()
    return

  printed = 0
  for score, chunk_id, doc_id in rows:
    meta = con.execute(
      "SELECT rel_path, ext, work_title, work_id, vol_idx, vol_total FROM docs WHERE doc_id=?",
      (doc_id,)
    ).fetchone()
    if meta:
      rel, ext, work_title, work_id, vol_idx, vol_total = meta
    else:
      rel, ext, work_title, work_id, vol_idx, vol_total = ("?", "?", None, None, None, None)

    text_row = con.execute("SELECT text FROM chunks WHERE chunk_id=?", (chunk_id,)).fetchone()
    full_text = text_row[0] if text_row else ""

    if (not args.no_boilerplate_skip) and full_text:
      low = full_text.lower()
      if any(b in low for b in BOILERPLATE):
        continue

    snip = extract_window(full_text, focus, width=args.window)

    extra = ""
    if work_id and work_title:
      v = ""
      if vol_idx is not None:
        v = f" vol={vol_idx}" + (f"/{vol_total}" if vol_total else "")
      extra = f"  work='{work_title}' work_id={work_id[:12]}…{v}"

    print(f"\n[{rel}] ({ext})  chunk={chunk_id}{extra}")
    print(snip)

    printed += 1
    if printed >= args.limit:
      break

  con.close()

if __name__ == "__main__":
  main()
