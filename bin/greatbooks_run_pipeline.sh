#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Great Books Pipeline (Steps 2–6)
#   2) Fetch (manifest -> Incoming)
#   3) Quarantine (Incoming -> Incoming/_quarantine_TIMESTAMP)
#   4) Promote (quarantine -> Primary) (copy-only, never overwrite)
#   5) Archive quarantine (-> Quarantine_Archive)
#   6) Run ebook_inventory
#
# SAFE BY DEFAULT:
#   - No overwrites: cp --update=none
#   - Shows PLAN before copying
#   - Requires typing YES unless --yes
# ============================================================

ROOT="/ai_data/ebooks/Great_Books"
MANIFEST="$ROOT/Acquisition/Manifests/great_books_manifest.tsv"
INCOMING="$ROOT/Acquisition/Incoming"
ARCHIVE="$ROOT/Acquisition/Quarantine_Archive"
LOGDIR="$ROOT/Logs"

FETCH_SCRIPT="$HOME/FineTuningAI/bin/greatbooks_fetch.sh"
INVENTORY_SCRIPT="$HOME/FineTuningAI/bin/ebook_inventory"

YES_MODE=0
if [[ "${1:-}" == "--yes" ]]; then
  YES_MODE=1
fi

die() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

need date
need mkdir
need awk
need sed
need cp
need mv
need ls
need find

[[ -f "$MANIFEST" ]] || die "Manifest not found: $MANIFEST"
[[ -d "$INCOMING" ]] || die "Incoming dir not found: $INCOMING"
[[ -x "$FETCH_SCRIPT" ]] || die "Fetch script not executable: $FETCH_SCRIPT"
[[ -f "$INVENTORY_SCRIPT" ]] || die "Inventory script not found: $INVENTORY_SCRIPT"

mkdir -p "$LOGDIR" "$ARCHIVE"

ts="$(date +%F_%H%M%S)"
runlog="$LOGDIR/pipeline_${ts}.log"

echo "=== Great Books Pipeline ===" | tee -a "$runlog"
echo "Manifest:  $MANIFEST"        | tee -a "$runlog"
echo "Incoming:  $INCOMING"        | tee -a "$runlog"
echo "Archive:   $ARCHIVE"         | tee -a "$runlog"
echo "Log:       $runlog"          | tee -a "$runlog"
echo "" | tee -a "$runlog"

# ------------------------------
# Step 2) Fetch
# ------------------------------
echo "== Step 2: FETCH ==" | tee -a "$runlog"
"$FETCH_SCRIPT" 2>&1 | tee -a "$runlog"
echo "" | tee -a "$runlog"

# ------------------------------
# Step 3) Quarantine whatever is now in Incoming (files only)
# ------------------------------
echo "== Step 3: QUARANTINE ==" | tee -a "$runlog"
qdir="$INCOMING/_quarantine_${ts}"
mkdir -p "$qdir"

# Move only files in Incoming root (not directories)
shopt -s nullglob
files=( "$INCOMING"/* )
moved=0

for p in "${files[@]}"; do
  base="$(basename "$p")"
  [[ -d "$p" ]] && continue
  mv -v "$p" "$qdir/" | tee -a "$runlog"
  moved=1
done

if [[ "$moved" -eq 0 ]]; then
  echo "Nothing new downloaded into Incoming. No files to quarantine." | tee -a "$runlog"
  echo "Stopping (nothing to promote)." | tee -a "$runlog"
  exit 0
fi

echo "" | tee -a "$runlog"
echo "Quarantine folder created:" | tee -a "$runlog"
ls -lh "$qdir" | tee -a "$runlog"
echo "" | tee -a "$runlog"

# ------------------------------
# Step 4) Promote (copy-only, no overwrite) based on manifest
# ------------------------------
echo "== Step 4: PROMOTE (PLAN) ==" | tee -a "$runlog"
echo "Quarantine source: $qdir" | tee -a "$runlog"
echo "" | tee -a "$runlog"

# Build plan: for each manifest row, see if that file exists in quarantine
# Manifest format:
# out_relpath<TAB>url<TAB>note
plan_count=0

# Using awk to read manifest robustly with tabs
while IFS=$'\t' read -r out_rel url note; do
  [[ -z "${out_rel:-}" ]] && continue
  [[ "${out_rel:0:1}" == "#" ]] && continue

  fname="$(basename "$out_rel")"
  src="$qdir/$fname"
  dst="$ROOT/$out_rel"

  if [[ -f "$src" ]]; then
    echo "WILL COPY: $src  ->  $dst" | tee -a "$runlog"
    plan_count=$((plan_count+1))
  fi
done < "$MANIFEST"

if [[ "$plan_count" -eq 0 ]]; then
  echo "No files in quarantine matched manifest filenames. Nothing to promote." | tee -a "$runlog"
  echo "Leaving quarantine in place: $qdir" | tee -a "$runlog"
  exit 0
fi

echo "" | tee -a "$runlog"

if [[ "$YES_MODE" -eq 0 ]]; then
  echo "If the PLAN above looks correct, type YES to proceed:" | tee -a "$runlog"
  read -r ans
  if [[ "$ans" != "YES" ]]; then
    echo "Not proceeding. Leaving quarantine in place: $qdir" | tee -a "$runlog"
    exit 1
  fi
else
  echo "--yes provided: proceeding without prompt." | tee -a "$runlog"
fi

echo "" | tee -a "$runlog"
echo "== Step 4: PROMOTE (COPYING - no overwrite) ==" | tee -a "$runlog"

# Copy with --update=none to prevent overwrite
copied=0
while IFS=$'\t' read -r out_rel url note; do
  [[ -z "${out_rel:-}" ]] && continue
  [[ "${out_rel:0:1}" == "#" ]] && continue

  fname="$(basename "$out_rel")"
  src="$qdir/$fname"
  dst="$ROOT/$out_rel"

  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    echo "COPY: $src -> $dst" | tee -a "$runlog"
    cp -a --update=none "$src" "$dst" 2>&1 | tee -a "$runlog"
    copied=$((copied+1))
  fi
done < "$MANIFEST"

echo "" | tee -a "$runlog"
echo "Copied files: $copied" | tee -a "$runlog"
echo "" | tee -a "$runlog"

# ------------------------------
# Step 5) Archive quarantine folder
# ------------------------------
echo "== Step 5: ARCHIVE QUARANTINE ==" | tee -a "$runlog"
mv -v "$qdir" "$ARCHIVE/" | tee -a "$runlog"
echo "Archived to: $ARCHIVE/$(basename "$qdir")" | tee -a "$runlog"
echo "" | tee -a "$runlog"

# ------------------------------
# Step 6) Run inventory
# ------------------------------
echo "== Step 6: RUN ebook_inventory ==" | tee -a "$runlog"
python3 "$INVENTORY_SCRIPT" 2>&1 | tee -a "$runlog"
echo "" | tee -a "$runlog"

echo "=== PIPELINE COMPLETE ===" | tee -a "$runlog"
echo "Log saved to: $runlog" | tee -a "$runlog"
