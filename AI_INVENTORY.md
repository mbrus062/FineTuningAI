# AI System Inventory
Generated: Sun Feb 22 12:58:08 PM MST 2026

## Project State (FineTuningAI)

- Repo path: /home/mario/FineTuningAI
- Git remote origin: https://github.com/mbrus062/FineTuningAI.git
- Branch: main
- Head commit: 5709ef7 2026-02-22 12:31:49 -0700 Fix Bookshelf UI mount; serve correct index.html; stabilize 8787 bookshelf
- Working tree changes: 7 item(s)

  Changed files (git status --porcelain):
  -  M AI_INVENTORY.md
  -  M bin/ai_inventory
  - ?? bin/bookshelf_launch_pdf
  - ?? bin/bookshelf_start
  - ?? bookshelf_app/catalog.sqlite
  - ?? bookshelf_app/overrides.json
  - ?? bookshelf_app/ui/index.html.bak.2026-02-22-1152

## Project Identity

- This is the FineTuningAI research platform.
- Primary purpose: AI-assisted historical, theological, and corpus research.
- GitHub-backed, version-controlled system.
- Inventory file is the authoritative context rehydration document.

## Development Guardrails

- GitHub repo is the source of truth.
- Always run 'git status' before modifying scripts.
- Commit and push after structural or architectural changes.
- Never overwrite working scripts without versioning.
- Bookshelf must be launched via: bin/bookshelf_launch.
- PDFs = reading UI; TXTs = AI ingestion corpus.
- Corpus flow: ingest → index → query.

## Bookshelf Wiring

- Bookshelf UI served by: /home/mario/FineTuningAI/bookshelf_app/ui/index.html
- Bookshelf server: /home/mario/FineTuningAI/bin/bookshelf_pdf_server.py (uvicorn on 127.0.0.1:8787)
- Bookshelf DB: /home/mario/FineTuningAI/bookshelf_app/catalog.sqlite (table: pdfs)
- Reindexer: /home/mario/FineTuningAI/bin/bookshelf_reindex.py (populates catalog.sqlite)
- Port: 8787 (local only)
- Routes: / redirects to /_bookshelf/ ; JSON index at /api/index

- Desktop file: /home/mario/Desktop/Bookshelf.desktop
- Desktop Exec line:
Exec=gnome-terminal -- bash -lc '/home/mario/FineTuningAI/bin/bookshelf_start'

- Launcher present (expected):
yes

## Library Roots (Bookshelf vs Corpus)

## Library Roots (Bookshelf vs Corpus)

- Bookshelf PDF library root: /ai_data/ebooks
  - realpath: /ai_data/ebooks
  - size: 213G
  - pdf: 47741
  - txt: 33755

### Corpus candidates

- Corpus candidate: /ai_data/ai_corpus
  - realpath: /ai_data/ai_corpus
  - size: 168G
  - pdf: 45503
  - txt: 58513
  - top dirs: extracted_text index index_egw index_egw_complete index_harvard logs manifests manifest.sqlite 

- Corpus candidate: /ai_data/ebooks
  - realpath: /ai_data/ebooks
  - size: 213G
  - pdf: 47741
  - txt: 33755
  - top dirs: 5000 Year Leap.pdf America's Great Depression Ancient History Anderson,Robert-Coming_Prince(b).pdf An Essay Concerning Human Understanding - John Locke Anglo Saxon Chronicle Anglo_Saxon_Norse An Introduction to Christian Economics - Gary North 

- Corpus candidate: /home/mario/ai_corpus
  - realpath: /ai_data/ai_corpus
  - size: 0
  - pdf: 0
  - txt: 0
  - top dirs: extracted_text index index_egw index_egw_complete index_harvard logs manifests manifest.sqlite 

## Ebook ingestion workflow (standard)

### Phase 1: Extract/copy text into ai_corpus (per-library outputs)

- Script: ~/ingest_ebooks_phase1.sh
- Default library if no argument is passed: ~/ebooks
- Recommended for manual daily imports: point it at /ai_data/ebooks/_imports/manual_incoming/YYYY-MM-DD

Examples:
  bash ~/ingest_ebooks_phase1.sh /ai_data/ebooks/_imports/manual_incoming/2026-02-20
  bash ~/ingest_ebooks_phase1.sh ~/ebooks/History/Reference/Cambridge_Ancient_History

Outputs created per-library:
  - OUT:      ~/ai_corpus/extracted_text/<library_label>__<LIB_ID>/
  - MANIFEST: ~/ai_corpus/manifests/manifest_<LIB_ID>.csv

Quick checks:
  grep -i needs_ocr ~/ai_corpus/manifests/manifest_<LIB_ID>.csv | head
  grep -i needs_archive_expansion ~/ai_corpus/manifests/manifest_<LIB_ID>.csv | head

### Phase 1b: Expand flagged archives and ingest their contents

- Script: ~/expand_archives_and_ingest.sh
- Run it against the specific manifest for the library you just ingested:

Examples:
  bash ~/expand_archives_and_ingest.sh ~/ai_corpus/manifests/manifest_3c35161e889c.csv
  bash ~/expand_archives_and_ingest.sh ~/ai_corpus/manifests/manifest_fbc5f7ce404b.csv

Result:
  - Archive rows get updated to archive_extracted
  - New extracted texts from inside archives get added to the SAME manifest
  - Any newly-discovered OCR candidates get flagged as needs_ocr


## Canonical Corpus Ingestion (Standard Procedure)

### What this does
- Converts PDFs/TXTs/EPUBs to extracted .txt in a per-library output folder.
- Writes a per-library manifest CSV (so runs don’t collide).
- Flags archives (.zip/.7z/.tar/.gz) for expansion, and flags likely-scanned PDFs as needs_ocr.

### Key scripts
- Ingest script:   ~/ingest_ebooks_phase1.sh
- Archive expander (uses a manifest): ~/expand_archives_and_ingest.sh

### IMPORTANT: ingest defaults to ~/ebooks unless you pass a path
- If you run:  bash ~/ingest_ebooks_phase1.sh
  it will scan: ~/ebooks
- To ingest a specific incoming batch, ALWAYS pass the path:

#### Standard manual-incoming batch (example)
SRC="/ai_data/ebooks/_imports/manual_incoming/YYYY-MM-DD"
bash ~/ingest_ebooks_phase1.sh "$SRC"

#### Cambridge example (direct folder ingest)
bash ~/ingest_ebooks_phase1.sh "~/ebooks/History/Reference/Cambridge_Ancient_History"

### After ingest: expand archives (if any were flagged)
1) Find flagged archives in that library’s manifest:
   - The ingest output prints: MANIFEST: /home/mario/ai_corpus/manifests/manifest_<LIB_ID>.csv
2) Expand + ingest contents of flagged archives:
   bash ~/expand_archives_and_ingest.sh "/home/mario/ai_corpus/manifests/manifest_<LIB_ID>.csv"

### Quick checks
- OCR candidates:
  grep -i needs_ocr "/home/mario/ai_corpus/manifests/manifest_<LIB_ID>.csv" | head
- Archives still pending:
  grep -i needs_archive_expansion "/home/mario/ai_corpus/manifests/manifest_<LIB_ID>.csv" | head

### Notes
- Keep PDFs for reading; extracted .txt is what feeds AI.
- If a PDF yields a tiny extracted txt (<~2000 bytes), it’s likely scanned → needs OCR later.

## Manifest & Corpus Summary

- Manifest files: 3
- Total manifest rows (including headers): 100
- Extracted text files: 48855
- Extracted text total size: 18G

## OCR Ticklers (needs_ocr queue)

- needs_ocr flagged rows across manifests: 1

  Newest OCR-flagged items (up to 15):
  - 0	/ai_data/ebooks/_imports/manual_incoming/2026-02-20/History_Modern_Europe/Modern_Europe_1789-1914.pdf	/ai_data/ai_corpus/extracted_text/ai_data__ebooks___imports__manual_incoming__2026-02-20__3c35161e889c/History_Modern_Europe__Modern_Europe_1789-1914.pdf.txt	needs_ocr

  Queue folder: /ai_data/ebooks/_ocr_queue
  (Batch OCR will operate on everything in that directory.)
