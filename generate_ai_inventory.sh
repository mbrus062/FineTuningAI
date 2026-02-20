#!/usr/bin/env bash

OUT=~/FineTuningAI/AI_SYSTEM_INVENTORY.md
BASES=(
  "$HOME"
  "$HOME/ai_corpus"
  "$HOME/FineTuningAI"
)

echo "# AI System Inventory" > "$OUT"
echo "Generated: $(date)" >> "$OUT"
echo >> "$OUT"

echo "## Python Scripts" >> "$OUT"
for b in "${BASES[@]}"; do
  find "$b" -type f -name "*.py" 2>/dev/null
done | sort | while read f; do
  echo "- \`$f\`  (modified $(stat -c %y "$f" | cut -d'.' -f1))" >> "$OUT"
done

echo >> "$OUT"
echo "## Shell Scripts" >> "$OUT"
for b in "${BASES[@]}"; do
  find "$b" -type f -name "*.sh" 2>/dev/null
done | sort | while read f; do
  echo "- \`$f\`  (modified $(stat -c %y "$f" | cut -d'.' -f1))" >> "$OUT"
done

echo >> "$OUT"
echo "## Virtual Environments" >> "$OUT"
find "$HOME" -type d -name "*venv*" 2>/dev/null | sort >> "$OUT"

echo >> "$OUT"
echo "## Large AI Artifacts (indexes, models)" >> "$OUT"
find "$HOME" -type f \( -name "*.index" -o -name "*.faiss" -o -name "*.pt" -o -name "*.bin" \) 2>/dev/null | sort >> "$OUT"

echo "Done."
