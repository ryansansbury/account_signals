#!/bin/bash
# The owner's machine only, about a minute. It checks for python3 and Node, downloads the Census Bureau's Gazetteer
# national places file (public domain) for the city coordinates, unzips it into data/raw/gazetteer/ (gitignored) and
# checks its columns. It tries the 2025 file first, then 2024. The build needs nothing else: Python's standard library
# and Node with no packages.
# Run from the build folder:   bash owner/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null 2>&1 || { echo "python3 is missing."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node is missing. Install it with: brew install node"; exit 1; }

mkdir -p data/raw/gazetteer
base="https://www2.census.gov/geo/docs/maps-data/data/gazetteer"
agent="AccountSignals/1.0 (+https://github.com/ryansansbury/account_signals; one download)"
got=""
for year in 2025 2024; do
  zip="data/raw/gazetteer/${year}_Gaz_place_national.zip"
  if [ ! -s "$zip" ]; then
    curl -fsSL --max-time 180 -A "$agent" -o "$zip" "$base/${year}_Gazetteer/${year}_Gaz_place_national.zip" || true
  fi
  if [ -s "$zip" ] && unzip -tq "$zip" >/dev/null 2>&1; then
    got="$year"
    break
  fi
  rm -f "$zip"
done
if [ -z "$got" ]; then
  echo "Couldn't download the Gazetteer places file for 2025 or 2024. Its address may have changed."
  exit 1
fi
unzip -o -q "data/raw/gazetteer/${got}_Gaz_place_national.zip" -d data/raw/gazetteer
python3 -m engine.gazetteer --check
echo "Next: python3 owner/exclusions.py"
