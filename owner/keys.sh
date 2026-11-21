#!/bin/bash
# The owner's machine only. Finds or saves the API keys the brief runs use, in this project's own Keychain items.
# Keys never go in a file, and nothing here prints one.
#
#   bash owner/keys.sh check                    which Keychain items hold a key now (names only)
#   bash owner/keys.sh anthropic                save the key on the clipboard as account-signals-anthropic
#   bash owner/keys.sh openai                   save the key on the clipboard as account-signals-openai
#   bash owner/keys.sh anthropic --from ITEM    copy a key already saved under another Keychain item
#
# A key typed into a Keychain prompt can be cut short, which is why a new key comes from the clipboard. The brief runs
# read the account-signals-* items (config/models.json).
set -euo pipefail
ITEMS="account-signals-anthropic account-signals-openai"
case "${1:-}" in
  check)
    for item in $ITEMS; do
      if security find-generic-password -s "$item" >/dev/null 2>&1; then
        echo "found    $item"
      else
        echo "missing  $item"
      fi
    done
    ;;
  anthropic|openai)
    if [ "${2:-}" = "--from" ] && [ -n "${3:-}" ]; then
      key="$(security find-generic-password -s "$3" -w)"
    else
      key="$(pbpaste)"
    fi
    if [ ${#key} -lt 20 ]; then
      echo "That doesn't look like a key. Copy it to the clipboard, or check the item name, and run this again."
      exit 1
    fi
    security add-generic-password -U -a "$USER" -s "account-signals-$1" -w "$key"
    echo "Saved the $1 key as account-signals-$1 (${#key} characters)."
    ;;
  *)
    echo "Usage: bash owner/keys.sh check | anthropic | openai [--from ITEM]"
    exit 1
    ;;
esac
