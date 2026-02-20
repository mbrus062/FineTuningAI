#!/usr/bin/env python3
import re, sqlite3, hashlib
from pathlib import Path

DB = Path("/ai_data/ai_corpus/manifest.sqlite")

VOL_PATTERNS = [
    # (Vol. 1 of 2)
    re.compile(r"\(\s*vol\.?\s*(\d+)\s*of\s*(\d+)\s*\)", re.I),
    # Vol. 1 / Vol 02 / Vol_03
    re.compile(r"\bvol\.?\s*0*(\d+)\b", re.I),
    # Volume I / Volume II / Volume 02
    re.compile(r"\bvolume\s+([ivxlcdm]+|\d+)\b", re.I),
    # Vol. I of II (rare)
    re.compile(r"\bvol\.?\s*([ivxlcdm]+)\s*of\s*([ivxlcdm]+)\b", re.I),
]

ROMAN = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10,
         "XI":11,"XII":12,"XIII":13,"XIV":14,"XV":15,"XVI":16,"XVII":17,"XVIII":18,"XIX":19,"XX":20}

def roman_to_int(s: str):
    s = s.strip().upper()
    return ROMAN.get(s)

def clean_title(fn: str) -> str:
    # remove extension
    t = re.sub(r"\.[A-Za-z0-9]+$", "", fn)
    # remove common trailing metadata like " - Author, YYYY (409p)"
    # but keep the core title + author if it helps uniqueness
    t = re.sub(r"\s*\(\s*\d+\s*p\.\s*\)\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*\(\s*\d+\s*p\)\s*$", "", t, flags=re.I)

    # remove volume markers
    t2 = t
    t2 = re.sub(r"\(\s*vol\.?\s*\d+\s*of\s*\d+\s*\)", "", t2, flags=re.I)
    t2 = re.sub(r"\bvol\.?\s*\d+\b", "", t2, flags=re.I)
    t2 = re.sub(r"\bvolume\s+([ivxlcdm]+|\d+)\b", "", t2, flags=re.I)

    # normalize whitespace
    t2 = re.sub(r"\s{2,}", " ", t2).strip(" -_")
    return t2.strip()

def parse_volume(fn: str):
    """Return (vol_idx, vol_total) if detectable, else (None, None)."""
    for pat in VOL_PATTERNS:
        m = pat.search(fn)
        if not m:
            continue

        g = m.groups()
        # pattern specific handling
        if len(g) == 2 and g[0].isdigit() and g[1].isdigit():
            return int(g[0]), int(g[1])

        if len(g) == 1:
            v = g[0]
            if v.isdigit():
                return int(v), None
            r = roman_to_int(v)
            return (r, None) if r else (None, None)

        if len(g) == 2:
            a, b = g
            if a.isdigit() and b.isdigit():
                return int(a), int(b)
            ra, rb = roman_to_int(a), roman_to_int(b)
            if ra and rb:
                return ra, rb

    return None, None

def make_work_id(work_title: str) -> str:
    # stable id: sha1 of normalized title
    norm = re.sub(r"\s+", " ", work_title.strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()

def main():
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row

    # only link things we can treat as “books”: pdf/txt for now
    rows = con.execute("""
        SELECT doc_id, rel_path, ext
        FROM docs
        WHERE ext IN ('pdf','txt')
    """).fetchall()

    total = len(rows)
    updated = 0

    for i, r in enumerate(rows, 1):
        rel = r["rel_path"] or ""
        fn = rel.split("/")[-1]

        vol_idx, vol_total = parse_volume(fn)
        work_title = clean_title(fn)
        if not work_title:
            continue

        work_id = make_work_id(work_title)

        con.execute("""
            UPDATE docs
            SET work_id=?, work_title=?, vol_idx=?, vol_total=?
            WHERE doc_id=?
        """, (work_id, work_title, vol_idx, vol_total, r["doc_id"]))
        updated += 1

        if i % 2000 == 0:
            con.commit()
            print(f"Progress: {i:,}/{total:,} docs scanned; {updated:,} updated")

    con.commit()
    con.close()
    print(f"Done. Scanned: {total:,}. Updated: {updated:,}.")

if __name__ == "__main__":
    main()
