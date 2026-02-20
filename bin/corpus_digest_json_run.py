#!/usr/bin/env python3
import argparse, json, re, sqlite3
from pathlib import Path
from typing import Any, Iterable, List, Union

def normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # collapse excessive blank lines
    s = re.sub(r"\n{4,}", "\n\n\n", s)
    return s.strip() + "\n"

def flatten_text(obj: Any) -> List[str]:
    """
    Best-effort extraction for Sefaria-style JSON:
      - dict with 'text' or 'he'/'en' or nested structures
      - lists of strings or lists of lists
    Returns list of paragraph-ish strings.
    """
    out: List[str] = []

    def add(x: Any):
        if x is None:
            return
        if isinstance(x, str):
            t = x.strip()
            if t:
                out.append(t)
        elif isinstance(x, (int, float)):
            out.append(str(x))
        elif isinstance(x, list):
            for it in x:
                add(it)
        elif isinstance(x, dict):
            # common keys that hold the payload
            for k in ("text", "he", "en", "content"):
                if k in x:
                    add(x[k])
                    return
            # sometimes nested by 'chapter', 'sections', etc.
            # fallback: scan values
            for v in x.values():
                add(v)
        else:
            # unknown type
            out.append(str(x))

    add(obj)
    return out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/ai_data/ebooks/_corpus_index/corpus_index.sqlite")
    ap.add_argument("--root", default="/ai_data/ebooks")
    ap.add_argument("--out", default="/ai_data/ebooks/_digested_json")
    ap.add_argument("--log", default="/ai_data/ebooks/_corpus_index/digest_json_errors.log")
    ap.add_argument("--limit", type=int, default=250)
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
    where status='RAW_TEXTJSON' and ext='.json'
    order by rel_path
    """
    rows = list(db.execute(q))
    if args.limit and args.limit > 0:
        rows = rows[:args.limit]

    ok = 0
    fail = 0

    for r in rows:
        item_id = r["sha256"]
        rel_path = r["rel_path"]
        src = src_root / rel_path
        out_path = out_root / (rel_path + ".txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if not src.exists():
                raise FileNotFoundError(f"missing source: {src}")

            data = json.loads(src.read_text(encoding="utf-8", errors="replace"))
            parts = flatten_text(data)

            # Join with paragraph breaks; keep some structure
            text = "\n\n".join(parts)
            text = normalize_text(text)

            out_path.write_text(text, encoding="utf-8")

            db.execute("update corpus_items set status='DIGESTED' where sha256=?", (item_id,))
            db.commit()
            ok += 1

        except Exception as e:
            fail += 1
            db.execute(
                "update corpus_items set status='FAILED', notes=coalesce(notes,'') || '\nDIGEST_JSON_FAIL: ' || ? where sha256=?",
                (str(e), item_id),
            )
            db.commit()
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"FAIL\t{rel_path}\t.json\t{e}\n")

    print(f"DIGEST_JSON DONE ok={ok} fail={fail} out={out_root} log={log_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
