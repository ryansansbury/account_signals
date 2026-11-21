#!/bin/bash
# About 15 minutes the first time. Reads the public job boards for the seed companies once so the build can find real
# signals. A rerun takes a minute or two, since it asks again only about boards that came back empty or hit a network
# error. To see every request first without sending anything:   python3 owner/fetch.py --dry-run
# Run from the build folder:   bash owner/fetch.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python3 owner/fetch.py "$@"
echo "Done. The boards are in data/raw/."
