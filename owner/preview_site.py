#!/usr/bin/env python3
"""Open the page the way ryansansbury.com will serve it, on this machine, to click through before the launch.

    python3 owner/preview_site.py          the built page at http://127.0.0.1:<a free port>/account-signals/
    python3 owner/preview_site.py --no-open    the same without opening the browser

It serves site/ under /account-signals/ with the security policy and cache rule the live site sets for the page (the
same ones tools/go_live.py stages and checks), so a script or style the policy would block fails here too. It takes a
free port, opens the address in the default browser, and runs until Ctrl-C. It refuses a preview or a dry build with the
stand-in's briefs, since neither ever goes live. Nothing leaves the machine.
"""
import argparse
import functools
import http.server
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SITE = HERE.joinpath("site")
FOLDER = "account-signals"
POLICY = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
          "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
CACHE = "public, max-age=0, must-revalidate"


class Handler(http.server.SimpleHTTPRequestHandler):
    """site/ under /account-signals/, the bare folder address redirected the way the live site does, and the page's
    own headers on every file."""

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        prefix = f"/{FOLDER}/"
        # Anything outside the folder maps to a name that's never in site/, so the server answers 404. (A name holding a
        # null byte made Python's open() raise ValueError, which the server doesn't catch, so it dropped the connection.)
        rest = clean[len(prefix):] if clean.startswith(prefix) else ".not-served"
        return super().translate_path("/" + rest)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", f"/{FOLDER}"):
            self.send_response(301)
            self.send_header("Location", f"/{FOLDER}/")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Content-Security-Policy", POLICY)
        self.send_header("Cache-Control", CACHE)
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def built_kind(site=SITE):
    data = site.joinpath("data.js")
    if not data.exists():
        return "missing"
    head = data.read_text(encoding="utf-8")[:200]
    if '"preview":true' in head:
        return "preview"
    if '"stand_in":true' in head:
        return "stand-in"
    return "page"


def serve(site=SITE, port=0):
    handler = functools.partial(Handler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-open", action="store_true", help="print the address without opening the browser")
    a = ap.parse_args(argv)
    kind = built_kind()
    if kind == "missing":
        sys.exit("Stopped: site/ isn't built. Run python3 build.py first.")
    if kind != "page":
        sys.exit(f"Stopped: site/ holds a {kind} build, which never goes live. Run python3 build.py first.")
    httpd = serve()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/{FOLDER}/"
    print(f"The page as the site will serve it: {url}\nPress Ctrl-C to stop.", flush=True)
    if not a.no_open:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        httpd.shutdown()
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
