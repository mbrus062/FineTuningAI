#!/usr/bin/env bash
set -euo pipefail

# ============ CONFIG ============
ROOT="/ai_data/ebooks/Great_Books"
MANIFEST="$ROOT/Acquisition/Manifests/great_books_manifest.tsv"
INCOMING="$ROOT/Acquisition/Incoming"
LOGDIR="$ROOT/Logs"

# Auto-pick the newest quarantine dir (by name sorting; your dirs include date)
# Auto-pick newest quarantine folder.
# Prefer Incoming, but if Incoming is empty (because you archived it), fall back to Quarantine_Archive.
INCOMING="$ROOT/Acquisition/Incoming"
ARCHIVE="$ROOT/Acquisition/Quarantine_Archive"

pick_newest_quar() {
  local base="$1"
  # List matching dirs, sort, pick last (newest by name)
  ls -1d "$base"/_quarantine_* 2>/dev/null | sort | tail -n 1
}

QUAR="$(pick_newest_quar "$INCOMING")"
if [[ -z "${QUAR:-}" ]]; then
  QUAR="$(pick_newest_quar "$ARCHIVE")"
fi

# Safety: never overwrite
CP_OPTS=(-a --update=none -v)

# ============ HELPERS ============
die() { echo "ERROR: $*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

# ============ PRE-FLIGHT ============
need awk
need sed
need cp
need mkdir
need date

[[ -f "$MANIFEST" ]] || die "Manifest not found: $MANIFEST"
[[ -d "$INCOMING" ]] || die "Incoming dir not found: $INCOMING"
[[ -n "$QUAR" && -d "$QUAR" ]] || die "No quarantine folder found under: $INCOMING"

ts="$(date +%F_%H%M%S)"
LOG="$LOGDIR/promote_$ts.log"
mkdir -p "$LOGDIR"

echo "=== Great Books Promote (quarantine -> Primary) ===" | tee -a "$LOG"
echo "Manifest:   $MANIFEST" | tee -a "$LOG"
echo "Quarantine: $QUAR" | tee -a "$LOG"
echo "Log:        $LOG" | tee -a "$LOG"
echo | tee -a "$LOG"

echo "Files currently in quarantine:" | tee -a "$LOG"
ls -lh "$QUAR" | tee -a "$LOG"
echo | tee -a "$LOG"

# ============ DRY-RUN PLAN ============
echo "=== PLAN (what would be copied) ===" | tee -a "$LOG"
# manifest columns: out_relpath<TAB>url<TAB>note
# We only care about out_relpath filename, and destination directory under Primary/...
awk -F'\t' '
  BEGIN { OFS="\t" }
  $0 ~ /^#/ { next }
  NF < 1 { next }
  {
    out = $1
    n = split(out, parts, "/")
    fname = parts[n]
    destdir = ""
    for (i=1; i<n; i++) {
      destdir = (destdir=="" ? parts[i] : destdir "/" parts[i])
    }
    print fname, destdir
  }
' "$MANIFEST" | while IFS=$'\t' read -r fname destdir; do
  src="$QUAR/$fname"
  dest="$ROOT/$destdir/$fname"
  if [[ -f "$src" ]]; then
    echo "WILL COPY: $src  ->  $dest" | tee -a "$LOG"
  fi
done

echo | tee -a "$LOG"
echo "If the PLAN above looks correct, type YES to proceed:" | tee -a "$LOG"
read -r ans
[[ "$ans" == "YES" ]] || die "User aborted (did not type YES)."

# ============ COPY PHASE ============
echo | tee -a "$LOG"
echo "=== COPYING (no overwrite) ===" | tee -a "$LOG"

copied=0
skipped=0

awk -F'\t' '
  $0 ~ /^#/ { next }
  NF < 1 { next }
  { print $1 }
' "$MANIFEST" | while read -r out; do
  # out is like: Primary/Classics/Dante_....txt
  fname="${out##*/}"
  rel_dir="${out%/*}"              # Primary/Classics
  src="$QUAR/$fname"
  destdir="$ROOT/$rel_dir"
  dest="$destdir/$fname"

  if [[ -f "$src" ]]; then
    mkdir -p "$destdir"
    echo "COPY: $src -> $dest" | tee -a "$LOG"
    cp "${CP_OPTS[@]}" "$src" "$destdir/" | tee -a "$LOG" || true
  fi
done

echo | tee -a "$LOG"
echo "=== DONE COPYING ===" | tee -a "$LOG"

# ============ OPTIONAL: inventory refresh ============
if [[ -x ~/FineTuningAI/bin/ebook_inventory ]]; then
  echo | tee -a "$LOG"
  echo "Running ebook_inventory..." | tee -a "$LOG"
  python3 ~/FineTuningAI/bin/ebook_inventory >/dev/null
  echo "ebook_inventory complete." | tee -a "$LOG"
else
  echo "NOTE: ~/FineTuningAI/bin/ebook_inventory not executable; skipping." | tee -a "$LOG"
fi

echo | tee -a "$LOG"
echo "Log saved to: $LOG" | tee -a "$LOG"
echo "SUCCESS." | tee -a "$LOG"
