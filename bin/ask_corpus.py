#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

DB = Path("/ai_data/ai_corpus/manifest.sqlite")
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

BOILERPLATE = (
    "project gutenberg",
    "start of the project gutenberg ebook",
    "transcriber's note",
    "gutenberg license",
)

STOPWORDS = {
    "the","a","an","and","or","not","to","of","in","on","for","with","by","as","at","from",
    "is","are","was","were","be","been","being","does","do","did","that","this","these","those",
    "it","its","he","she","they","them","his","her","their","you","your","i","we","our","us",
    "what","how","why","who","whom","which","when","where",
    "volume","volumes","book","books","chapter","chapters","argue","argues","connect","connection",
    "summarize","summary","doctrine","relate","relates","relation","within","about"
}

ANCHOR_TERMS = (
    "predestination",
    "predestinate",
    "election",
    "elect",
    "reprobate",
    "reprobation",
    "grace",
    "faith",
    "justification",
    "providence",
    "will",
    "free",
    "responsibility",
    "sin",
    "corruption",
    "merit",
    "works",
    "calling",
)

def connect_db():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    return con

def tokenize_for_fts(text: str):
    t = text.lower()
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')
    t = t.replace("—", " ").replace("–", " ")
    t = re.sub(r"[^\w]+", " ", t)
    words = [w for w in t.split() if w and w not in STOPWORDS]
    return words

def fts_term(tok: str) -> str:
    if re.fullmatch(r"[a-z0-9_]+", tok, flags=re.I):
        return tok
    tok = tok.replace('"', '""')
    return f'"{tok}"'

def make_or_fts_query(question: str, max_terms: int = 12) -> str:
    words = tokenize_for_fts(question)
    if not words:
        return ""
    words = sorted(set(words), key=lambda w: (-len(w), w))
    words = words[:max_terms]
    return " OR ".join(fts_term(w) for w in words)

def make_anchor_first_query(question: str) -> str:
    qlow = question.lower()
    hits = []
    for t in ANCHOR_TERMS:
        if t in qlow:
            hits.append(t)

    baseline = ["predestination", "election", "grace", "justification", "faith"]
    for b in baseline:
        if b not in hits:
            hits.append(b)

    seen = set()
    out = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)

    return " OR ".join(fts_term(h) for h in out)

def search_chunks(con, fts_q, k, ext="", like="", path_eq="", work_id="", work_like=""):
    where_meta = []
    params_meta = []

    if ext:
        where_meta.append("ext = ?")
        params_meta.append(ext.lower())

    if like:
        where_meta.append("lower(rel_path) like ?")
        params_meta.append(f"%{like.lower()}%")

    if path_eq:
        where_meta.append("rel_path = ?")
        params_meta.append(path_eq)

    if work_id:
        where_meta.append("work_id = ?")
        params_meta.append(work_id)

    if work_like:
        where_meta.append("lower(work_title) like ?")
        params_meta.append(f"%{work_like.lower()}%")

    meta_clause = ("WHERE " + " AND ".join(where_meta)) if where_meta else ""
    fetch_n = max(k * 60, k)

    sql = f"""
      SELECT bm25(chunks_fts) AS score, chunks_fts.chunk_id
      FROM chunks_fts
      JOIN (
        SELECT doc_id FROM docs {meta_clause}
      ) d ON d.doc_id = chunks_fts.doc_id
      WHERE chunks_fts MATCH ?
      ORDER BY score
      LIMIT ?
    """

    try:
        rows = con.execute(sql, (*params_meta, fts_q, fetch_n)).fetchall()
    except sqlite3.OperationalError as e:
        raise sqlite3.OperationalError(f"FTS query error: {e}\nQuery was: {fts_q!r}")

    out = []
    for r in rows:
        cid = r["chunk_id"]
        txt = con.execute("SELECT text FROM chunks WHERE chunk_id=?", (cid,)).fetchone()
        if not txt:
            continue

        low = txt["text"].lower()
        if any(b in low for b in BOILERPLATE):
            continue

        out.append(cid)
        if len(out) >= k:
            break

    return out

def fetch_chunk(con, chunk_id):
    row = con.execute("""
      SELECT d.rel_path, d.ext, d.work_title, d.work_id, d.vol_idx, d.vol_total, c.chunk_id, c.text
      FROM chunks c
      JOIN docs d ON d.doc_id = c.doc_id
      WHERE c.chunk_id = ?
    """, (chunk_id,)).fetchone()

    if not row:
        return ("?", "?", None, None, None, None, chunk_id, "")

    return (
        row["rel_path"], row["ext"],
        row["work_title"], row["work_id"], row["vol_idx"], row["vol_total"],
        row["chunk_id"], row["text"]
    )

def build_prompt(question, sources):
    # HARD constraints to prevent drift
    system = """You are a careful scholarly assistant.
You MUST answer the QUESTION exactly as asked.
Use ONLY the provided SOURCES.
Do NOT ask the user for more context.
If sources are insufficient, say: "Insufficient sources to answer fully." and explain what is missing in 1–2 sentences.
Do NOT say "the text you provided" or "the excerpts"—these are internal sources.
Cite claims inline as (rel_path chunk=<chunk_id>).
Do not invent citations.
Output format:
- 1 paragraph answer (5–9 sentences).
- then a short bullet list of 3–6 key citations, each bullet = what it supports + citation.
"""

    src_blocks = []
    for i, (rel, ext, work_title, work_id, vol_idx, vol_total, cid, txt) in enumerate(sources, 1):
        head = f"[SOURCE {i}] {rel} ({ext}) chunk={cid}"
        if work_id and work_title:
            v = ""
            if vol_idx is not None:
                v = f" vol={vol_idx}" + (f"/{vol_total}" if vol_total else "")
            head += f"  work='{work_title}' work_id={work_id}{v}"
        src_blocks.append(head + "\n" + txt.strip() + "\n")

    user = "QUESTION:\n" + question + "\n\nSOURCES:\n\n" + "\n".join(src_blocks)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

def ollama_chat(model, messages, temperature, top_p, num_ctx):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_ctx": num_ctx
        }
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode("utf-8"))

    return data["message"]["content"].strip()

def main():
    ap = argparse.ArgumentParser("Ask questions grounded in your local corpus")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--ext", default="")
    ap.add_argument("--like", default="")
    ap.add_argument("--path-eq", default="")
    ap.add_argument("--work-id", default="")
    ap.add_argument("--work-like", default="")
    ap.add_argument("--model", default="command-r:latest")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--top-p", type=float, default=0.9)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--show-sources", action="store_true")
    ap.add_argument("--fts", default="", help="Override the FTS query directly (advanced). Example: 'predestination OR grace'")
    ap.add_argument("--debug-fts", action="store_true", help="Print the FTS queries tried.")
    args = ap.parse_args()

    question = " ".join(args.question).strip()
    con = connect_db()

    tried = []
    chunk_ids = []

    if args.fts.strip():
        fts_q = args.fts.strip()
        tried.append(("--fts", fts_q))
        chunk_ids = search_chunks(con, fts_q, args.k, ext=args.ext, like=args.like,
                                  path_eq=args.path_eq, work_id=args.work_id, work_like=args.work_like)
    else:
        fts_anchor = make_anchor_first_query(question)
        tried.append(("ANCHOR", fts_anchor))
        if fts_anchor:
            chunk_ids = search_chunks(con, fts_anchor, args.k, ext=args.ext, like=args.like,
                                      path_eq=args.path_eq, work_id=args.work_id, work_like=args.work_like)

        if not chunk_ids:
            fts_or = make_or_fts_query(question)
            tried.append(("OR", fts_or))
            if fts_or:
                chunk_ids = search_chunks(con, fts_or, args.k, ext=args.ext, like=args.like,
                                          path_eq=args.path_eq, work_id=args.work_id, work_like=args.work_like)

        if not chunk_ids:
            words = tokenize_for_fts(question)
            if words:
                one = sorted(set(words), key=lambda w: (-len(w), w))[0]
                one = fts_term(one)
                tried.append(("SINGLE", one))
                chunk_ids = search_chunks(con, one, args.k, ext=args.ext, like=args.like,
                                          path_eq=args.path_eq, work_id=args.work_id, work_like=args.work_like)

    if not chunk_ids:
        con.close()
        print("No relevant chunks found.")
        if tried:
            print("Tried FTS queries:")
            for tag, tq in tried:
                print(f"  - {tag}: {tq!r}")
        sys.exit(1)

    sources = [fetch_chunk(con, cid) for cid in chunk_ids]
    con.close()

    if args.debug_fts:
        print("Tried FTS queries:")
        for tag, tq in tried:
            print(f"  - {tag}: {tq!r}")
        print("=" * 80)

    messages = build_prompt(question, sources)
    answer = ollama_chat(args.model, messages, args.temperature, args.top_p, args.num_ctx)
    print(answer)

    if args.show_sources:
        print("\n" + "=" * 80)
        for rel, ext, work_title, work_id, vol_idx, vol_total, cid, txt in sources:
            head = f"\n[{rel}] ({ext}) chunk={cid}"
            if work_id and work_title:
                v = ""
                if vol_idx is not None:
                    v = f" vol={vol_idx}" + (f"/{vol_total}" if vol_total else "")
                head += f"  work='{work_title}' work_id={work_id}{v}"
            print(head + "\n" + txt.strip())

if __name__ == "__main__":
    main()
