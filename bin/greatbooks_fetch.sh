#!/usr/bin/env bash
set -euo pipefail

GB="/ai_data/ebooks/Great_Books"
MAN="$GB/Acquisition/Manifests/great_books_manifest.tsv"
IN="$GB/Acquisition/Incoming"
LOG="$GB/Logs/fetch_$(date +%F_%H%M%S).log"

mkdir -p "$IN"
touch "$LOG"

if [[ ! -f "$MAN" ]]; then
  echo "ERROR: manifest not found: $MAN" | tee -a "$LOG"
  exit 1
fi

echo "=== Great Books Fetch ===" | tee -a "$LOG"
echo "Manifest: $MAN" | tee -a "$LOG"
echo "Incoming: $IN" | tee -a "$LOG"
echo "Log: $LOG" | tee -a "$LOG"
echo "" | tee -a "$LOG"

# Downloader choice: prefer aria2c if installed; fall back to wget; then curl
dl() {
  local url="$1"
  local out="$2"

  if command -v aria2c >/dev/null 2>&1; then
    aria2c -x 8 -s 8 -k 1M --allow-overwrite=true -o "$(basename "$out")" -d "$(dirname "$out")" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$out" "$url"
  else
    curl -L --fail -o "$out" "$url"
  fi
}

while IFS=$'\t' read -r out_rel url note; do
  [[ -z "${out_rel// }" ]] && continue
  [[ "$out_rel" =~ ^# ]] && continue

  # Normalize filename for Incoming
  fname="$(basename "$out_rel")"
  out="$IN/$fname"

  echo "FETCH: $fname" | tee -a "$LOG"
  echo "  URL:  $url" | tee -a "$LOG"
  echo "  NOTE: $note" | tee -a "$LOG"

  dl "$url" "$out" |& tee -a "$LOG"
  echo "" | tee -a "$LOG"
done < "$MAN"

echo "DONE. Files in: $IN" | tee -a "$LOG"
