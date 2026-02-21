#!/usr/bin/env bash
set -euo pipefail

# =========================
# Batch downloader (Archive.org + direct links)
# - Retries
# - SHA256 manifest
# - Auto-unzip for IA "compress" ZIPs (Nag Hammadi)
# =========================

OUT_DIR="${1:-/ai_data/ebooks/_imports/manual_fetch_2026-02-20}"
MANIFEST="${OUT_DIR}/SHA256SUMS.txt"
LOG="${OUT_DIR}/download.log"

mkdir -p "${OUT_DIR}"
: > "${LOG}"
: > "${MANIFEST}"

# Prefer aria2c if available (faster + better retries), else curl.
have() { command -v "$1" >/dev/null 2>&1; }

download_one () {
  local url="$1"
  local out="$2"

  echo "==> ${out}" | tee -a "${LOG}"
  echo "    ${url}" | tee -a "${LOG}"

  if have aria2c; then
    aria2c \
      --allow-overwrite=true \
      --auto-file-renaming=false \
      --check-certificate=true \
      --continue=true \
      --max-connection-per-server=8 \
      --split=8 \
      --min-split-size=1M \
      --retry-wait=2 \
      --max-tries=10 \
      --timeout=60 \
      --out="${out}" \
      --dir="${OUT_DIR}" \
      "${url}" >> "${LOG}" 2>&1
  else
    curl -L --fail \
      --retry 10 --retry-delay 2 --retry-all-errors \
      -A "Mozilla/5.0 (X11; Linux x86_64) batch_fetch" \
      -o "${OUT_DIR}/${out}" \
      "${url}" >> "${LOG}" 2>&1
  fi
}

# -------------------------
# URL -> filename mappings
# -------------------------

# Empire of the Steppes (PDF)
download_one \
  "https://archive.org/download/the-empire-of-the-steppes-a-history-of-central-asia_202510/Grousset%202002%20The%20empire%20of%20the%20steppes%20a%20history%20of%20Central%20Asia.pdf" \
  "Empire_of_the_Steppes_Grousset_2002.pdf"

# A History of Eastern Europe (Great Courses) (DJVU TXT stream)
download_one \
  "https://archive.org/stream/AHistoryOfEasternEurope/AHistoryOfEasternEurope_djvu.txt" \
  "A_History_of_Eastern_Europe_Great_Courses_djvu.txt"

# Ian Jeffries 2007 (TXT + PDF)
download_one \
  "https://archive.org/stream/A_History_of_Eastern_Europe_Crisis_and_Change_by_Ian_Jeffries_2007/A_History_of_Eastern_Europe_Crisis_and_Change_by_Ian_Jeffries_2007_djvu.txt" \
  "A_History_of_Eastern_Europe_Jeffries_2007_djvu.txt"
download_one \
  "https://archive.org/download/A_History_of_Eastern_Europe_Crisis_and_Change_by_Ian_Jeffries_2007/A_History_of_Eastern_Europe_Crisis_and_Change_by_Ian_Jeffries_2007.pdf" \
  "A_History_of_Eastern_Europe_Jeffries_2007.pdf"

# Modern Europe 1789-1914 (TXT + PDF)
download_one \
  "https://archive.org/stream/in.ernet.dli.2015.102252/2015.102252.Modern-Europe-1789-1914_djvu.txt" \
  "Modern_Europe_1789-1914_djvu.txt"
download_one \
  "https://archive.org/download/in.ernet.dli.2015.102252/2015.102252.Modern-Europe-1789-1914.pdf" \
  "Modern_Europe_1789-1914.pdf"

# Historical Atlas of Modern Europe 1789-1914 (PDF)
download_one \
  "https://archive.org/download/historicalatlaso00robe/historicalatlaso00robe.pdf" \
  "Historical_Atlas_of_Modern_Europe_1789-1914.pdf"

# Behistan inscription of King Darius (TXT + PDF)
download_one \
  "https://archive.org/stream/behistaninscript00daririch/behistaninscript00daririch_djvu.txt" \
  "Behistan_Inscription_of_King_Darius_djvu.txt"
download_one \
  "https://archive.org/download/behistaninscript00daririch/behistaninscript00daririch.pdf" \
  "Behistan_Inscription_of_King_Darius.pdf"

# Early Christian Doctrines (J.N.D. Kelly) (TXT + PDF)
download_one \
  "https://archive.org/stream/pdfy-CY7YNVnvFwggDjnT/103911481-J-N-D-Kelly-Early-Christian-Doctrines_djvu.txt" \
  "Kelly_Early_Christian_Doctrones_djvu.txt"
download_one \
  "https://archive.org/download/pdfy-CY7YNVnvFwggDjnT/103911481-J-N-D-Kelly-Early-Christian-Doctrines.pdf" \
  "Kelly_Early_Christian_Doctrines.pdf"

# The Early Church (Chadwick) (TXT + PDF)
download_one \
  "https://archive.org/stream/20200507-early-church/20200507_%20early%20Church_djvu.txt" \
  "Chadwick_The_Early_Church_djvu.txt"
download_one \
  "https://archive.org/download/20200507-early-church/20200507_%20early%20Church_text.pdf" \
  "Chadwick_The_Early_Church.pdf"

# Quigley: Evolution of Civilizations (TXT + PDF)
download_one \
  "https://archive.org/stream/CarrollQuigleyTheEvolutionOfCivilizations/Carroll_Quigley_-_The_Evolution_of_Civilizations_djvu.txt" \
  "Quigley_Evolution_of_Civilizations_djvu.txt"
download_one \
  "https://archive.org/download/CarrollQuigleyTheEvolutionOfCivilizations/Carroll_Quigley_-_The_Evolution_of_Civilizations.pdf" \
  "Quigley_Evolution_of_Civilizations.pdf"

# Quigley: Tragedy and Hope (TXT + PDF from carrollquigley.net)
download_one \
  "https://archive.org/stream/pdfy-Sv4zfy4FhzwYgEZm/Carroll-Quigley-Tragedy-and-Hope-A-History-of-The-World-in-Our-Time_djvu.txt" \
  "Quigley_Tragedy_and_Hope_djvu.txt"
download_one \
  "https://www.carrollquigley.net/pdf/Tragedy_and_Hope.pdf" \
  "Quigley_Tragedy_and_Hope.pdf"

# Quigley: Anglo-American Establishment (TXT + PDF from carrollquigley.net)
download_one \
  "https://archive.org/stream/the-anglo-american-establishment-1981-carroll-quigley/The%20Anglo-American%20Establishment%201981-%20Carroll%20Quigley_djvu.txt" \
  "Quigley_Anglo-American_Establishment_djvu.txt"
download_one \
  "https://www.carrollquigley.net/pdf/the_anglo-american_establishment.pdf" \
  "Quigley_Anglo-American_Establishment.pdf"

# Bernays – Propaganda (TXT + PDF)
download_one \
  "https://archive.org/stream/propaganda00bern_0/propaganda00bern_0_djvu.txt" \
  "Bernays_Propaganda_djvu.txt"
download_one \
  "https://ia601200.us.archive.org/9/items/BernaysPropaganda/Bernays_Propaganda_text.pdf" \
  "Bernays_Propaganda.pdf"

# Nag Hammadi / Coptic Gnostic Library (5 vols) - two IA compress zips
download_one \
  "https://archive.org/compress/the-coptic-gnostic-library.-a-complete-edition-of-the-nag-hammadi-codices-5-vols./formats=DJVUTXT&file=/the-coptic-gnostic-library.-a-complete-edition-of-the-nag-hammadi-codices-5-vols..zip" \
  "Nag_Hammadi_5vols_DJVUTXT.zip"
download_one \
  "https://archive.org/compress/the-coptic-gnostic-library.-a-complete-edition-of-the-nag-hammadi-codices-5-vols./formats=TEXT%20PDF&file=/the-coptic-gnostic-library.-a-complete-edition-of-the-nag-hammadi-codices-5-vols..zip" \
  "Nag_Hammadi_5vols_TEXT_PDF.zip"

# Kebra Nagast (PDF + TXT)
download_one \
  "https://archive.org/download/kebranagast/Kebra%20Nagast.pdf" \
  "Kebra_Nagast.pdf"
download_one \
  "https://archive.org/stream/kebranagast/Kebra%20Nagast_djvu.txt" \
  "Kebra_Nagast_djvu.txt"

# -------------------------
# Post-processing: unzip the Nag Hammadi ZIPs if present
# -------------------------
if have unzip; then
  for z in "Nag_Hammadi_5vols_DJVUTXT.zip" "Nag_Hammadi_5vols_TEXT_PDF.zip"; do
    if [[ -f "${OUT_DIR}/${z}" ]]; then
      mkdir -p "${OUT_DIR}/Nag_Hammadi_unzipped/${z%.zip}"
      unzip -o "${OUT_DIR}/${z}" -d "${OUT_DIR}/Nag_Hammadi_unzipped/${z%.zip}" >> "${LOG}" 2>&1
    fi
  done
else
  echo "NOTE: 'unzip' not installed; skipping ZIP extraction." | tee -a "${LOG}"
fi

# -------------------------
# Manifest: SHA256
# -------------------------
if have sha256sum; then
  ( cd "${OUT_DIR}" && find . -type f ! -name "$(basename "${MANIFEST}")" -print0 | sort -z | xargs -0 sha256sum ) > "${MANIFEST}"
else
  echo "NOTE: 'sha256sum' not installed; skipping SHA256 manifest." | tee -a "${LOG}"
fi

echo
echo "Done."
echo "Output dir: ${OUT_DIR}"
echo "Log:        ${LOG}"
echo "SHA256:     ${MANIFEST}"
