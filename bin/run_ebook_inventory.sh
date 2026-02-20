#!/usr/bin/env bash
set -euo pipefail

echo
echo "=== Running ebook inventory ==="
echo "DATE: $(date -Is)"
echo "PWD:  $(pwd)"
echo "HOME: $HOME"
echo

# Activate venv if present
if [ -f "$HOME/ai-ebooks-venv/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$HOME/ai-ebooks-venv/bin/activate"
fi

echo "PYTHON: $(command -v python3)"
python3 -V
echo "SCRIPT: $HOME/FineTuningAI/bin/ebook_inventory"
ls -l "$HOME/FineTuningAI/bin/ebook_inventory"
echo

python3 "$HOME/FineTuningAI/bin/ebook_inventory"

echo
echo "=== Done ==="
echo
read -r -p "Press ENTER to close..."
