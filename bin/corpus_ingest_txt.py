#!/usr/bin/env python3
import os
import re
import sqlite3
import hashlib
from pathlib import Path

SRC_ROOT = Path("/ai_data/ebooks")
OUT_ROOT = Path("/ai_data/ai_corpus")
NORM_DIR = OUT_ROOT / "normalized"
DB = OUT_ROOT / "manifest.sqlite"

NORM_DIR.mkdir(parents=True, exist_ok=True)

def sha256_text(s: str) -> str:
  return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()

def doc_id_for(rel_path: str) -> str:
  return hashlib.sha1(rel_path.encode("utf-8", "ignore")).hexdigest()

def normalize_text(raw: str) -> str:
  # conservative normalization: keep paragraph breaks, clean control chars
  raw = raw.replace("\r\n", "\n").replace("\r", "\n")
  raw = re.sub(r"[^\S\n]+", " ", raw)          # collapse horizontal whitespace
  raw = re.sub(r"\n{4,}", "\n\n\n", raw)       # cap huge vertical gaps
  return raw.strip() + "\n"

def chunk_paragraph_aware(text: str, target_chars=2500, overlap_chars=200):
  # char-based chunking; deterministic; paragraph-aware by splitting on blank lines
  paras = re.split(r"\n\s*\n", text)
  chunks = []
  buf = ""
  start = 0
  pos = 0

  def emit(chunk_text, chunk_start, chunk_end):
    chunks.append((chunk_text, chunk_start, chunk_end))

  for p in paras:
    p = p.strip()
    if not p:
      pos += 2
      continue

    candidate = (buf + ("\n\n" if buf else "") + p)
    if len(candidate) <= target_chars:
      buf = candidate
    else:
      if buf:
        end = start + len(buf)
        emit(buf, start, end)

        # overlap: keep tail
        tail = buf[-overlap_chars:] if overlap_chars and len(buf) > overlap_chars else ""
        buf = (tail + ("\n\n" if tail else "") + p).strip()
        start = end - len(tail)
      else:
        # single huge paragraph: hard cut
        big = p
        while len(big) > target_chars:
          part = big[:target_chars]
          end = start + len(part)
          emit(part, start, end)
          big = big[target_chars - overlap_chars:]
          start = end - overlap_chars
        buf = big

    pos += len(p) + 2

  if buf:
    end = start + len(buf)
    emit(buf, start, end)

  return chunks

def upsert_doc(con, doc):
  con.execute("""
    INSERT INTO docs(doc_id, rel_path, abs_path, ext, size_bytes, mtime_ns, norm_hash, norm_path, updated_at)
    VALUES(?,?,?,?,?,?,?,?,datetime('now'))
    ON CONFLICT(doc_id) DO UPDATE SET
      rel_path=excluded.rel_path,
      abs_path=excluded.abs_path,
      ext=excluded.ext,
      size_bytes=excluded.size_bytes,
      mtime_ns=excluded.mtime_ns,
      norm_hash=excluded.norm_hash,
      norm_path=excluded.norm_path,
      updated_at=datetime('now')
  """, doc)

def delete_chunks_for_doc(con, doc_id: str):
  con.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))

def main():
  con = sqlite3.connect(DB)
  con.execute("PRAGMA journal_mode=WAL;")
  con.execute("PRAGMA synchronous=NORMAL;")

  # Canonical subtree only
  CANON = SRC_ROOT / "_text_unified" / "clean_txt"
  paths = list(CANON.rglob("*.txt"))
  print(f"Using canonical subtree: {CANON}")
  print(f"Found TXT: {len(paths):,}")

  done = 0
  for ap in paths:
    # avoid merged duplicates
    if ap.name.lower() == "merged.txt":
      continue

    try:
      rel = ap.relative_to(SRC_ROOT).as_posix()
    except Exception:
      continue

    # exclude derived digests inside canonical tree
    if "/_digested/" in rel:
      continue

    st = ap.stat()
    doc_id = doc_id_for(rel)
    norm_path = (NORM_DIR / f"{doc_id}.txt").as_posix()

    row = con.execute(
      "SELECT size_bytes, mtime_ns, norm_hash FROM docs WHERE doc_id=?",
      (doc_id,)
    ).fetchone()

    # incremental: skip if size/mtime match and norm exists
    if row and row[0] == st.st_size and row[1] == st.st_mtime_ns and os.path.exists(norm_path):
      done += 1
      continue

    raw = ap.read_text(errors="ignore")
    norm = normalize_text(raw)
    nh = sha256_text(norm)

    # write normalized
    Path(norm_path).write_text(norm, encoding="utf-8")

    # update doc record
    upsert_doc(con, (
      doc_id, rel, str(ap.resolve()), "txt", st.st_size, st.st_mtime_ns, nh, norm_path
    ))

    # rebuild chunks for this doc
    delete_chunks_for_doc(con, doc_id)
    chunks = chunk_paragraph_aware(norm)

    for idx, (ct, s, e) in enumerate(chunks):
      chunk_id = hashlib.sha1(f"{doc_id}:{idx}:{s}:{e}".encode("utf-8")).hexdigest()
      con.execute(
        "INSERT INTO chunks(chunk_id, doc_id, chunk_idx, start_char, end_char, text) VALUES(?,?,?,?,?,?)",
        (chunk_id, doc_id, idx, s, e, ct)
      )

    con.commit()
    done += 1
    if done % 500 == 0:
      print(f"Processed: {done:,}/{len(paths):,}")

  con.close()
  print("Done.")

if __name__ == "__main__":
  main()
