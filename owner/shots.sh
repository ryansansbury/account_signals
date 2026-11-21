#!/bin/bash
# About three minutes. Builds the page, opens it in headless Chrome from a server on 127.0.0.1 and from the file system,
# takes every view at 1600, 1440, 1280, 1024 and 768 pixels, the phone's screens and the tour's ten steps, and checks
# the layout, console errors, every request and the threads. When everything passes, the README's screens go to
# docs/images/ and the build runs again so the README shows them. Results land in owner/out/.
# Run from the build folder:   bash owner/shots.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python3 build.py --quiet
python3 owner/browser_check.py "$@"
python3 build.py --quiet
