#!/bin/bash
# The model runs, from the build folder. Each needs the snapshot the build makes from the fetch.
#   bash owner/run.sh dev       about 8 minutes: three models on the six dev accounts, then the judges on them
#   bash owner/run.sh briefs    about 35 minutes: three models on the top 25 after the freeze, then the judges on them
#   bash owner/run.sh judge     the second read alone, to finish one that stopped
# A stopped run starts again where it stopped, since a record that matches today's prompt and input is skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  dev|briefs)
    python3 -m engine.rank
    python3 owner/record_briefs.py --split "$1"
    python3 evals/score.py
    python3 owner/judge_briefs.py
    ;;
  judge)
    python3 owner/judge_briefs.py
    ;;
  *) echo "Usage: bash owner/run.sh dev|briefs|judge"; exit 1 ;;
esac
echo "Done. The $1 run is recorded."
