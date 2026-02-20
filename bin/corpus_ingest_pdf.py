#!/usr/bin/env python3
import os
import re
import sqlite3
import hashlib
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import itertools

SRC_ROOT_DEFAULT = Path("/ai_data/ebooks")
OUT_ROOT = Path("/ai_data/ai_corpus")
NORM_DIR = OUT_ROOT / "normalized"
DB = OUT_ROOT / "manifest.sqlite"
LOG_DIR = OUT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
NORM_DIR.mkdir(parents=True, exist_ok=True)

FAIL_LOG = LOG_DIR / "pdf_ingest_failures.log"

def sha256_text(s: str) -> str:
  return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()

def doc_id_for(rel_path: str) -> str:
  return hashlib.sha1(rel_path.encode("utf-8", "ignore")).hexdigest()

def normalize_text(raw: str) -> str:
  raw = raw.replace("\r\n", "\n").replace("\r", "\n")
  raw = re.sub(r"[^\S\n]+", " ", raw)
  raw = re.sub(r"\n{4,}", "\n\n\n", raw)
  return raw.strip() + "\n"

def chunk_paragraph_aware(text: str, target_chars=2500, overlap_chars=200):
  paras = re.split(r"\n\s*\n", text)
  chunks = []
  buf = ""
  start = 0

  def emit(chunk_text, chunk_start, chunk_end):
    chunks.append((chunk_text, chunk_start, chunk_end))

  for p in paras:
    p = p.strip()
    if not p:
      continue

    candidate = (buf + ("\n\n" if buf else "") + p)
    if len(candidate) <= target_chars:
      buf = candidate
    else:
      if buf:
        end = start + len(buf)
        emit(buf, start, end)
        tail = buf[-overlap_chars:] if overlap_chars and len(buf) > overlap_chars else ""
        buf = (tail + ("\n\n" if tail else "") + p).strip()
        start = end - len(tail)
      else:
        big = p
        while len(big) > target_chars:
          part = big[:target_chars]
          end = start + len(part)
          emit(part, start, end)
          big = big[target_chars - overlap_chars:]
          start = end - overlap_chars
        buf = big

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

def pdftotext_extract(pdf_path: Path) -> str:
  cmd = ["pdftotext", "-nopgbrk", "-layout", str(pdf_path), "-"]
  r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
  if r.returncode != 0:
    raise RuntimeError(r.stderr.decode("utf-8", "ignore").strip() or f"pdftotext failed rc={r.returncode}")
  return r.stdout.decode("utf-8", "ignore")

def should_skip(rel: str) -> bool:
  if "/_text_unified/clean_txt/" in rel:
    return True
  if "/_digested/" in rel:
    return True
  return False

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--root", default=str(SRC_ROOT_DEFAULT), help="Root directory to scan for PDFs")
  ap.add_argument("--src-root", default=str(SRC_ROOT_DEFAULT), help="Base root used to compute rel_path (usually /ai_data/ebooks)")
  ap.add_argument("--limit", type=int, default=0, help="Process at most N PDFs (0 = no limit)")
  ap.add_argument("--min-text", type=int, default=200, help="Minimum extracted chars to accept (scan-only below this)")
  args = ap.parse_args()

  scan_root = Path(args.root)
  src_root = Path(args.src_root)

  con = sqlite3.connect(DB)
  con.execute("PRAGMA journal_mode=WAL;")
  con.execute("PRAGMA synchronous=NORMAL;")

  it = scan_root.rglob("*.pdf")
  pdfs_iter = itertools.islice(it, args.limit) if args.limit and args.limit > 0 else it

  done = 0
  failed = 0
  seen = 0

  for pdf in pdfs_iter:
    seen += 1
    try:
      rel = pdf.relative_to(src_root).as_posix()
    except Exception:
      # If root isn't under src_root, fall back to rel within scan_root
      rel = pdf.relative_to(scan_root).as_posix()

    if should_skip(rel):
      continue

    st = pdf.stat()
    doc_id = doc_id_for(rel)
    norm_path = (NORM_DIR / f"{doc_id}.txt").as_posix()

    row = con.execute(
      "SELECT size_bytes, mtime_ns FROM docs WHERE doc_id=?",
      (doc_id,)
    ).fetchone()

    if row and row[0] == st.st_size and row[1] == st.st_mtime_ns and os.path.exists(norm_path):
      done += 1
      continue

    try:
      raw = pdftotext_extract(pdf)
      norm = normalize_text(raw)

      if len(norm.strip()) < args.min_text:
        raise RuntimeError("extracted text too short (likely scanned/image-only PDF)")

      nh = sha256_text(norm)
      Path(norm_path).write_text(norm, encoding="utf-8")

      upsert_doc(con, (
        doc_id, rel, str(pdf.resolve()), "pdf", st.st_size, st.st_mtime_ns, nh, norm_path
      ))

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

      if done % 25 == 0:
        print(f"Processed PDFs: {done:,} (failures: {failed:,})  last={rel}")

    except Exception as ex:
      failed += 1
      with FAIL_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()}  {rel}\n  {ex}\n")

  con.close()
  print(f"Scan root: {scan_root}")
  print(f"Done. PDFs processed: {done:,}, failures: {failed:,}, scanned: {seen:,}")
  print(f"Failure log: {FAIL_LOG}")

if __name__ == "__main__":
  main()
