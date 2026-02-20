#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path("/ai_data/ai_corpus/manifest.sqlite")
DB.parent.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL;")
con.execute("PRAGMA synchronous=NORMAL;")

con.executescript("""
CREATE TABLE IF NOT EXISTS docs (
  doc_id       TEXT PRIMARY KEY,
  rel_path     TEXT NOT NULL,
  abs_path     TEXT NOT NULL,
  ext          TEXT NOT NULL,
  size_bytes   INTEGER NOT NULL,
  mtime_ns     INTEGER NOT NULL,
  file_hash    TEXT,          -- optional later (sha256 of bytes)
  norm_hash    TEXT,          -- sha256 of normalized text
  norm_path    TEXT,          -- /ai_data/ai_corpus/normalized/<doc_id>.txt
  title        TEXT,
  author       TEXT,
  tradition    TEXT,
  source       TEXT,
  language     TEXT,
  status       TEXT,
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_docs_rel_path ON docs(rel_path);
CREATE INDEX IF NOT EXISTS idx_docs_ext      ON docs(ext);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id     TEXT PRIMARY KEY,
  doc_id       TEXT NOT NULL,
  chunk_idx    INTEGER NOT NULL,
  start_char   INTEGER NOT NULL,
  end_char     INTEGER NOT NULL,
  text         TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(doc_id) REFERENCES docs(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

-- Full-text search over chunk text
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED,
  doc_id   UNINDEXED,
  text,
  tokenize = 'unicode61'
);

-- Keep FTS in sync (simple triggers)
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(chunk_id, doc_id, text) VALUES (new.chunk_id, new.doc_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  DELETE FROM chunks_fts WHERE chunk_id = old.chunk_id;
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  UPDATE chunks_fts SET text=new.text WHERE chunk_id=new.chunk_id;
END;
""")

con.commit()
con.close()
print(f"Initialized: {DB}")
