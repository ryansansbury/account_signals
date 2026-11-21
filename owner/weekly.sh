#!/bin/bash
# The owner's machine only. The weekly read of the boards on the page: the exclusion list is written again first, then
# each board is read once and the read is kept by its day in data/raw/weekly/ (gitignored). It never builds, deploys or
# publishes anything.
#
#   bash owner/weekly.sh               one read now (a few minutes)
#   bash owner/weekly.sh install       run it on this Mac every Sunday at 6 PM, and at the next wake when the Mac slept
#   bash owner/weekly.sh status        whether it's scheduled, and the last reads
#   bash owner/weekly.sh uninstall     stop the weekly runs
#
# The schedule is a launchd agent in ~/Library/LaunchAgents that runs this script with "run". Its output goes to
# data/raw/weekly/launchd.log.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
LABEL="com.accountsignals.weekly"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HERE="$(pwd)"

case "${1:-run}" in
  run)
    echo "Weekly read, $(date '+%a %b %d %H:%M %Z')"
    python3 owner/exclusions.py
    python3 owner/weekly.py
    ;;
  install)
    mkdir -p "$HOME/Library/LaunchAgents" data/raw/weekly
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$HERE/owner/weekly.sh</string><string>run</string></array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$HERE/data/raw/weekly/launchd.log</string>
  <key>StandardErrorPath</key><string>$HERE/data/raw/weekly/launchd.log</string>
</dict>
</plist>
EOF
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "Scheduled: every Sunday at 6 PM on this Mac, and at the next wake when it slept through one."
    echo "It only reads the boards. Nothing is built, deployed or published."
    ;;
  status)
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "Scheduled: every Sunday at 6 PM ($PLIST)."
    else
      echo "Not scheduled. Run bash owner/weekly.sh install to schedule it."
    fi
    if [ -f data/raw/weekly/reads.csv ]; then
      echo "The last reads:"
      tail -n 5 data/raw/weekly/reads.csv
    else
      echo "No weekly read yet."
    fi
    ;;
  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "The weekly runs are off. The reads already kept stay in data/raw/weekly/."
    ;;
  *)
    echo "Usage: bash owner/weekly.sh [run | install | status | uninstall]"
    exit 1
    ;;
esac
