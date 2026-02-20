#!/usr/bin/env bash
set -euo pipefail

# DSS extraction helpers (Abegg/Flint/Ulrich volume)
# Location: ~/FineTuningAI/helpers/dss_extract_helpers.sh
# Load with: source ~/FineTuningAI/helpers/dss_extract_helpers.sh
#
# These helpers extract a page-range from the IA PDF, merge, pdftotext,
# prepend a provenance header, and write minimal metadata.

PDF_DEFAULT="/ai_data/ebooks/Jewish/Biblical/DSS/Translations/Dead_Sea_Scrolls_Bible_Abegg-Flint-Ulrich.pdf"

# Usage:
#   extract_book "DirName" "Pretty Title" STARTPDF ENDPDF BOOKSTART BOOKEND
# Writes to:
#   /ai_data/ebooks/Jewish/Biblical/DSS/<DirName>/{source,english,metadata}
extract_book () {
  local dir="$1"
  local title="$2"
  local sp="$3"
  local ep="$4"
  local bstart="$5"
  local bend="$6"
  local pdf="${7:-$PDF_DEFAULT}"

  local base="/ai_data/ebooks/Jewish/Biblical/DSS/${dir}"
  rm -rf "$base"
  mkdir -p "$base/source" "$base/english" "$base/metadata"

  pdfseparate -f "$sp" -l "$ep" "$pdf" "$base/source/page_%03d.pdf"
  pdfunite "$base/source/page_"*.pdf "$base/source/${dir}_DSS_Abegg-Flint-Ulrich.pdf"

  pdftotext "$base/source/${dir}_DSS_Abegg-Flint-Ulrich.pdf" \
    "$base/english/${dir}_DSS_Abegg-Flint-Ulrich_english.txt"

  local OUT="$base/english/${dir}_DSS_Abegg-Flint-Ulrich_english.txt"
  local TMP="$base/english/.tmp.txt"
  mv "$OUT" "$TMP"

  cat > "$OUT" <<HDR
# ${title} — Biblical text reconstructed from DSS witnesses (English)
# Source volume: The Dead Sea Scrolls Bible (Abegg, Flint, Ulrich)
# Extraction: PDF pages ${sp}–${ep} (Internet Archive scan)
# Book pages: ${bstart}–${bend}
# Notes: Includes editorial and variant notes per source volume.
HDR
  echo "" >> "$OUT"
  cat "$TMP" >> "$OUT"
  rm -f "$TMP"

  cat > "$base/metadata/${dir}_dss_abegg_flint_ulrich.json" <<JSON
{
  "work": "${title}",
  "corpus": "Biblical DSS",
  "source_volume": "The Dead Sea Scrolls Bible",
  "editors_translators": ["Martin Abegg Jr.", "Peter Flint", "Eugene Ulrich"],
  "pdf_page_range": "${sp}-${ep}",
  "book_page_range": "${bstart}-${bend}",
  "language": "English",
  "notes": "Derived from PDF extraction; includes editorial and variant notes."
}
JSON

  echo "DONE: $dir  (PDF $sp-$ep | Book $bstart-$bend)"
}

# Usage:
#   extract_deut "DirName" "Pretty Title" STARTPDF ENDPDF BOOKSTART BOOKEND
# Writes to:
#   /ai_data/ebooks/Jewish/Second_Temple/Deuterocanonical/<DirName>/{source,english,metadata}
extract_deut () {
  local dir="$1"
  local title="$2"
  local sp="$3"
  local ep="$4"
  local bstart="$5"
  local bend="$6"
  local pdf="${7:-$PDF_DEFAULT}"

  local base="/ai_data/ebooks/Jewish/Second_Temple/Deuterocanonical/${dir}"
  rm -rf "$base"
  mkdir -p "$base/source" "$base/english" "$base/metadata"

  pdfseparate -f "$sp" -l "$ep" "$pdf" "$base/source/page_%03d.pdf"
  pdfunite "$base/source/page_"*.pdf "$base/source/${dir}_DSSBible_Abegg-Flint-Ulrich.pdf"

  pdftotext "$base/source/${dir}_DSSBible_Abegg-Flint-Ulrich.pdf" \
    "$base/english/${dir}_DSSBible_Abegg-Flint-Ulrich_english.txt"

  local OUT="$base/english/${dir}_DSSBible_Abegg-Flint-Ulrich_english.txt"
  local TMP="$base/english/.tmp.txt"
  mv "$OUT" "$TMP"

  cat > "$OUT" <<HDR
# ${title} — Deuterocanonical / Second Temple text (English)
# Source volume: The Dead Sea Scrolls Bible (Abegg, Flint, Ulrich)
# Extraction: PDF pages ${sp}–${ep} (Internet Archive scan)
# Book pages: ${bstart}–${bend}
# Notes: Kept outside Biblical/DSS to preserve canon/category boundaries.
HDR
  echo "" >> "$OUT"
  cat "$TMP" >> "$OUT"
  rm -f "$TMP"

  cat > "$base/metadata/${dir}_dssbible_abegg_flint_ulrich.json" <<JSON
{
  "work": "${title}",
  "corpus": "Second Temple / Deuterocanonical",
  "source_volume": "The Dead Sea Scrolls Bible",
  "editors_translators": ["Martin Abegg Jr.", "Peter Flint", "Eugene Ulrich"],
  "pdf_page_range": "${sp}-${ep}",
  "book_page_range": "${bstart}-${bend}",
  "language": "English",
  "notes": "Derived from PDF extraction; kept separate from Biblical/DSS."
}
JSON

  echo "DONE: Deut/$dir  (PDF $sp-$ep | Book $bstart-$bend)"
}
