#!/usr/bin/env python3
import argparse, json, sqlite3
from pathlib import Path
from typing import Any

def looks_like_text_json(obj: Any) -> bool:
    # Sefaria-style text JSON often has keys: text/he/en, versions, etc.
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if "text" in keys or "he" in keys or "en" in keys:
            v = obj.get("text") or obj.get("en") or obj.get("he")
            if isinstance(v, (list, str)):
                return True
        # Some Sefaria exports use "chapter" / "sections" containing strings
        for k in ("chapters", "sections", "content", "body"):
            if k in keys and isinstance(obj[k], (list, str, dict)):
                # heuristic: if it eventually contains strings, we'll treat as text
                if contains_strings(obj[k]):
                    return True
        # “schema” JSON is typically metadata
        if "contents" in keys and "title" in keys and "categories" in keys:
            return False
        # if it has lots of structural/index-y keys
        if keys.intersection({"contents", "categories", "order", "heTitle", "enShortDesc", "heShortDesc", "corpus"}):
            # could still be text, but usually TOC
            if not keys.intersection({"text", "he", "en"}):
                return False
    elif isinstance(obj, list):
        # if it’s a list of strings or list-lists of strings, it’s probably text-ish
        return contains_strings(obj)
    return False

def contains_strings(x: Any, budget: int = 5000) -> bool:
    # bounded recursion to avoid huge nested structures
    stack = [x]
    seen = 0
    while stack and seen < budget:
        cur = stack.pop()
        seen += 1
        if isinstance(cur, str):
            # ignore tiny tokens; accept real content
            if len(cur.strip()) >= 20:
                return True
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur[:50])  # cap fanout
    return False

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/ai_data/ebooks/_corpus_index/corpus_index.sqlite")
    ap.add_argument("--root", default="/ai_data/ebooks")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    root = Path(args.root)

    rows = list(db.execute(
        "select sha256, rel_path, size_bytes from corpus_items "
        "where status='RAW' and ext='.json' order by size_bytes desc, rel_path"
    ))
    if args.limit and args.limit > 0:
        rows = rows[:args.limit]

    to_text = []
    to_meta = []
    unknown = []

    for r in rows:
        rel = r["rel_path"]
        p = root / rel
        try:
            # Read whole file (most are small). If you ever hit a monster file, we can stream later.
            raw = p.read_text(encoding="utf-8", errors="replace")
            obj = json.loads(raw)
            if looks_like_text_json(obj):
                to_text.append(r)
            else:
                to_meta.append(r)
        except Exception:
            # If JSON parse fails, treat as META + note (usually not a real text payload)
            unknown.append(r)

    print(f"RAW json examined: {len(rows)}")
    print(f"  -> classify RAW_TEXTJSON: {len(to_text)}")
    print(f"  -> classify META:         {len(to_meta)}")
    print(f"  -> parse/other UNKNOWN:   {len(unknown)}")

    def show_sample(label, items):
        print(f"\nSample {label} (up to 10):")
        for r in items[:10]:
            print(" -", r["rel_path"])

    show_sample("RAW_TEXTJSON", to_text)
    show_sample("META", to_meta)
    show_sample("UNKNOWN", unknown)

    if not args.apply:
        print("\nDRY RUN only. Re-run with --apply to write DB updates.")
        return 0

    # Apply updates
    for r in to_text:
        db.execute("update corpus_items set status='RAW_TEXTJSON' where sha256=?", (r["sha256"],))
    for r in to_meta:
        db.execute("update corpus_items set status='META' where sha256=?", (r["sha256"],))
    for r in unknown:
        db.execute(
            "update corpus_items set status='META', notes=coalesce(notes,'') || '\nJSON_PARSE_FAIL' where sha256=?",
            (r["sha256"],)
        )

    db.commit()
    print("\nAPPLIED: DB updated.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
