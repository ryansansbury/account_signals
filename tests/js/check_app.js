/* The Node click-through. It runs the built page's own scripts against a small DOM (dom.js) and walks every view:
   the map with its chips and bubbles, an account with its threads, model switch, second read and first touch (edited
   into a flagged claim, approved and reset), the score with the weights moved and reset, the list sorted and
   filtered, How it works with its code open on the excerpts and the file pane, the tour's ten addresses, deep links, and the phone's
   three screens. It also checks that the page ranks the accounts exactly as the build did. Exits 1 on any failed
   check.

       node tests/js/check_app.js [site folder]

   It can't see layout, color, motion or real timing. owner/browser_check.py covers those in real Chrome. */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const {Document, Element} = require("./dom.js");

const ROOT = path.join(__dirname, "..", "..");
const SITE = path.resolve(process.argv[2] || path.join(ROOT, "site"));
const checks = [], errors = [];
function check(name, ok, detail) { checks.push({name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 300)}); }
function attempt(name, fn) { try { fn(); } catch (e) { errors.push(name + ": " + (e && e.stack || e)); } }

const html = fs.readFileSync(path.join(SITE, "index.html"), "utf8");
check("no script, style or font comes from another site", !/(?:src|href)=['"](?:https?:)?\/\/(?!github\.com\/ryansansbury|www\.ryansansbury\.com\/account-signals\/['"])/.test(html));
check("the page carries its share preview", /<link rel='canonical' href='https:\/\/www\.ryansansbury\.com\/account-signals\/'>/.test(html) &&
  /og:image' content='https:\/\/www\.ryansansbury\.com\/images\/share\/account-signals\.png\?v=1'/.test(html));
check("no inline script or style", !/<script>(?!<\/script>)|<script[^>]*>[^<]+<\/script>| style=/.test(html));

/* The small DOM gives every element a 100 by 20 box. The map's rings are sized in screen pixels, so its box gets the
   frame's own size here: one pixel to one unit of the frame at zoom 1. */
const boxOf = Element.prototype.getBoundingClientRect;
Element.prototype.getBoundingClientRect = function () {
  const cls = (this.getAttribute && this.getAttribute("class")) || "";
  if (this.tagName && this.tagName.toLowerCase() === "svg" && /(^| )map( |$)/.test(cls)) {
    return {left: 0, top: 0, width: 1035, height: 610, right: 1035, bottom: 610};
  }
  return boxOf.call(this);
};

function boot(width, isPhone) {
  const doc = new Document(html);
  const timers = [];
  const win = {document: doc, innerWidth: width, innerHeight: 1000, devicePixelRatio: 1, scrollX: 0, scrollY: 0,
    listeners: {}, addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); },
    setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout(id) { if (id) { timers[id - 1] = null; } },
    location: {hash: "", protocol: "file:"}, history: {replaceState(s, t, url) { win.location.hash = url; }},
    console: console};
  if (isPhone) { win.matchMedia = (q) => ({matches: q.indexOf("max-width") >= 0, addEventListener() {}}); }
  win.window = win;
  const ctx = vm.createContext(win);
  for (const name of ["data.js", "scoring.js", "route.js", "claims.js", "app.js"]) {
    try { vm.runInContext(fs.readFileSync(path.join(SITE, name), "utf8"), ctx, {filename: name}); }
    catch (e) { errors.push(name + " threw: " + (e && e.stack || e)); }
  }
  const flush = () => {
    for (let guard = 0; guard < 400 && timers.some(Boolean); guard++) {
      const i = timers.findIndex(Boolean), fn = timers[i];
      timers[i] = null;
      fn();
    }
  };
  flush();
  return {doc, win, ctx, flush};
}

const {doc, win, ctx, flush} = boot(1600, false);
check("index.html parses with every tag closed", doc.errors.length === 0, doc.errors.slice(0, 3).join("; "));
const AS = win.AS, P = win.ASP;
const click = (el) => { doc.dispatch("click", el); flush(); };
const input = (el, value) => { el.value = value; doc.dispatch("input", el); flush(); };
const go = (hash) => { win.location.hash = hash; P.nav(hash); flush(); };
const $ = (s) => doc.querySelector(s), $$ = (s) => doc.querySelectorAll(s);
const visible = (id) => doc.getElementById(id).classList.contains("on");
const clean = (where, text) => {
  const bad = (text.match(/undefined|NaN|\{[a-z_]+\}|\[object Object\]/g) || []).filter((m) => m !== "{first_name}" && m !== "{sender_name}");
  check(where + " shows no undefined, NaN or unfilled field", !bad.length, bad.slice(0, 3).join(" "));
};

if (P) {
  attempt("the map", () => {
    const ranked = P.ranked();
    const onMap = AS.accounts.filter((a) => a.hub).length;
    check("the page opens on the map", P.state().view === "map" && visible("v-map"));
    const marks = P.marks();
    const counted = marks.reduce((t, m) => t + m.n, 0);
    check("every account with a US city sits in a ring or a dot", counted === onMap && $$(".map .ring").length === marks.length, counted + " of " + onMap);
    check("a ring's number is its count", $$(".map .ring .count").length > 0 &&
      $$(".map .ring").every((el) => { const m = marks.find((x) => x.slugs[0] === el.getAttribute("data-ring")); const c = el.querySelector(".count");
        return m && (m.n === 1 ? !c : c && Number(c.textContent) === m.n); }));
    const isTop = (slug) => P.ranked().findIndex((a) => a.slug === slug) < 10;
    const tops = $$(".map .ring").filter((el) => (marks.find((x) => x.slugs[0] === el.getAttribute("data-ring")) || {slugs: []}).slugs.some(isTop));
    check("every city holding a top ten account wears a dark ring", tops.length > 0 && tops.every((el) => el.querySelector(".topring") || el.querySelector(".one.top")),
      tops.length + " cities");
    check("every state is drawn", $$(".map .st").length >= 50, $$(".map .st").length);
    const left = Math.min.apply(null, ($(".map .nation").getAttribute("d").match(/[ML](-?\d+),/g) || []).map((m) => Number(m.slice(1, -1))));
    check("the map's frame takes in every island", $(".map").getAttribute("viewBox").split(" ")[0] <= left, $(".map").getAttribute("viewBox") + " for " + left);
    check("the top list holds ten accounts", $$(".toplist .acct").length === Math.min(10, ranked.length));
    check("the top account is selected", P.current().slug === ranked[0].slug && $(".acct.sel") && $(".acct.sel").getAttribute("data-slug") === ranked[0].slug);
    check("the leader's sentence names it", ($("#why") || {textContent: ""}).textContent.indexOf(ranked[0].name) >= 0);
    check("the fresh pill gives the board count", ($("#fresh") || {textContent: ""}).textContent.indexOf(String(AS.meta.stats.boards_read)) >= 0);
    check("labels are drawn for the leaders", $$(".map .labels text").length >= 4, $$(".map .labels text").length);
    clean("the map", doc.getElementById("v-map").innerHTML);
    const rk = path.join(ROOT, "data", AS.meta.preview ? "preview" : "out", "ranking.json");
    if (fs.existsSync(rk)) {
      const py = JSON.parse(fs.readFileSync(rk, "utf8")).accounts;
      const pyOrder = py.slice().sort((x, y) => (y.score - x.score) || (x.account < y.account ? -1 : 1));
      const same = pyOrder.every((a, i) => ranked[i] && ranked[i].name === a.account && Math.abs(ranked[i].r.score - a.score) < 1e-9 &&
        ranked[i].r.tier === a.tier && Math.abs(ranked[i].r.fit - a.fit) < 1e-9 && Math.abs(ranked[i].r.intent - a.intent) < 1e-9);
      check("the page scores and ranks every account exactly as the build did", same && pyOrder.length === ranked.length);
      const routes = P.routes();
      check("the page routes every account exactly as the build did", py.every((a) => JSON.stringify(routes[a.account]) === JSON.stringify(a.route)));
    }
    const overlapping = (ms) => ms.reduce((t, a, i) => t + ms.slice(i + 1).filter((b) => Math.hypot(a.x - b.x, a.y - b.y) < a.r + b.r).length, 0);
    check("no two rings overlap", overlapping(marks) === 0, overlapping(marks) + " overlapping pairs");
    const box = () => $(".map").getAttribute("viewBox").split(" ").map(Number);
    const whole = box();
    const dotPx = () => $$(".map .ring.single .one").map((c) => Number(c.getAttribute("r")) * P.zoom().k);
    check("the map opens on the whole frame with zoom out and reset off", P.zoom().k === 1 && $("[data-zoom='out']").disabled && $("[data-zoom='reset']").disabled);
    click($("[data-zoom='in']"));
    check("the zoom button zooms in", P.zoom().k === 2 && Math.abs(box()[2] - whole[2] / 2) < 0.2, box().join(" "));
    check("every dot keeps its size on the screen as the map zooms", dotPx().length > 0 && dotPx().every((r) => Math.abs(r - 5) < 0.01 || Math.abs(r - 7.4) < 0.01),
      dotPx().slice(0, 4).join(", "));
    const zmarks = P.marks();
    check("the rings group again at the new zoom with none overlapping and more cities apart", overlapping(zmarks) === 0 && zmarks.length >= marks.length,
      zmarks.length + " marks from " + marks.length);
    const v = box();
    const labels = $$(".map .labels text").map((t) => [Number(t.getAttribute("x")), Number(t.getAttribute("y"))]);
    check("the labels name only accounts in view", labels.length > 0 && labels.every((xy) => xy[0] >= v[0] && xy[0] <= v[0] + v[2] && xy[1] >= v[1] && xy[1] <= v[1] + v[3]),
      labels.length + " labels");
    for (let i = 0; i < 4; i++) { click($("[data-zoom='in']")); }
    check("the zoom stops at sixteen times", P.zoom().k === 16 && $("[data-zoom='in']").disabled);
    click($("[data-zoom='reset']"));
    check("reset shows the whole map again", P.zoom().k === 1 && box().join(" ") === whole.join(" ") && P.marks().length === marks.length);
    click($("[data-region='Northeast']"));
    const ne = ranked.filter((a) => a.hub && a.region === "Northeast"), nv = box();
    check("a region's chip zooms to its accounts", P.zoom().k > 1 && ne.length > 0 &&
      ne.every((a) => a.hub[2] >= nv[0] && a.hub[2] <= nv[0] + nv[2] && a.hub[3] >= nv[1] && a.hub[3] <= nv[1] + nv[3]), P.zoom().k.toFixed(2) + " for " + ne.length);
    click($("[data-region='all']"));
    check("All regions shows the whole map", P.zoom().k === 1 && box().join(" ") === whole.join(" "));
    const west = $("[data-region='West']");
    click(west);
    const westCount = AS.accounts.filter((a) => a.hub && P.accounts.find((x) => x.name === a.name).region === "West").length;
    const westOn = P.marks().reduce((t, m) => t + m.n, 0);
    check("a region chip keeps only its accounts on the map", westOn === westCount, westOn + " of " + westCount);
    check("the top list follows the region", $$(".toplist .acct").every((r) => P.accounts.find((x) => x.slug === r.getAttribute("data-slug")).region === "West"));
    click($("[data-region='all']"));
    const many = P.marks().find((m) => m.n > 1);
    click($(".map .ring[data-ring='" + many.slugs[0] + "']"));
    check("a ring lists its accounts beside the map", $$(".toplist .acct").length === many.n &&
      ($(".sidehead h3") || {textContent: ""}).textContent.indexOf(many.place) === 0, $$(".toplist .acct").length + " of " + many.n);
    check("the picked ring stands out and the rest fade", $$(".map .ring.picked").length === 1 && $$(".map .ring.fade").length === P.marks().length - 1);
    click($("[data-ring-back]"));
    check("back returns to the top ten", $$(".toplist .acct").length === Math.min(10, ranked.length) && $$(".map .ring.fade").length === 0);
    const one = P.marks().find((m) => m.n === 1 && (P.accounts.find((x) => x.slug === m.slugs[0]).fp || []).length > 1);
    const solo = P.accounts.find((x) => x.slug === one.slugs[0]);
    click($(".map .ring[data-ring='" + solo.slug + "']"));
    check("a dot picks its account and lights up every city it hires in", P.current().slug === solo.slug && $$(".map .foot .fp").length === solo.fp.length,
      $$(".map .foot .fp").length + " of " + solo.fp.length);
    check("the card says where it hires", ($("#card .fpline") || {textContent: ""}).textContent.indexOf(AS.fpc[solo.fp[0][0]][0]) >= 0);
    check("the caption on the map says what the dots are", !$("#fpcap").hidden && $("#fpcap").textContent.indexOf(solo.name) === 0 &&
      $("#fpcap").textContent.indexOf(String(solo.fp.length)) > 0, $("#fpcap").textContent);
    click($(".map .st"));
    check("the map's empty space clears the pick", $$(".map .foot .fp").length === 0 && $$(".map .ring.fade").length === 0);
    const row0 = $(".toplist .acct"), a0 = P.accounts.find((x) => x.slug === row0.getAttribute("data-slug"));
    doc.dispatch("mouseover", row0);
    check("pointing at a top ten row lights up every city it hires in", (a0.fp || []).length > 0 && $$(".map .foot .fp").length === a0.fp.length,
      $$(".map .foot .fp").length + " of " + (a0.fp || []).length);
    doc.dispatch("mouseover", $(".map .st"));
    check("the cities go dark when the pointer leaves", $$(".map .foot .fp").length === 0 && $("#fpcap").hidden);
    click($(".acct[data-slug='" + ranked[1].slug + "']"));
    check("a top list row opens its account", P.state().view === "account" && P.current().slug === ranked[1].slug &&
      win.location.hash === "#/a/" + ranked[1].slug, win.location.hash);
  });

  attempt("the live check against the recorder's", () => {
    let n = 0, same = 0, first = "";
    P.ranked().forEach((a) => a.briefs.forEach((b) => {
      const t = b.brief.first_touch || {};
      const js = win.ASClaims.checkTouch({subject: t.subject || "", body: t.body || "", cites: t.cites || []},
        AS.sources[a.name] || {}, a.name, AS.meta.read_on, AS.tools, new Set(AS.first_names));
      const row = (b.flags.rows || []).find((r) => r.field === "first_touch");
      const py = row ? row.problems.filter((x) => x.indexOf("writing:") !== 0) : [];
      n++;
      if (JSON.stringify(js) === JSON.stringify(py)) { same++; } else if (!first) { first = a.name + " " + b.model + ": " + JSON.stringify(js) + " vs " + JSON.stringify(py); }
    }));
    check("the page's live check agrees with the recorder on every recorded first touch", same === n, same + " of " + n + " " + first);
  });

  const withBrief = P.ranked().find((a) => a.briefs.length);
  attempt("an account", () => {
    if (!withBrief) { check("an account has a brief", false, "no briefs in this build"); return; }
    go("#/map/" + withBrief.slug);
    click($("#card a.btn.pri"));
    check("the card opens the account", P.state().view === "account" && visible("v-account") && win.location.hash === "#/a/" + withBrief.slug);
    const chips = $$(".brief .cite[data-c]");
    const rows = $$(".sources .src[data-src]");
    check("the brief cites its sources", chips.length > 0 && rows.length > 1, chips.length + " citations, " + rows.length + " sources");
    check("every citation has a source to land on", chips.every((c) => $(".sources .src[data-src='" + c.getAttribute("data-c") + "']")));
    check("every citation has a thread", $$("svg.threads path").length === chips.length, $$("svg.threads path").length + " of " + chips.length);
    const sent = $(".brief [data-i='w0']");
    doc.dispatch("mouseover", sent);
    check("pointing at a sentence lights its sources", $$(".sources .src.hot").length > 0 && $$("svg.threads path.hot").length > 0);
    check("the second read is shown", !!$("#read .verdict"));
    check("the brief's model switch lists every model that wrote it", $$(".models button").length === withBrief.briefs.length);
    const models = $$(".models button").map((b) => b.getAttribute("data-model"));
    models.forEach((m) => {
      click($(".models button[data-model='" + m + "']"));
      check("the switch shows " + m + "'s brief", $(".models button[aria-pressed='true']").getAttribute("data-model") === m && P.briefOf(P.current()).model === m);
    });
    click($(".models button[data-model='" + models[0] + "']"));
    clean("the account", doc.getElementById("v-account").innerHTML);
    const b = P.briefOf(P.current());
    const startProblems = P.touchProblems(P.current(), b);
    check("the recorded first touch passes the live check", startProblems.length === 0 || b.needs_review, startProblems.join("; "));
    click($("[data-touch='edit']"));
    check("edit opens the email", !$("#t-body").hasAttribute("readonly"));
    input($("#t-body"), $("#t-body").value + "\n\nWe guarantee a 40% lift in revenue for Quorvex Freight.");
    check("an edit with a promise and a stranger's name is flagged as you type", !$("#checks").classList.contains("ok") && $$("#checks li").length >= 2,
      ($("#checks") || {textContent: ""}).textContent);
    check("approve waits while the checks flag something", $("[data-touch='approve']").disabled === true);
    click($("[data-touch='reset']"));
    check("undo restores the recorded email", $("#checks").classList.contains("ok") && !$("[data-touch='approve']").hasAttribute("disabled"));
    click($("[data-touch='approve']"));
    check("approve marks it approved and not sent", ($("#tstatus") || {textContent: ""}).textContent.length > 0 && $("#tstatus .ok"));
    click($("[data-touch='reject']"));
    check("reject marks it rejected", !!$("#tstatus .no"));
  });

  attempt("the score", () => {
    const a = withBrief || P.ranked()[0];
    go("#/a/" + a.slug);
    click($(".vtabs a[href='#/a/" + a.slug + "/score']"));
    check("the score tab opens the score", P.state().view === "score" && visible("v-score"));
    check("the chart draws the score and intent lines", !!$("#chart .lscore") && !!$("#chart .lintent"));
    check("every counted signal has a row", $$("#rows .row").length >= a.r.intent_rows.length + 4, $$("#rows .row").length);
    clean("the score", doc.getElementById("v-score").innerHTML);
    const before = P.ranked().map((x) => x.name + x.r.score).join("|");
    const marksBefore = JSON.stringify(P.marks());
    input($("#c-share"), "0");
    check("with no weight on intent every score is its fit", P.ranked().every((x) => Math.abs(x.r.score - x.r.fit) < 1e-9));
    check("moving a weight re-ranks the accounts", P.ranked().map((x) => x.name + x.r.score).join("|") !== before);
    check("moving a weight regroups the map's rings", JSON.stringify(P.marks()) !== marksBefore);
    check("the page says the weights moved", !$("#moved").hasAttribute("hidden"));
    input($("#c-half"), "7");
    check("the half-life control moves", P.state().half === 7);
    const fam = $("[data-ctl='fam']");
    input(fam, "0");
    check("a family's points move", P.state().points[fam.getAttribute("data-fam")] === 0);
    click($("[data-ctl-reset]"));
    check("reset restores the defaults and the ranking", P.ranked().map((x) => x.name + x.r.score).join("|") === before && $("#moved").hasAttribute("hidden"));
  });

  attempt("the list", () => {
    go("#/list");
    check("the list opens", P.state().view === "list" && visible("v-list"));
    check("the list holds every account", $$("table.accts tbody tr").length === AS.accounts.length, $$("table.accts tbody tr").length);
    const nums = $$("table.accts tbody tr").slice(0, 40).map((tr) => Array.prototype.slice.call(tr.querySelectorAll("td.num"), 1).map((td) => td.textContent))
      .reduce((x, y) => x.concat(y), []);
    check("the list's fit, intent and score line up on one decimal", nums.length === 120 && nums.every((t) => /^\d+\.\d$/.test(t)), nums.filter((t) => !/^\d+\.\d$/.test(t)).slice(0, 3).join(", "));
    click($("[data-ftier='A']"));
    const nA = P.ranked().filter((a) => a.r.tier === "A").length;
    check("the tier filter narrows the list", $$("table.accts tbody tr").length === nA, $$("table.accts tbody tr").length + " of " + nA);
    click($("[data-ftier='all']"));
    click($("[data-sort='name']"));
    const names = $$("table.accts tbody tr .n").map((n) => n.textContent.toLowerCase());
    check("a column sorts the list", names.every((n, i) => i === 0 || names[i - 1] <= n));
    click($("[data-sort='score']"));
    click($("[data-fbrief]"));
    const nb = P.ranked().filter((a) => a.briefs.length).length;
    check("the brief filter shows the accounts with a brief", $$("table.accts tbody tr").length === nb, $$("table.accts tbody tr").length + " of " + nb);
    click($("[data-fbrief]"));
    clean("the list", doc.getElementById("v-list").innerHTML);
    const row = $("table.accts tbody tr");
    click(row);
    check("a row opens its account", P.state().view === "account" && P.current().slug === row.getAttribute("data-open"));
  });

  attempt("how it works", () => {
    go("#/how");
    check("How it works opens", P.state().view === "how" && visible("v-how"));
    ["sources", "exclusions", "read", "scoring", "routing", "briefs", "second", "board", "team", "limits", "code"].forEach((id) =>
      check("How it works has its " + id + " section", !!doc.getElementById("how-" + id)));
    check("five featured files sit in one row", $$(".files button").length === 5);
    clean("How it works", doc.getElementById("v-how").innerHTML);
    const sc = doc.getElementById("codejs");
    check("the code opens with How it works", !!sc && sc.getAttribute("src") === "code.js");
    vm.runInContext(fs.readFileSync(path.join(SITE, "code.js"), "utf8"), ctx, {filename: "code.js"});
    if (sc && sc.onload) { sc.onload(); }
    flush();
    const C = win.AS_CODE, names = Object.keys(C.files);
    const meta = () => ($(".codeview .meta") || {textContent: ""}).textContent;
    check("the code opens on its default file", meta().indexOf(C.default + " · ") === 0, meta());
    check("the file pane lists every file in its folder", $$("#codetree button").length === names.length && $$("#codetree p").length >= 4,
      $$("#codetree button").length + " of " + names.length);
    check("every featured file is in the pane", $$(".files button").every((b) => names.indexOf(b.getAttribute("data-file")) >= 0));
    check("every file shown is an excerpt, never the whole file", names.every((n) => {
      const f = C.files[n];
      return f.parts.reduce((t, p) => t + p[1].split("\n").length, 0) < f.lines;
    }));
    const pick = $$("#codetree button").find((b) => b.getAttribute("data-file") === "site/scoring.js") || $("#codetree button");
    click(pick);
    const rel = pick.getAttribute("data-file"), f = C.files[rel];
    const numbered = $$(".codeview pre span[data-n]");
    const want = f.parts.reduce((t, p) => t + p[1].split("\n").length, 0);
    check("a file in the pane opens its excerpt", meta().indexOf(rel + " · ") === 0 && pick.getAttribute("aria-pressed") === "true", meta());
    check("every line keeps its number from its file", numbered.length === want && numbered[0].getAttribute("data-n") === String(f.parts[0][0]),
      numbered.length + " of " + want);
    check("a gap mark stands wherever the excerpt skips lines", $$(".codeview pre .gap").length >= f.parts.length - 1);
  });

  attempt("the tour", () => {
    click($("[data-tour='0']"));
    check("the tour starts at its first address", win.location.hash === "#/tour/1" && !doc.getElementById("tour").hidden);
    const n = P.tour.length;
    check("the tour has ten steps", n === 10, n);
    for (let i = 1; i <= n; i++) {
      const spot = $$(".spot");
      check("tour step " + i + " spotlights its part of the page", spot.length === 1, P.tour[i - 1].key + " " + spot.length);
      if (i < n) { click($("[data-tour-next]")); }
    }
    check("the last step is the tenth address", win.location.hash === "#/tour/10");
    click($("[data-tour-back]"));
    check("back goes one step", win.location.hash === "#/tour/9");
    go("#/tour/4");
    check("a tour address opens its step directly", P.state().tour === 3 && P.state().view === "account");
    doc.dispatch("keydown", doc.body, {key: "Escape"});
    flush();
    check("escape closes the tour", doc.getElementById("tour").hidden && $$(".spot").length === 0);
  });

  attempt("deep links", () => {
    const a = P.ranked()[5];
    go("#/a/" + a.slug + "/score");
    check("a score address opens that account's score", P.state().view === "score" && P.current().slug === a.slug);
    go("#/map/" + a.slug);
    check("a map address selects its account", P.state().view === "map" && P.current().slug === a.slug);
    go("#/nowhere");
    check("an unknown address falls back to the map", P.state().view === "map");
  });
}

attempt("the phone", () => {
  const ph = boot(390, true);
  const PP = ph.win.ASP;
  check("on a phone the map, the account and the score share one strip", ph.doc.getElementById("strip").classList.contains("on") &&
    ["v-map", "v-account", "v-score"].every((id) => ph.doc.getElementById(id).classList.contains("on")));
  check("the phone's tab bar has four tabs", ph.doc.querySelectorAll("[data-tab]").length === 4);
  ph.doc.dispatch("click", ph.doc.querySelector("[data-tab='account']"));
  ph.flush();
  check("a tab moves to its screen", PP.state().view === "account" && ph.doc.querySelector("[data-tab='account']").getAttribute("aria-current") === "true");
  ph.doc.dispatch("click", ph.doc.querySelector("[data-tab='how']"));
  ph.flush();
  check("How it works leaves the strip", PP.state().view === "how" && !ph.doc.getElementById("strip").classList.contains("on"));
});

check("the scripts ran without an error", errors.length === 0, errors.slice(0, 3).join(" | "));
const failed = checks.filter((c) => !c.ok);
failed.forEach((c) => console.log("FAIL " + c.name + (c.detail ? " (" + c.detail + ")" : "")));
errors.slice(0, 5).forEach((e) => console.log("ERROR " + e));
console.log(checks.length - failed.length + " of " + checks.length + " page checks pass");
process.exit(failed.length ? 1 : 0);
