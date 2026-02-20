#!/usr/bin/env bash
set -euo pipefail

INCOMING="/ai_data/ebooks/Great_Books/Acquisition/Incoming"
LOGDIR="/ai_data/ebooks/Great_Books/Acquisition/Logs"
mkdir -p "$INCOMING" "$LOGDIR"

log="$LOGDIR/gb_fetch_$(date +%F_%H%M%S).log"
exec > >(tee -a "$log") 2>&1

echo "=== Great Books fetch started: $(date -Is) ==="

# Usage:
#   gb_fetch.sh "URL" "output_filename.pdf"
fetch () {
  local url="$1"
  local out="$2"
  echo "---"
  echo "Fetching: $url"
  echo "Into:     $INCOMING/$out"
  curl -L --fail --retry 3 --retry-delay 2 -o "$INCOMING/$out" "$url"
  ls -lh "$INCOMING/$out"
}

# Put your fetch(...) lines below this line.
# Example:
# fetch "https://..." "Aquinas_Summa_Theologica_English_Dominican_Vol1_IA.pdf"

echo "=== Great Books fetch finished: $(date -Is) ==="
