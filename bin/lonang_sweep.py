#!/usr/bin/env python3
import re
import sys
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DOWNLOADS_PAGE = "https://lonang.com/downloads/"
ALLOWED_EXT = {".pdf", ".epub", ".mobi", ".azw3", ".zip"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def safe_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\-. ()]+", "_", s)
    return s[:180].strip()

def main():
    out_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/ai_data/ebooks/LONANG/Downloads")
    out_root.mkdir(parents=True, exist_ok=True)

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (compatible; research-downloader/1.0)"})

    r = sess.get(DOWNLOADS_PAGE, timeout=60)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        url = urljoin(DOWNLOADS_PAGE, href)
        path = urlparse(url).path.lower()
        ext = Path(path).suffix
        if ext in ALLOWED_EXT:
            label = a.get_text(" ", strip=True) or ext.upper()
            links.append((label, url))

    # de-dupe while preserving order
    seen = set()
    uniq = []
    for label, url in links:
        if url not in seen:
            seen.add(url)
            uniq.append((label, url))

    manifest = out_root / "manifest.tsv"
    sha_file = out_root / "sha256.txt"

    with manifest.open("w", encoding="utf-8") as mf:
        mf.write("label\turl\toutfile\n")
        for label, url in uniq:
            filename = Path(urlparse(url).path).name
            filename = safe_name(filename)
            outfile = out_root / filename

            mf.write(f"{label}\t{url}\t{outfile}\n")

            if outfile.exists() and outfile.stat().st_size > 0:
                continue  # already downloaded

            print(f"GET {url}")
            with sess.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with outfile.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

    # write hashes after downloads
    with sha_file.open("w", encoding="utf-8") as sf:
        for p in sorted(out_root.glob("*")):
            if p.is_file() and p.name not in {"manifest.tsv", "sha256.txt"}:
                sf.write(f"{sha256_file(p)}  {p.name}\n")

    print(f"\nDONE: {len(uniq)} file links recorded")
    print(f"Manifest: {manifest}")
    print(f"SHA256:   {sha_file}")

if __name__ == "__main__":
    main()
