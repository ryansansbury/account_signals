"""The owner's machine only. Look at the page in real Chrome: the screens for the review and the README, the layout checks,
console errors, every request the page makes, and the threads.

    bash owner/shots.sh            (from the build folder: the build, this check, then the build again for the README)

It opens the page in headless Chrome with a fresh profile and drives it over the DevTools pipe, from a small server on
127.0.0.1 that serves site/ under /account-signals/ with the live site's security policy (owner/preview_site.py), and
once straight from the file system. Everything goes to owner/out/, which is gitignored:

    screens/card-1600.png           the map as a fresh load opens it at 1600 by 1000, the homepage card's frame
    screens/gallery-<view>.png      the map, an account, its score, the list, How it works and the phone at the card's
                                    size, which docs/images/ takes for the README once every check passes
    screens/<width>-<view>.png      every view as a full page at 1440, 1280, 1024 and 768 pixels
    screens/phone-<screen>.png      the phone's screens at 390 by 844
    screens/phone360-<screen>.png   the map and an account on phones 360 and 375 wide (phone375-), and the map on a
                                    phone on its side at 844 by 390 (phone-side-map)
    screens/<view>-dark.png         dark mode: every view at 1440 (1440-<view>-dark), the phone's map and the gallery's
    screens/tour-NN.png             each of the tour's ten steps at 1440
    browser_check.json              the summary this prints, with the hash of every page file it looked at, which
                                    tools/go_live.py compares before anything goes live

Standard library only.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT.joinpath("site")
OUT = HERE.joinpath("out")
SHOTS = OUT.joinpath("screens")
IMAGES = ROOT.joinpath("docs", "images")
APPS = Path("/").joinpath("Applications")
SHIPS = ("index.html", "app.css", "app.js", "scoring.js", "route.js", "claims.js", "data.js", "code.js",
         "favicon.svg")
WIDTHS = ((1440, 900), (1280, 800), (1024, 768), (768, 1024))
VIEWS = ("map", "account", "score", "list", "how")
GALLERY = ("map", "account", "score", "list", "how", "phone", "map-dark")
SETTLE = 1.4
TRAMPOLINE = 'exec "$@" 3<&0 4>&1 0</dev/null 1>&2'
THREADS_JS = ("(function () { var p = document.querySelectorAll('svg.threads path'); var bad = 0; "
              "p.forEach(function (x) { if (/NaN|undefined/.test(x.getAttribute('d'))) { bad += 1; } }); "
              "return {threads: p.length, chips: document.querySelectorAll('.brief .cite[data-c]').length, bad: bad}; })()")
FIT_JS = ("(function () { var h = window.innerHeight + 1; return document.documentElement.scrollHeight <= h && "
          "document.body.scrollHeight <= h && document.documentElement.scrollWidth <= window.innerWidth + 1; })()")
SHOWN_JS = ("(function () { var v = Array.prototype.slice.call(document.querySelectorAll('.view.on')); "
            "return v.length > 0 && v.every(function (x) { var r = x.getBoundingClientRect(); "
            "return r.height > 50 && r.top < window.innerHeight - 50 && r.bottom > 60; }); })()")
CODE_JS = ("(function () { var s = document.getElementById('how-code'); "
           "if (s) { s.scrollIntoView({block: 'start'}); } return !!s; })()")
# The map twelve times closer on the top account's city, the Northeast's chip zooming to its accounts, the biggest
# ring picked with its list beside the map, and the top row pointed at with every city it hires in.
ZOOM_JS = ("(function () { var a = ASP.ranked().find(function (x) { return x.hub; }); "
           "if (a) { ASP.zoomTo(12, a.hub[2], a.hub[3], true); } return ASP.zoom().k; })()")
REGION_JS = ("(function () { var c = document.querySelector(\"[data-region='Northeast']\"); "
             "if (c) { c.click(); } return ASP.zoom().k; })()")
RING_JS = ("(function () { var m = ASP.marks().filter(function (x) { return x.n > 1; })"
           ".sort(function (a, b) { return b.n - a.n; })[0]; if (m) { ASP.pick(m.slugs[0]); } return !!m; })()")
FOOT_JS = ("(function () { var r = document.querySelector('.toplist .acct'); "
           "if (r) { r.dispatchEvent(new MouseEvent('mouseover', {bubbles: true})); } return !!r; })()")
TEXT_JS = ("(function () { var t = document.getElementById('main').innerText; "
           "return (t.match(/undefined|NaN|\\{[a-z_]+\\}|\\[object Object\\]/g) || [])"
           ".filter(function (m) { return m !== '{first_name}' && m !== '{sender_name}'; }); })()")

LAYOUT_JS = """(function () {
  var W = window.innerWidth, out = {wider_than_window: document.documentElement.scrollWidth > W + 1, overlaps: [],
    short_last_lines: [], spills: []};
  var root = document.body, boxes = new Map(), covers = [];
  function name(el) {
    return (el.id ? '#' + el.id : el.tagName.toLowerCase() + Array.prototype.map.call(el.classList, function (c) {
      return '.' + c; }).join('')).slice(0, 50);
  }
  function clip(el) {
    if (boxes.has(el)) { return boxes.get(el); }
    var b = {l: -1e9, t: -1e9, r: 1e9, b: 1e9};
    for (var a = el; a && a !== document.documentElement; a = a.parentElement) {
      var cs = getComputedStyle(a);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        var q = a.getBoundingClientRect();
        b = {l: Math.max(b.l, q.left), t: Math.max(b.t, q.top), r: Math.min(b.r, q.right), b: Math.min(b.b, q.bottom)};
      }
    }
    boxes.set(el, b);
    return b;
  }
  root.querySelectorAll('*').forEach(function (el) {
    if (el.closest('svg') || !el.checkVisibility()) { return; }
    var cs = getComputedStyle(el);
    if (cs.position === 'sticky' || cs.position === 'fixed' || el.matches('.pop')) { covers.push(el); }
    if (out.spills.length >= 25 || el.closest('pre, .code-tree, .sr') || cs.display === 'inline' || !el.clientWidth) { return; }
    if (/x|both/.test(cs.scrollSnapType || '')) { return; }
    if (el.scrollWidth > el.clientWidth + 1) {
      var scrolls = cs.overflowX === 'auto' || cs.overflowX === 'scroll';
      out.spills.push(name(el) + ' by ' + (el.scrollWidth - el.clientWidth) + 'px' + (scrolls ? ' (scrolls)' : ''));
    }
  });
  function covered(el, f) {
    return covers.some(function (c) {
      if (c === el || c.contains(el)) { return false; }
      var q = c.getBoundingClientRect();
      return f.l < q.right && f.r > q.left && f.t < q.bottom && f.b > q.top;
    });
  }
  root.querySelectorAll('p, li, dd, h2, h3, h4').forEach(function (el) {
    if (el.closest('pre, .code-tree, .transcript-pane, .findings, .chips') || !el.checkVisibility() ||
        el.querySelector('.chip, button, input, select, label')) { return; }
    var r = document.createRange(); r.selectNodeContents(el);
    var rects = Array.prototype.filter.call(r.getClientRects(), function (x) { return x.width > 1; });
    if (rects.length < 2) { return; }
    var tops = {}, box = el.getBoundingClientRect();
    rects.forEach(function (x) { var k = Math.round(x.top); tops[k] = Math.max(tops[k] || 0, x.right); });
    var keys = Object.keys(tops).map(Number).sort(function (a, b) { return a - b; });
    if (keys.length < 2) { return; }
    var lastRight = tops[keys[keys.length - 1]], fill = (lastRight - box.left) / Math.max(1, box.width);
    if (fill < 0.8) { out.short_last_lines.push({text: el.textContent.trim().slice(-60), fill: Math.round(fill * 100)}); }
  });
  var frags = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node, range = document.createRange();
  while ((node = walker.nextNode())) {
    var el = node.parentElement;
    if (!/\\S/.test(node.data) || !el || el.closest('script, style, pre, .code-tree') || !el.checkVisibility()) { continue; }
    var box = clip(el);
    range.selectNodeContents(node);
    Array.prototype.forEach.call(range.getClientRects(), function (x) {
      if (x.width < 1 || x.height < 1) { return; }
      var h = x.bottom - x.top, mid = (x.top + x.bottom) / 2;
      var f = {el: el, l: Math.max(x.left, box.l), r: Math.min(x.right, box.r), t: x.top + h * 0.2, b: x.bottom - h * 0.2,
        text: node.data.trim().slice(0, 40)};
      if (mid < box.t || mid > box.b || f.r - f.l < 1 || covered(el, f)) { return; }
      frags.push(f);
    });
  }
  frags.sort(function (a, b) { return a.t - b.t; });
  for (var i = 0; i < frags.length && out.overlaps.length < 20; i++) {
    for (var j = i + 1; j < frags.length && frags[j].t < frags[i].b; j++) {
      var f = frags[i], g = frags[j];
      if (f.el === g.el || f.el.contains(g.el) || g.el.contains(f.el)) { continue; }
      if (Math.min(f.r, g.r) - Math.max(f.l, g.l) > 2) { out.overlaps.push(f.text + ' / ' + g.text); }
    }
  }
  return out;
})()"""



def find_chrome(given=None):
    """The Chrome or Chromium program: the one given, an app in the Applications folder, or one on the PATH."""
    if given:
        return str(given)
    for app in sorted(APPS.glob("*Chrom*.app")):
        exe = app.joinpath("Contents", "MacOS", app.stem)
        if exe.exists():
            return str(exe)
    for n in ("google-chrome", "chromium"):
        if shutil.which(n):
            return shutil.which(n)
    raise SystemExit("Chrome wasn't found. Run again with --chrome and the path to the Chrome program.")



class CDP:
    """The DevTools protocol over Chrome's pipe: JSON messages, each ended by a zero byte."""

    def __init__(self, proc, on_event=None):
        self.proc, self.on_event = proc, on_event
        self.next_id, self.responses, self.events = 0, {}, []
        self.cond, self.wlock = threading.Condition(), threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read1(1 << 16)
            if not chunk:
                break
            buf += chunk
            while b"\0" in buf:
                raw, buf = buf.split(b"\0", 1)
                msg = json.loads(raw)
                with self.cond:
                    if "id" in msg:
                        self.responses[msg["id"]] = msg
                    else:
                        self.events.append(msg)
                    self.cond.notify_all()
                if "id" not in msg and self.on_event:
                    self.on_event(msg)

    def send(self, method, params=None, session=None, timeout=60):
        with self.cond:
            self.next_id += 1
            mid = self.next_id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        with self.wlock:
            self.proc.stdin.write(json.dumps(msg).encode() + b"\0")
            self.proc.stdin.flush()
        deadline = time.time() + timeout
        with self.cond:
            while mid not in self.responses:
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)
            reply = self.responses.pop(mid)
        if "error" in reply:
            raise RuntimeError(f"{method}: {reply['error'].get('message')}")
        return reply.get("result", {})

    def mark(self):
        with self.cond:
            return len(self.events)

    def wait_event(self, method, session, since, timeout=60):
        deadline = time.time() + timeout
        with self.cond:
            while True:
                for e in self.events[since:]:
                    if e.get("method") == method and e.get("sessionId") == session:
                        return e
                left = deadline - time.time()
                if left <= 0:
                    raise TimeoutError(method)
                self.cond.wait(left)



class Browser:
    def __init__(self, chrome):
        self.requests, self.console, self.loads = [], [], 0
        profile = OUT.joinpath("chrome-profile")
        shutil.rmtree(profile, ignore_errors=True)
        flags = ["--headless=new", "--remote-debugging-pipe", f"--user-data-dir={profile}", "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars", "--mute-audio",
                 "--disable-background-networking", "--disable-sync", "--disable-component-update",
                 "--autoplay-policy=no-user-gesture-required", "--allow-file-access-from-files"]
        self.log = OUT.joinpath("chrome.log").open("wb")
        self.proc = subprocess.Popen(["bash", "-c", TRAMPOLINE, "chrome", chrome, *flags], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log)
        self.cdp = CDP(self.proc, self.event)
        target = self.cdp.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.s = self.cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        for m in ("Page.enable", "Runtime.enable", "Network.enable", "Log.enable"):
            self.cdp.send(m, session=self.s)

    def event(self, e):
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            self.requests.append(p["request"]["url"])
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            self.console.append({"kind": "exception", "text": (d.get("exception") or {}).get("description") or d.get("text")})
        elif m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "assert"):
            self.console.append({"kind": "console.error", "text": " ".join(str(a.get("value", a.get("description")))
                                                                           for a in p.get("args", []))})
        elif m == "Log.entryAdded" and p["entry"].get("level") == "error":
            self.console.append({"kind": "log", "text": p["entry"].get("text"), "url": p["entry"].get("url")})

    def view(self, width, height, mobile=False):
        self.cdp.send("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1,
                                                             "mobile": mobile}, self.s)

    def load(self, url):
        """A fresh page at the address. Each load carries its own query, so it is never a move within the same page,
        which fires no load event, and a reload can't race the page's own address change."""
        self.loads += 1
        base, mark, frag = url.partition("#")
        fresh = f"{base}{'&' if '?' in base else '?'}load={self.loads}{mark}{frag}"
        since = self.cdp.mark()
        self.cdp.send("Page.navigate", {"url": fresh}, self.s)
        self.cdp.wait_event("Page.loadEventFired", self.s, since)
        self.pause(0.5)

    def js(self, expr, wait=False):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": wait}, self.s)
        if "exceptionDetails" in r:
            raise RuntimeError(f"{expr[:60]}: {r['exceptionDetails'].get('text')}")
        return r.get("result", {}).get("value")

    def pause(self, seconds):
        time.sleep(seconds)
        self.js("document.readyState")

    def shot(self, name, width, full=True):
        params = {"format": "png"}
        if full:
            size = self.cdp.send("Page.getLayoutMetrics", session=self.s)["cssContentSize"]
            params.update(captureBeyondViewport=True, clip={"x": 0, "y": 0, "width": width,
                                                            "height": min(size["height"], 9000), "scale": 1})
        data = self.cdp.send("Page.captureScreenshot", params, self.s, timeout=120)["data"]
        SHOTS.joinpath(f"{name}.png").write_bytes(base64.b64decode(data))

    def close(self):
        try:
            self.cdp.send("Browser.close", timeout=10)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()




def preview_server():
    spec = importlib.util.spec_from_file_location("owner_preview_site", str(HERE.joinpath("preview_site.py")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.serve(SITE), mod.FOLDER


def hashes():
    return {n: hashlib.sha256(SITE.joinpath(n).read_bytes()).hexdigest() for n in SHIPS}


def address(view, slug):
    return {"map": "#/map", "account": f"#/a/{slug}", "score": f"#/a/{slug}/score", "list": "#/list", "how": "#/how"}[view]


class Check:
    """Every finding, by the shot it came from."""

    def __init__(self, b):
        self.b, self.layout, self.threads, self.text, self.shots, self.scrolls, self.hidden = b, {}, {}, {}, [], [], []

    def look(self, name, width, full=True, threads=False):
        self.b.pause(SETTLE)
        self.layout[name] = self.b.js(LAYOUT_JS)
        if not self.b.js(FIT_JS):
            self.scrolls.append(name)
        if not self.b.js(SHOWN_JS):
            self.hidden.append(name)
        bad = self.b.js(TEXT_JS) or []
        if bad:
            self.text[name] = bad[:5]
        if threads:
            self.threads[name] = self.b.js(THREADS_JS)
        self.b.shot(name, width, full)
        self.shots.append(name)


def run_checks(b, base, slug):
    c = Check(b)
    b.view(1600, 1000)
    b.load(base + "#/map")
    b.pause(1.2)
    c.look("card-1600", 1600, full=False)
    for view in VIEWS:
        b.load(base + address(view, slug))
        if view == "account":
            b.js("(function () { var s = document.querySelector('.brief [data-i=w0]'); if (s) { s.dispatchEvent("
                 "new MouseEvent('mouseover', {bubbles: true})); } })()")
        c.look(f"gallery-{view}", 1600, full=False, threads=view == "account")
    b.load(base + "#/how")
    b.pause(1.0)
    b.js(CODE_JS)
    c.look("how-code-1600", 1600, full=False)
    for name, js in (("zoom-1600", ZOOM_JS), ("region-1600", REGION_JS), ("ring-1600", RING_JS), ("footprint-1600", FOOT_JS)):
        b.load(base + "#/map")
        b.pause(1.0)
        b.js(js)
        b.pause(1.6)
        c.look(name, 1600, full=False)
    for width, height in WIDTHS:
        b.view(width, height)
        for view in VIEWS:
            b.load(base + address(view, slug))
            c.look(f"{width}-{view}", width, full=False, threads=view == "account")
    b.view(390, 844, mobile=True)
    b.load(base + "#/map")
    c.look("phone-map", 390, full=False)
    shutil.copyfile(SHOTS.joinpath("phone-map.png"), SHOTS.joinpath("gallery-phone.png"))
    for tab in ("account", "score", "how"):
        b.js(f"document.querySelector('[data-tab={tab}]').click()")
        c.look(f"phone-{tab}", 390, full=False)
    b.pause(1.0)
    b.js(CODE_JS)
    c.look("phone-how-code", 390, full=False)
    # Phones 360 and 375 wide and a phone on its side (11/20), the widths the other demos' phone rounds take.
    for width, height in ((360, 780), (375, 812)):
        b.view(width, height, mobile=True)
        b.load(base + "#/map")
        c.look(f"phone{width}-map", width, full=False)
        b.js("document.querySelector('[data-tab=account]').click()")
        c.look(f"phone{width}-account", width, full=False)
    b.view(844, 390, mobile=True)
    b.load(base + "#/map")
    c.look("phone-side-map", 844, full=False)
    # Dark mode (11/20): each view loads light and the switch turns it on, as a visitor would.
    b.view(1440, 900)
    for view in VIEWS:
        b.load(base + address(view, slug))
        b.js("ASP.dark(true)")
        c.look(f"1440-{view}-dark", 1440, full=False, threads=view == "account")
    b.view(390, 844, mobile=True)
    b.load(base + "#/map")
    b.js("ASP.dark(true)")
    c.look("phone-map-dark", 390, full=False)
    b.view(1600, 1000)
    b.load(base + "#/map")
    b.js("ASP.dark(true)")
    c.look("gallery-map-dark", 1600, full=False)
    b.view(1440, 900)
    for i in range(1, 11):
        b.load(base + f"#/tour/{i}")
        c.look(f"tour-{i:02d}", 1440, full=False)
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chrome", help="the path to the Chrome program")
    a = ap.parse_args(argv)
    head = SITE.joinpath("data.js").read_text(encoding="utf-8")[:300] if SITE.joinpath("data.js").exists() else ""
    if not head:
        sys.exit("Stopped: site/ isn't built. Run python3 build.py first.")
    shutil.rmtree(SHOTS, ignore_errors=True)
    SHOTS.mkdir(parents=True)
    before = hashes()
    httpd, folder = preview_server()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/{folder}/"
    b = Browser(find_chrome(a.chrome))
    t0 = time.time()
    try:
        b.view(1600, 1000)
        b.load(base + "#/map")
        slug = b.js("(function () { var a = ASP.ranked().find(function (x) { return x.briefs.length; }) || ASP.ranked()[0]; "
                    "return a.slug; })()")
        c = run_checks(b, base, slug)
        file_url = SITE.joinpath("index.html").resolve().as_uri()
        b.load(file_url + "#/map")
        b.pause(SETTLE)
        from_file = b.js("document.querySelectorAll('.map .ring').length")
    finally:
        b.close()
        httpd.shutdown()
    local = ("http://127.0.0.1:", "file://", "data:", "blob:", "about:", "chrome-extension:", "devtools:")
    off = sorted({u for u in b.requests if not u.startswith(local)})
    layout = c.layout
    report = {
        "files": before, "changed_during_check": hashes() != before, "seconds": round(time.time() - t0),
        "console_errors": len(b.console), "console": b.console[:20],
        "requests": len(b.requests), "requests_off_the_machine": len(off), "off_the_machine": off[:20],
        "wider_than_window": sorted(n for n, v in layout.items() if v and v.get("wider_than_window")),
        "overlaps": {n: v["overlaps"] for n, v in layout.items() if v and v.get("overlaps")},
        "spills": {n: v["spills"] for n, v in layout.items() if v and v.get("spills")},
        "short_last_lines": {n: v["short_last_lines"][:6] for n, v in layout.items() if v and v.get("short_last_lines")},
        "unfilled_text": c.text, "threads": c.threads,
        "broken_threads": sum(1 for v in c.threads.values() if v and (v["bad"] or v["threads"] != v["chips"])),
        "opens_from_file": bool(from_file), "page_scrolls": c.scrolls, "views_out_of_sight": c.hidden, "shots": c.shots,
    }
    passes = not (report["console_errors"] or report["requests_off_the_machine"] or report["wider_than_window"] or
                  report["broken_threads"] or report["unfilled_text"] or report["changed_during_check"] or
                  report["page_scrolls"] or report["views_out_of_sight"] or not report["opens_from_file"])
    report["passes"] = passes
    if not passes:
        report["files"] = {}
    OUT.joinpath("browser_check.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if passes:
        IMAGES.mkdir(parents=True, exist_ok=True)
        for name in GALLERY:
            shutil.copyfile(SHOTS.joinpath(f"gallery-{name}.png"), IMAGES.joinpath(f"{name}.png"))
    print(f"{len(c.shots)} screens in {report['seconds']} s. Console errors {report['console_errors']}, requests off the "
          f"machine {report['requests_off_the_machine']}, wider than the window {len(report['wider_than_window'])}, "
          f"overlapping text in {len(report['overlaps'])} screens, spills in {len(report['spills'])}, broken threads "
          f"{report['broken_threads']}, unfilled text in {len(c.text)}, the page itself scrolls in {len(c.scrolls)}, "
          f"a view out of sight in {len(c.hidden)}, "
          f"opens from file {report['opens_from_file']}.")
    print("Passed, and docs/images/ holds the README's screens." if passes else
          "Something needs a look: owner/out/browser_check.json says what.")
    return 0 if passes else 1


if __name__ == "__main__":
    sys.exit(main())
