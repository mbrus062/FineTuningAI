#!/usr/bin/env bash
set -euo pipefail

# Vermes section-splitting helper
# Location: ~/FineTuningAI/helpers/vermes_split_helpers.sh
# Load with: source ~/FineTuningAI/helpers/vermes_split_helpers.sh
#
# Splits the Vermes IA text witness into named works using start/end regex markers.
# You can tune the markers as needed; output is provenance-stamped.

VERMES_TXT="/ai_data/ebooks/Jewish/Second_Temple/DSS/Translations/Vermes/Dead_Sea_Scrolls_Vermes_Complete_English.txt"
VERMES_PDF="/ai_data/ebooks/Jewish/Second_Temple/DSS/Translations/Vermes/Dead_Sea_Scrolls_Vermes_Complete_English_scan.pdf"

# Usage:
#   vermes_extract "DirName" "Pretty Title" "START_REGEX" "END_REGEX"
# Extracts from first line matching START_REGEX up to line BEFORE first match of END_REGEX after that.
vermes_extract () {
  local dir="$1"
  local title="$2"
  local start_re="$3"
  local end_re="$4"

  local base="/ai_data/ebooks/Jewish/Second_Temple/DSS/Sectarian/${dir}"
  rm -rf "$base"
  mkdir -p "$base/english" "$base/metadata"

  # Find start line
  local start_line
  start_line=$(grep -n -m 1 -E "$start_re" "$VERMES_TXT" | cut -d: -f1 || true)
  if [ -z "${start_line:-}" ]; then
    echo "ERROR: start marker not found for $dir: $start_re" >&2
    return 2
  fi

  # Find end line AFTER start
  local end_line
  end_line=$(tail -n +"$start_line" "$VERMES_TXT" | grep -n -m 1 -E "$end_re" | cut -d: -f1 || true)
  if [ -z "${end_line:-}" ]; then
    echo "ERROR: end marker not found for $dir: $end_re" >&2
    return 3
  fi
  # Convert relative end_line to absolute, and stop the line before the marker
  end_line=$((start_line + end_line - 2))

  local out="$base/english/${dir}_Vermes_english.txt"

  {
    echo "# ${title} — English (Vermes)"
    echo "# Source: Geza Vermes, Complete Dead Sea Scrolls in English"
    echo "# Witness: $VERMES_TXT (primary); $VERMES_PDF (reference)"
    echo "# Extraction: lines ${start_line}-${end_line} from Vermes IA text witness"
    echo ""
    sed -n "${start_line},${end_line}p" "$VERMES_TXT"
  } > "$out"

  cat > "$base/metadata/${dir}_vermes.json" <<JSON
{
  "work": "${title}",
  "corpus": "DSS Sectarian / Non-biblical",
  "source_volume": "Geza Vermes — Complete Dead Sea Scrolls in English",
  "witness_text": "${VERMES_TXT}",
  "witness_pdf": "${VERMES_PDF}",
  "line_range": "${start_line}-${end_line}",
  "language": "English",
  "notes": "Derived from Vermes IA text witness; section boundaries defined by regex markers."
}
JSON

  echo "DONE: Vermes/${dir}  (lines ${start_line}-${end_line})"
}


# Find the first occurrence line number for a case-insensitive keyword/pattern
# Usage: vermes_find "community rule"
vermes_find () {
  local pat="$1"
  grep -n -i -m 1 -E "$pat" "$VERMES_TXT" || true
}

# Extract from a START pattern up to just before the NEXT pattern (both regex)
# Usage: vermes_extract_next "Dir" "Title" "START_RE" "NEXT_RE"
vermes_extract_next () {
  local dir="$1"
  local title="$2"
  local start_re="$3"
  local next_re="$4"

  local start_line
  start_line=$(grep -n -i -m 1 -E "$start_re" "$VERMES_TXT" | cut -d: -f1 || true)
  if [ -z "${start_line:-}" ]; then
    echo "ERROR: start marker not found for $dir: $start_re" >&2
    return 2
  fi

  local next_rel
  next_rel=$(tail -n +"$((start_line+1))" "$VERMES_TXT" | grep -n -i -m 1 -E "$next_re" | cut -d: -f1 || true)
  if [ -z "${next_rel:-}" ]; then
    echo "ERROR: next marker not found after $dir: $next_re" >&2
    return 3
  fi
  local end_line=$(( (start_line+1) + next_rel - 2 ))

  local base="/ai_data/ebooks/Jewish/Second_Temple/DSS/Sectarian/${dir}"
  rm -rf "$base"
  mkdir -p "$base/english" "$base/metadata"

  local out="$base/english/${dir}_Vermes_english.txt"
  {
    echo "# ${title} — English (Vermes)"
    echo "# Source: Geza Vermes, Complete Dead Sea Scrolls in English"
    echo "# Witness: $VERMES_TXT (primary); $VERMES_PDF (reference)"
    echo "# Extraction: lines ${start_line}-${end_line}"
    echo ""
    sed -n "${start_line},${end_line}p" "$VERMES_TXT"
  } > "$out"

  cat > "$base/metadata/${dir}_vermes.json" <<JSON
{
  "work": "${title}",
  "corpus": "DSS Sectarian / Non-biblical",
  "source_volume": "Geza Vermes — Complete Dead Sea Scrolls in English",
  "witness_text": "${VERMES_TXT}",
  "witness_pdf": "${VERMES_PDF}",
  "line_range": "${start_line}-${end_line}",
  "language": "English",
  "notes": "Split by start/next heading regex markers."
}
JSON

  echo "DONE: Vermes/${dir}  (lines ${start_line}-${end_line})"
}
