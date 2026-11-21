#!/usr/bin/env python3
"""The owner's machine only, optional: a read by hand of ten briefs against their postings, about 20 minutes.

    python3 owner/spot_check.py          (from the build folder, after bash owner/run.sh briefs)

Since November 10 the gate is the second read by two judges (owner/judge_briefs.py), and no brief is read by
hand. This page stays for anyone who wants to check the judges with their own eyes.

It serves a local page on 127.0.0.1 at a free port and opens it. The page shows ten recorded briefs (the top four
accounts from the routed model, then six more drawn with a fixed seed across every model), each beside its numbered
sources and the full text of the postings it cites, redacted the same way as everything else. The reader marks each
one "holds up," "overreaches" or "wrong," with a note if wanted, and can mark 40 signals right or wrong on the
second tab for a signal precision figure. Every click is saved to evals/spot_check.json, so a read can stop and
come back. The
bar is nine of ten holding up. Nothing here leaves the machine.
"""
import html
import http.server
import json
import random
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs, replay  # noqa: E402
from engine import boards, redact  # noqa: E402

OUT = HERE.joinpath("evals", "spot_check.json")
RAW = HERE.joinpath("data", "raw")
SEED = 1109


def choose(recs, ranking, route):
    """The routed model's briefs for the top four accounts, then six more drawn by the seed across every model, one
    brief to an account, so the ten cover ten companies."""
    order = {a["account"]: i for i, a in enumerate(ranking)}
    top = sorted({r["account"] for r in recs}, key=lambda a: order.get(a, 9999))[:4]
    picked = [r for r in recs if r["account"] in top and r["model"] == route][:4]
    rest = [r for r in recs if r not in picked]
    random.Random(SEED).shuffle(rest)
    seen = {r["account"] for r in picked}
    for r in rest:
        if len(picked) == 10:
            break
        if r["account"] not in seen:
            picked.append(r)
            seen.add(r["account"])
    return picked


def posting_text(source_ids, manifest):
    """{posting_id: redacted plain text} for the postings the sources cite, read from the boards as fetched."""
    out, by_board = {}, {}
    for pid in source_ids:
        provider, token, _ = pid.split(":", 2)
        by_board.setdefault((provider, token), []).append(pid)
    for (provider, token), pids in by_board.items():
        path = RAW.joinpath("boards", f"{provider}_{token}.json")
        if not path.exists():
            continue
        for p in boards.parse(provider, token, path.read_bytes()):
            if p["id"] in pids:
                out[p["id"]] = redact.redact(p["text"], keep=[manifest.get(token, "")])[0]
    return out


def page(items, sample):
    esc = html.escape
    cards = []
    for i, r in enumerate(items):
        b = r["final"]["brief"] or {}
        srcs = "".join(f"<li><b>[{k}]</b> {esc(v.get('title') or v.get('text', ''))} <i>{esc(v.get('posted', ''))}</i>"
                       f"<br>{esc(v.get('excerpt', '')) if v.get('excerpt') != v.get('title') else ''}</li>"
                       for k, v in sorted(r["sources"].items(), key=lambda kv: int(kv[0])))
        full = "".join(f"<details><summary>{esc(pid)}</summary><p>{esc(t)}</p></details>"
                       for pid, t in r.get("full", {}).items())
        why = "".join(f"<li>{esc(s['text'])}</li>" for s in b.get("why_now", []))
        touch = esc((b.get("first_touch") or {}).get("body", "")).replace("\n", "<br>")
        chk = r["final"]["check"] or {}
        flags = [p for p in chk.get("problems", [])] + [p for s in chk.get("sentences", []) for p in s["problems"]]
        flagged = f"<p><b>Flagged by the checks:</b> {esc('; '.join(flags))}</p>" if flags else ""
        cards.append(f"<section data-i='{i}'><h2>{i + 1}. {esc(r['account'])} <small>{esc(r['label'])}"
                     f"{' · needs review' if r['final']['needs_review'] else ''}</small></h2>{flagged}"
                     f"<div class='two'><div><h3>Why now</h3><ul>{why}</ul><h3>Likely priority</h3>"
                     f"<p>{esc((b.get('priority') or {}).get('text', ''))}</p><h3>First touch</h3><p>{touch}</p></div>"
                     f"<div><h3>Sources</h3><ol class='src'>{srcs}</ol>{full}</div></div>"
                     f"<p class='v'><button data-v='holds up'>Holds up</button><button data-v='overreaches'>"
                     f"Overreaches</button><button data-v='wrong'>Wrong</button> <input placeholder='note'></p></section>")
    sigs = "".join(f"<tr data-sid='{esc(s['sid'])}'><td>{esc(s['label'])}</td><td>{esc(s['title'])}</td>"
                   f"<td>{esc(s['excerpt']) if s['excerpt'] != s['title'] else ''}</td>"
                   f"<td><button data-s='right'>Right</button><button data-s='wrong'>Wrong</button></td></tr>"
                   for s in sample)
    return ("<!doctype html><meta charset='utf-8'><title>Hand check</title><style>body{font:14px/1.5 system-ui;"
            "margin:24px;max-width:1300px}section{border:1px solid #ddd;border-radius:10px;padding:12px 16px;margin:14px 0}"
            ".two{display:grid;grid-template-columns:1fr 1fr;gap:20px}.src li{margin-bottom:6px}button{margin-right:6px}"
            "button.on{background:#a21caf;color:#fff}td{border-top:1px solid #eee;padding:6px;vertical-align:top}</style>"
            "<h1>Hand check: ten briefs against their postings</h1><p>Mark each brief, then the signals below if there's "
            "time. Every click saves.</p>" + "".join(cards) + "<h1>Signals (optional)</h1><table>" + sigs +
            "</table><p><button id='done'>Done</button></p><script>"
            "const post=(u,b)=>fetch(u,{method:'POST',body:JSON.stringify(b)});"
            "document.querySelectorAll('section').forEach(s=>s.querySelectorAll('button').forEach(b=>b.onclick=()=>{"
            "s.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');"
            "post('/verdict',{i:+s.dataset.i,verdict:b.dataset.v,note:s.querySelector('input').value})}));"
            "document.querySelectorAll('section input').forEach(n=>n.onchange=()=>{const s=n.closest('section'),"
            "b=s.querySelector('button.on');if(b)post('/verdict',{i:+s.dataset.i,verdict:b.dataset.v,note:n.value})});"
            "document.querySelectorAll('tr').forEach(r=>r.querySelectorAll('button').forEach(b=>b.onclick=()=>{"
            "r.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');"
            "post('/signal',{sid:r.dataset.sid,verdict:b.dataset.s})}));"
            "document.getElementById('done').onclick=()=>post('/done',{}).then(()=>document.body.innerHTML="
            "'<h1>Saved. You can close this tab.</h1>')</script>")


def main():
    recs = [r for r in replay.load_all(strict=False) if r["split"] == "briefs" and r["prompt_hash"] == inputs.prompt_hash()]
    if not recs:
        print("No briefs recorded yet. Run bash owner/run.sh briefs first.")
        return 1
    ranking = json.loads(HERE.joinpath("data", "out", "ranking.json").read_text(encoding="utf-8"))["accounts"]
    scores = HERE.joinpath("evals", "scores.json")
    route = json.loads(scores.read_text(encoding="utf-8"))["route"] if scores.exists() else "claude-sonnet"
    items = choose(recs, ranking, route)
    import csv
    with open(RAW.joinpath("manifest.csv"), newline="", encoding="utf-8") as f:
        manifest = {m["token"]: m["company"] for m in csv.DictReader(f) if m["status"] == "ok"}
    for r in items:
        r["full"] = posting_text({v["posting_id"] for v in r["sources"].values() if v.get("posting_id")}, manifest)
    sigs = [json.loads(ln) for ln in HERE.joinpath("data", "snapshot", "signals.jsonl").read_text(encoding="utf-8")
            .splitlines() if ln.strip()]
    scoring = [s for s in sigs if s["family"] not in ("pace", "stack")]
    sample = random.Random(SEED).sample(scoring, min(40, len(scoring)))
    state = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"briefs": {}, "signals": {}}
    body = page(items, sample).encode()
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.path == "/verdict":
                r = items[int(data["i"])]
                state["briefs"][f"{r['account']}|{r['model']}"] = {"account": r["account"], "model": r["model"],
                                                                   "verdict": data["verdict"], "note": data.get("note", "")}
            elif self.path == "/signal":
                state["signals"][data["sid"]] = data["verdict"]
            state["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            OUT.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
            self.send_response(204)
            self.end_headers()
            if self.path == "/done":
                done.set()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"The spot check is open at {url}. Press Done on the page when you finish.")
    webbrowser.open(url)
    done.wait()
    server.shutdown()
    held = sum(1 for v in state["briefs"].values() if v["verdict"] == "holds up")
    print(f"Saved to evals/spot_check.json: {held} of {len(state['briefs'])} briefs hold up (the bar is nine of ten), "
          f"and {len(state['signals'])} signals marked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
