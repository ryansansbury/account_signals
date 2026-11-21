# The owner's scripts

These run on the owner's machine and nowhere else. They read the boards, call the models, and take the screens. The build never does any of that and the page never does either. Every command runs from the build folder.

## In order

1. `bash owner/bootstrap.sh` downloads the Census Bureau's Gazetteer of places and checks its columns.
2. The private exclusion list goes in `private/exclusions.txt` and a script that stays on the owner's machine writes it. Every later step refuses a company on it and the list never ships.
3. `python3 owner/fetch.py --dry-run | tail -4` shows what the read would ask for, and `bash owner/fetch.sh` reads each board once. It talks only to the providers' job board hosts and honors each host's robots.txt.
4. `python3 owner/accounts.py` prints every company the read found for a skim before any model sees the list.
5. `python3 owner/claude_check.py` asks each model in config/models.json for one word through the Claude Code command line. Every model call runs there on the owner's Claude plan with no key.
6. `bash owner/run.sh dev` writes the briefs for the practice accounts with all three models. Then it runs the second read on them. The prompt is tuned on these and then frozen.
7. `bash owner/run.sh briefs` writes the briefs for the top accounts after the freeze. It scores the models and ends with the second read.
8. `bash owner/shots.sh` builds the page, checks it in headless Chrome, takes every screen, and copies the README's screens to `docs/images/`.
9. `python3 owner/preview_site.py` opens the page the way the website serves it with its own security policy for a last click through.

A stopped run starts again where it stopped. A record that matches today's prompt and input is skipped. `bash owner/run.sh judge` runs the second read alone.

## What each one keeps

- The read keeps the boards as read in `data/raw/` and they never ship. The build turns them into the redacted snapshot in `data/snapshot/`.
- Each brief goes to `data/ai_runs/brief/<account>/<model>.json` with its prompt hash, its input hash, every attempt, the checks, the tokens, the cost, and the seconds.
- Each judgment goes to `data/ai_runs/judge/` with the verdicts and their reasons. It never keeps a posting's text.
- Every model call adds a line to `data/ai_runs/audit.jsonl`.
- The screens and the browser check's report go to `owner/out/`. Only the README's screens leave it.

## Keys

The relaunch's runs need no key. Every call goes through the Claude Code command line. The API backends stay for anyone who runs it with keys. Those keys live in the macOS Keychain and never in a file. `owner/keychain.py` reads them without printing one. No test imports it.
