/* Account Signals: the page. It reads window.AS (site/data.js), scores every account with site/scoring.js, routes
   them with site/route.js and checks an edited first touch with site/claims.js, the same arithmetic and rules as the
   build. Five views: the map (the default and the homepage card), an account with its brief, the account's score with
   live weights, the list, and How it works. Each view and each tour step has its own address. Events are delegated
   from the document, nothing is sent anywhere, and every visible word comes from WORDS.md through AS.words. */
(function () {
  "use strict";
  const AS = window.AS, S = window.ASScoring, R = window.ASRoute, C = window.ASClaims;
  if (!AS || !S || !R) { return; }
  const W = AS.words || {};
  const doc = document;
  const MONTHS = String(W.months || "").split(" ");
  const READ_ON = AS.meta.read_on;
  const READ_DAY = S.dayNumber(READ_ON);
  const FAMS = AS.meta.families;
  const STRIP = ["map", "account", "score"];
  const PARTS = ["W1", "W2", "W3", "P", "E"];

  /* Helpers */
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"})[c]);
  const fill = (t, v) => String(t == null ? "" : t).replace(/\{(\w+)\}/g, (m, k) => (v[k] == null ? m : v[k]));
  const $ = (sel, root) => (root || doc).querySelector(sel);
  const $$ = (sel, root) => Array.prototype.slice.call((root || doc).querySelectorAll(sel));
  const f1 = (x) => (Number.isInteger(x) ? String(x) : (Math.round(x * 10) / 10).toFixed(1));
  const d1 = (x) => (Math.round(Number(x || 0) * 10) / 10).toFixed(1);
  const n0 = (x) => Number(x || 0).toLocaleString("en-US");
  const slugOf = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const mdate = (iso) => { if (!iso) { return ""; } const p = iso.split("-").map(Number); return MONTHS[p[1] - 1] + " " + p[2]; };
  const later = (fn, ms) => window.setTimeout(fn, ms || 0);
  const mq = window.matchMedia ? window.matchMedia("(max-width: 720px), (max-height: 520px) and (max-width: 1000px) and (orientation: landscape)") : null;
  const phone = () => !!(mq && mq.matches);
  const calm = () => !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const first = (el) => (el && el.children ? el.children[0] : null);
  const TITLE = doc.title || "";

  /* The data, unpacked */
  const SIG = AS.signals.map((r, i) => ({
    sid: i, family: FAMS[r[0]], age: r[1], posted: r[1] == null ? "" : S.isoDay(READ_DAY - r[1]),
    kind: AS.meta.date_kinds[r[2]], temporary: !!r[3], title: AS.titles[r[4]], quote: r[5],
    url: AS.links[r[6]].replace("{}", r[7]), uid: r[7], tool: r[8], carried: r[9], read_on: READ_ON}));
  const ACCTS = AS.accounts.map((a) => Object.assign({}, a, {
    slug: slugOf(a.name), read_on: READ_ON, list: a.sigs.map((i) => SIG[i]),
    state: a.hub ? a.hub[1] : "", region: R.regionOf(a.hub ? a.hub[1] : "", AS.model.routing),
    briefs: AS.briefs[a.name] || []}));
  const FIRST = new Set(AS.first_names || []);
  const NB = ACCTS.filter((a) => a.briefs.length).length;
  const BY = {};
  ACCTS.forEach((a) => { BY[a.slug] = a; });
  const DEFAULTS = {share: AS.model.weights.intent_share, half: AS.model.weights.half_life_days,
    points: Object.assign({}, AS.model.points)};

  const st = {view: "map", sel: "", region: "all", share: DEFAULTS.share, half: DEFAULTS.half,
    points: Object.assign({}, DEFAULTS.points), model: {}, touch: {}, sort: {col: "score", dir: -1},
    ftier: "all", fregion: "all", fbrief: false, tour: -1, file: "", hash: null, drawn: false,
    zoom: {k: 1, cx: null, cy: null}, zooming: false, dragged: 0, ver: 0, ring: null, fp: null, hover: null};
  let ranked = [], routes = {};

  /* Scoring, ranking and routing with the current weights */
  const opts = () => ({intent_share: st.share, half_life: st.half, points: st.points});
  function rescore() {
    const o = opts();
    ACCTS.forEach((a) => { a.r = S.score(a, a.list, AS.model, o); });
    ranked = ACCTS.slice().sort((x, y) => (y.r.score - x.r.score) || (x.name < y.name ? -1 : x.name > y.name ? 1 : 0));
    ranked.forEach((a, i) => { a.rank = i + 1; });
    routes = R.route(ranked.map((a) => ({account: a.name, score: a.r.score, tier: a.r.tier, openings: a.openings,
      state: a.state})), AS.model.routing, READ_ON);
  }
  const moved = () => st.share !== DEFAULTS.share || st.half !== DEFAULTS.half ||
    Object.keys(DEFAULTS.points).some((k) => st.points[k] !== DEFAULTS.points[k]);
  const current = () => BY[st.sel] || ranked[0];
  const briefAccount = () => ranked.find((a) => a.briefs.length) || ranked[0];

  /* Words built from the score, never from a model */
  function whenText(s) {
    const t = W.when || {};
    if (s.age == null) { return t.undated; }
    if (s.age === 0) { return t.today; }
    if (s.age === 1) { return t.one; }
    return fill(t[s.kind] || t.published, {n: s.age});
  }
  const strongest = (a) => a.r.intent_rows.filter((x) => x.family !== "pace" && x.family !== "stack")
    .sort((x, y) => (y.points - x.points) || (x.sid - y.sid));
  const phrase = (row) => (W.family || {})[row.family] + " " + whenText(SIG[row.sid]);
  function bandOf(a) { const r = a.r.fit_rows.find((x) => x.part === "open_roles"); return r ? r.band : ""; }
  function whyText(a) {
    const out = [fill(W["why.lead"], {name: a.name, score: f1(a.r.score), intent: f1(a.r.intent), fit: f1(a.r.fit)})];
    const top = strongest(a).slice(0, 2);
    if (top.length === 2) { out.push(fill(W["why.signals"], {list: fill(W["why.pair"], {a: phrase(top[0]), b: phrase(top[1])})})); }
    else if (top.length === 1) { out.push(fill(W["why.signal"], {one: phrase(top[0])})); }
    else { out.push(W["why.none"]); }
    out.push(fill(W["why.fit"], {industry: (W.industry || {})[a.industry] || a.industry, band: bandOf(a)}));
    return out.join(" ");
  }
  function reasonText(a) { const top = strongest(a)[0]; return top ? phrase(top) : W["reason.fit"]; }
  function routeText(a) {
    const rt = routes[a.name];
    if (!rt) { return ""; }
    if (rt.overflow) { return fill(W["route.overflow"], {territory: rt.territory}); }
    if (!rt.deadline) { return fill(W["route.nodue"], {seat: rt.seat}); }
    return fill(W["route.line"], {seat: rt.seat, date: mdate(rt.deadline)});
  }
  const hubText = (a) => (a.hub ? fill(W["acct.hub"], {city: a.hub[0] + ", " + a.hub[1]}) : W["acct.nohub"]);
  const rolesText = (a) => (a.openings === 1 ? W["acct.one"] : fill(W["acct.roles"], {n: n0(a.openings)}));
  const tierTag = (t) => "<span class='tier " + t.toLowerCase() + "'>" + esc(t) + "</span>";
  const famLabel = (f) => {
    const l = String(AS.model.labels[f] || f).replace(/^A /, "");
    return l.charAt(0).toUpperCase() + l.slice(1);
  };
  const cites = (text) => esc(text).replace(/\[(\d+)\]/g, (m, k) => "<span class='cite' data-c='" + k + "'>" + k + "</span>");

  /* The briefs: the routed model's first, then the rest in the config's order */
  function modelsOf(a) {
    const order = [AS.meta.route].concat(Object.keys(AS.meta.models));
    return a.briefs.slice().sort((x, y) => {
      const i = order.indexOf(x.model), j = order.indexOf(y.model);
      return (i < 0 ? 99 : i) - (j < 0 ? 99 : j);
    });
  }
  function briefOf(a) {
    const list = modelsOf(a);
    return list.find((b) => b.model === st.model[a.slug]) || list[0] || null;
  }
  function readState(b) {
    if (!b || !b.read) { return {cls: "none", text: W["read.none"]}; }
    if (b.read.both) { return {cls: "ok", text: W["read.both"]}; }
    const js = Object.values(b.read.judges);
    const flagged = js.filter((j) => j.verdict !== "holds up").length;
    const wrong = js.some((j) => j.verdict === "wrong");
    return {cls: wrong ? "bad" : "warn", text: flagged > 1 ? W["read.two"] : W["read.one"]};
  }
  const verdictTag = (b) => { const r = readState(b); return "<span class='verdict " + r.cls + "'>" + esc(r.text) + "</span>"; };

  /* The map: one ring per city where accounts hire most. A ring's size is how many accounts are there, its colors the mix
     of tiers and its number the count, and a city with one account is a dot. A city that holds a top ten account wears a
     dark ring. Rings that only touch are nudged apart within half their size, and the ones still overlapping merge until a
     zoom pulls their cities apart. Every size is in pixels on the screen, so a ring keeps its size at any zoom. */
  const TOP = 10;
  const RING = {one: 5, oneTop: 7.4, base: 7, per: 2.5, top: 2};
  const isTop = (a) => a.rank <= TOP;
  function inRegion(a) {
    if (st.region === "all") { return true; }
    if (st.region === "tierA") { return a.r.tier === "A"; }
    return a.region === st.region;
  }
  function ringR(g) {
    const n = g.members.length, top = g.members.some(isTop);
    return n === 1 ? (top ? RING.oneTop : RING.one) : RING.base + RING.per * Math.sqrt(n) + (top ? RING.top : 0);
  }
  /* A ring that holds one city takes its name. A merged ring is named for the city with the most of its accounts, the
     better rank first on a tie, so a ring of 42 Northeast accounts reads as the New York area and not as its leader's
     smaller city. */
  function placeName(g) {
    const cities = {};
    g.members.forEach((a) => {
      const c = a.hub[0] + ", " + a.hub[1];
      cities[c] = cities[c] || {n: 0, city: a.hub[0], rank: a.rank};
      cities[c].n += 1;
    });
    const list = Object.keys(cities).map((c) => cities[c]);
    if (list.length === 1) { return list[0].city; }
    list.sort((p, q) => (q.n - p.n) || (p.rank - q.rank));
    return fill(W["ring.area"], {city: list[0].city});
  }
  let marks = [], marksKey = "";
  /* The groups at scale s, in pixels of the whole frame, so a pan reuses them and only a zoom, a region or new weights
     group the cities again. */
  function groupsAt(s) {
    const key = s.toFixed(5) + "|" + st.region + "|" + st.ver;
    if (key === marksKey) { return marks; }
    const by = {};
    ranked.forEach((a) => { if (a.hub && inRegion(a)) { const c = a.hub[0] + ", " + a.hub[1]; (by[c] = by[c] || []).push(a); } });
    const gs = Object.keys(by).sort().map((c) => {
      const m = by[c];
      return {members: m, ax: m[0].hub[2] * s, ay: m[0].hub[3] * s, x: m[0].hub[2] * s, y: m[0].hub[3] * s};
    });
    for (let round = 0; round < 80; round++) {
      let moved = false;
      for (let i = 0; i < gs.length; i++) {
        for (let j = i + 1; j < gs.length; j++) {
          const a = gs[i], b = gs[j], dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01;
          const need = ringR(a) + ringR(b) + 3;
          if (d < need) {
            const push = (need - d) / 2 + 0.05;
            a.x -= dx / d * push; a.y -= dy / d * push;
            b.x += dx / d * push; b.y += dy / d * push;
            moved = true;
          }
        }
      }
      gs.forEach((g) => {
        const ox = g.x - g.ax, oy = g.y - g.ay, lim = 0.5 * ringR(g), off = Math.hypot(ox, oy);
        if (off > lim) { g.x = g.ax + ox / off * lim; g.y = g.ay + oy / off * lim; }
      });
      if (!moved) { break; }
    }
    let merged = true;
    while (merged) {
      merged = false;
      for (let i = 0; i < gs.length && !merged; i++) {
        for (let j = i + 1; j < gs.length; j++) {
          const a = gs[i], b = gs[j];
          if (Math.hypot(b.x - a.x, b.y - a.y) < ringR(a) + ringR(b) + 3) {
            const na = a.members.length, nb = b.members.length, t = na + nb;
            a.x = (a.x * na + b.x * nb) / t; a.y = (a.y * na + b.y * nb) / t;
            a.ax = (a.ax * na + b.ax * nb) / t; a.ay = (a.ay * na + b.ay * nb) / t;
            a.members = a.members.concat(b.members).sort((p, q) => p.rank - q.rank);
            gs.splice(j, 1);
            merged = true;
            break;
          }
        }
      }
    }
    marks = gs;
    marksKey = key;
    return gs;
  }
  function ringSvg(g, s, faded, picked) {
    const k = 1 / s, x = (g.x * k).toFixed(2), y = (g.y * k).toFixed(2), at = "' cx='" + x + "' cy='" + y + "' r='";
    const n = g.members.length, best = g.members[0], top = g.members.some(isTop), R = ringR(g);
    const label = n === 1 ? fill(W["ring.one"], {name: best.name, city: best.hub[0], score: f1(best.r.score)}) :
      fill(W["ring.many"], {place: placeName(g), n: n, name: best.name});
    let out = "<g class='ring" + (n === 1 ? " single" : "") + (faded ? " fade" : "") + (picked ? " picked" : "") + "' data-ring='" +
      best.slug + "' role='button' tabindex='0' aria-label='" + esc(label) + "'>";
    if (picked) { out += "<circle class='halo" + at + ((R + 7) * k).toFixed(3) + "'/>"; }
    if (n === 1) {
      return out + "<circle class='one t" + best.r.tier + (top ? " top" : "") + at + (R * k).toFixed(3) + "' stroke-width='" +
        ((top ? 1.8 : 1.6) * k).toFixed(3) + "'/></g>";
    }
    const body = R - (top ? RING.top : 0), thick = Math.max(4, body * 0.42), mid = body - thick / 2;
    out += "<circle class='bg" + at + ((body + 1) * k).toFixed(3) + "'/>";
    let start = 0;
    ["A", "B", "C", "D"].forEach((t) => {
      const c = g.members.filter((a) => a.r.tier === t).length;
      if (!c) { return; }
      const pct = 100 * c / n;
      out += "<circle class='seg t" + t + at + (mid * k).toFixed(3) + "' pathLength='100' stroke-width='" + (thick * k).toFixed(3) +
        "' stroke-dasharray='" + pct.toFixed(2) + " " + (100 - pct).toFixed(2) + "' stroke-dashoffset='" + (-start).toFixed(2) +
        "' transform='rotate(-90 " + x + " " + y + ")'/>";
      start += pct;
    });
    if (top) { out += "<circle class='topring" + at + ((body + 1.2) * k).toFixed(3) + "' stroke-width='" + (1.8 * k).toFixed(3) + "'/>"; }
    return out + "<text class='count' x='" + x + "' y='" + ((g.y + 3.8) * k).toFixed(2) + "' font-size='" + (10.5 * k).toFixed(3) + "'>" + n + "</text></g>";
  }
  /* Labels in screen pixels, the leaders first. A label stays clear of the other labels, the box's edge, the caption's
     strip at the top and every ring's number, and of the other marks when it can. Only the first few may cover a mark
     when no clear spot is left, and none ever covers a number. */
  function labelsSvg(list, obstacles, v, most, lead, counts, top) {
    const s = v.s, w0 = v.w * s, h0 = v.h * s, boxes = [];
    const clamp = (q, lo, hi) => Math.max(lo, Math.min(hi, q));
    const fits = (b) => b.x >= 4 && b.y >= (top || 4) && b.x + b.w <= w0 - 44 && b.y + b.h <= h0 - 4;
    const crowds = (b) => boxes.some((o) => b.x < o.x + o.w && o.x < b.x + b.w && b.y < o.y + o.h && o.y < b.y + b.h);
    const near = (m, b, d) => (clamp(m.x, b.x, b.x + b.w) - m.x) ** 2 + (clamp(m.y, b.y, b.y + b.h) - m.y) ** 2 < d * d;
    const hides = (b, own) => (counts || []).some((m) => !(own && m.x === own.x && m.y === own.y) && near(m, b, 9));
    const covers = (b, own) => obstacles.filter((m) => m !== own && near(m, b, m.r + 1)).length;
    let out = "", seen = 0;
    for (const it of list) {
      if (boxes.length >= most) { break; }
      if (it.x < 0 || it.y < 0 || it.x > w0 || it.y > h0) { continue; }
      seen += 1;
      const w = Math.max(it.name.length * 7.1, it.sub.length * 6.2) + 4, h = 30, r = it.r;
      const tries = [[it.x + r + 5, it.y - 13, "start", it.x + r + 5], [it.x - r - 5 - w, it.y - 13, "end", it.x - r - 5],
        [it.x - w / 2, it.y + r + 3, "middle", it.x], [it.x - w / 2, it.y - r - 33, "middle", it.x]];
      let pick = null;
      tries.forEach((t, j) => {
        const b = {x: t[0], y: t[1], w: w, h: h};
        if (!fits(b) || crowds(b) || hides(b, it)) { return; }
        const c = covers(b, it);
        if (!pick || c < pick.c) { pick = {c: c, b: b, t: t, j: j}; }
      });
      if (!pick || (pick.c && seen > lead)) { continue; }
      boxes.push(pick.b);
      const tx = (v.x + pick.t[3] / s).toFixed(2);
      out += "<text x='" + tx + "' y='" + (v.y + (pick.b.y + 12) / s).toFixed(2) + "' text-anchor='" + pick.t[2] + "' class='nm'>" + esc(it.name) + "</text>" +
        "<text x='" + tx + "' y='" + (v.y + (pick.b.y + 26) / s).toFixed(2) + "' text-anchor='" + pick.t[2] + "' class='lsub'>" + esc(it.sub) + "</text>";
    }
    return out;
  }
  function renderMarks() {
    const view = doc.getElementById("v-map"), svg = $(".map", view);
    if (!svg) { return; }
    const v = viewRect(), s = v.s, k = 1 / s, ox = v.x * s, oy = v.y * s, w0 = v.w * s, h0 = v.h * s;
    const gs = groupsAt(s);
    const shown = BY[st.hover] || BY[st.fp] || null;
    const picked = st.ring ? new Set(st.ring.slugs) : null;
    let rings = "";
    const items = [];
    gs.slice().sort((a, b) => ringR(b) - ringR(a)).forEach((g) => {
      const px = g.x - ox, py = g.y - oy, R = ringR(g);
      if (px < -R - 40 || py < -R - 40 || px > w0 + R + 40 || py > h0 + R + 40) { return; }
      const mine = !!(picked && g.members.some((a) => picked.has(a.slug)));
      rings += ringSvg(g, s, !!((picked && !mine) || shown), mine);
      items.push({x: px, y: py, r: R + 1, g: g, mine: mine});
    });
    $(".map .marks", view).innerHTML = rings;
    /* The picked account's footprint: a solid dot at every US city its postings name, sized by its open roles there,
       with a caption on the map that says what the dots are. */
    let foot = "";
    const spots = [], fp = shown ? (shown.fp || []) : [];
    fp.forEach((row) => {
      const c = AS.fpc[row[0]], n = row[1], R = 2.6 + 1.5 * Math.sqrt(n);
      foot += "<circle class='fp' cx='" + c[2] + "' cy='" + c[3] + "' r='" + (R * k).toFixed(3) + "' stroke-width='" +
        (1.2 * k).toFixed(3) + "'/>";
      spots.push({x: c[2] * s - ox, y: c[3] * s - oy, r: R, name: c[0], sub: n === 1 ? W["fp.role"] : fill(W["fp.roles"], {n: n})});
    });
    $(".map .foot", view).innerHTML = foot;
    const cap = doc.getElementById("fpcap");
    if (cap) {
      cap.hidden = !fp.length;
      cap.textContent = !fp.length ? "" : fp.length === 1 ? fill(W["fp.caption1"], {name: shown.name, city: AS.fpc[fp[0][0]][0]}) :
        fill(W["fp.caption"], {name: shown.name, n: fp.length});
    }
    const labels = $(".map .labels", view);
    if (st.zooming) { labels.innerHTML = ""; return; }
    const most = Math.min(12, Math.round(7 + 2 * Math.log2(st.zoom.k)));
    const counts = items.filter((it) => it.g.members.length > 1).map((it) => ({x: it.x, y: it.y}));
    if (shown) {
      labels.innerHTML = labelsSvg(spots, spots.concat(items), v, most, 3, counts, fp.length ? 40 : 4);
      return;
    }
    const list = items.slice().sort((a, b) => (b.mine - a.mine) || (a.g.members[0].rank - b.g.members[0].rank)).map((it) => {
      const g = it.g, n = g.members.length, best = g.members[0];
      return {x: it.x, y: it.y, r: it.r, name: best.name,
        sub: n === 1 ? best.hub[0] + " · " + f1(best.r.score) : placeName(g) + " · " + fill(W["ring.count"], {n: n})};
    });
    labels.innerHTML = labelsSvg(list, list, v, most, st.zoom.k < 1.5 ? 5 : 3, counts, 4);
  }
  const ICON = {in: "<path d='M8 3v10M3 8h10'/>", out: "<path d='M3 8h10'/>", reset: "<path d='M3 6V3h3M10 3h3v3M13 10v3h-3M6 13H3v-3'/>"};
  function renderMap() {
    const view = doc.getElementById("v-map");
    const nA = ranked.filter((a) => a.r.tier === "A").length;
    const states = {};
    ranked.forEach((a) => { if (a.hub) { states[a.hub[1]] = 1; } });
    const f = frame();
    const chips = ["all"].concat(Object.keys(AS.model.routing.regions), ["tierA"]).map((r) =>
      "<button type='button' class='chip" + (st.region === r ? " on" : "") + "' data-region='" + esc(r) + "'>" +
      esc(r === "all" ? W["chip.all"] : r === "tierA" ? W["chip.tierA"] : r) + "</button>").join("");
    const remote = ranked.filter((a) => !a.hub);
    const key = ["A", "B", "C", "D"].map((t) => "<span><i class='k" + t + "'></i>" + esc(fill(W["key.tier"], {t: t})) + "</span>").join("") +
      "<span><i class='kring'></i>" + esc(W["key.ring"]) + "</span><span><i class='ktop'></i>" + esc(W["key.top"]) + "</span>";
    const zoom = "<div class='zoom' role='group' aria-label='" + esc(W["zoom.group"]) + "'>" + ["in", "out", "reset"].map((k) =>
      "<button type='button' data-zoom='" + k + "' aria-label='" + esc(W["zoom." + k]) + "' title='" + esc(W["zoom." + k]) + "'><svg viewBox='0 0 16 16' aria-hidden='true'>" +
      ICON[k] + "</svg></button>").join("") + "</div>";
    view.innerHTML = "<div class='mapview'><div class='mapwrap'>" +
      "<div class='mh'><h1>" + esc(W["map.title"]) + "</h1><span class='sub'>" + esc(fill(W["map.sub"], {n: n0(ranked.length), a: nA})) + "</span></div>" +
      "<div class='chips' role='group'>" + chips + "</div>" +
      "<div class='mapbox'><svg class='map' viewBox='" + f.x + " " + f.y + " " + f.w + " " + f.h +
      "' role='img' aria-label='" + esc(W["map.aria"]) + "'><g class='states'>" +
      AS.map.states.map((s) => "<path class='st" + (states[s.code] ? " on" : "") + "' d='" + s.d + "'><title>" + esc(s.name) + "</title></path>").join("") +
      "</g><path class='nation' d='" + AS.map.nation + "'/><g class='marks'></g><g class='foot'></g><g class='labels'></g></svg>" +
      "<div class='maptip' id='maptip' hidden></div><div class='fpcap' id='fpcap' hidden></div>" + zoom + "</div>" +
      "<div class='mapfoot'><div class='left'><div class='key'>" + key + "</div>" +
      (remote.length ? "<div class='tray'><b>" + esc(W["remote.title"]) + "</b><span>" + esc(fill(W["remote.text"], {n: remote.length})) + "</span>" +
        remote.slice(0, 3).map((a) => "<button type='button' class='chip' data-pick='" + a.slug + "'>" + esc(a.name) + "</button>").join("") +
        "<a href='#/list' data-go='list' data-list-region='" + esc(AS.model.routing.remote_region) + "'>" + esc(W["remote.more"]) + "</a></div>" : "") +
      "</div><div class='why' id='why'></div></div>" +
      "</div><aside class='side' id='side'></aside></div>";
    st.drawn = true;
    renderSide();
    applyView();
    watchBox();
  }
  /* The map's box settles after the rest of the view fills in and changes with the window, and the view box follows it. */
  let boxWatch = null;
  function watchBox() {
    if (boxWatch) { boxWatch.disconnect(); boxWatch = null; }
    const svg = $(".map", doc.getElementById("v-map"));
    if (!svg || !window.ResizeObserver) { return; }
    let last = "";
    boxWatch = new window.ResizeObserver(() => {
      const r = svg.getBoundingClientRect(), size = Math.round(r.width) + "x" + Math.round(r.height);
      if (size !== last) { last = size; applyView(); }
    });
    boxWatch.observe(svg);
  }
  /* Picking: a ring lists its accounts beside the map, a dot picks its account and lights up every city it hires in, and
     the map's empty space clears both. */
  function pickMark(id) {
    const g = marks.find((m) => m.members[0].slug === id);
    if (!g) { return; }
    if (g.members.length === 1) {
      st.ring = null;
      st.fp = id;
      select(id);
      renderMarks();
      return;
    }
    st.fp = null;
    st.hover = null;
    st.ring = {slugs: g.members.map((a) => a.slug), title: placeName(g)};
    renderSide();
    renderMarks();
  }
  function clearPick() {
    if (!st.ring && !st.fp) { return; }
    st.ring = null;
    st.fp = null;
    renderSide();
    renderMarks();
  }
  function fpText(a) {
    const fp = a.fp || [];
    if (!fp.length) { return W["fp.none"]; }
    if (fp.length === 1) { return fill(W["fp.one"], {city: AS.fpc[fp[0][0]][0]}); }
    const parts = fp.slice(0, 3).map((r) => AS.fpc[r[0]][0] + " (" + r[1] + ")");
    const list = parts.length === 2 ? parts.join(" " + W["fp.and"] + " ") : parts.slice(0, -1).join(", ") + ", " + W["fp.and"] + " " + parts[parts.length - 1];
    return fill(W["fp.many"], {n: fp.length, list: list});
  }

  /* Zoom: a center and a zoom over the frame's fit to its box. The view box takes the box's own shape, so the whole
     frame shows at zoom 1 and nothing stretches. */
  const ZMAX = 16;
  const frame = () => ({x: AS.map.x || 0, y: 0, w: AS.map.width, h: AS.map.height});
  function mapBox() {
    const svg = $(".map", doc.getElementById("v-map"));
    const r = svg && svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
    return r && r.width && r.height ? r : null;
  }
  function viewRect() {
    const f = frame(), z = st.zoom, r = mapBox();
    const bw = r ? r.width : f.w, bh = r ? r.height : f.h;
    const base = Math.min(bw / f.w, bh / f.h), s = base * z.k, w = bw / s, h = bh / s;
    const mid = (want, lo, span, size) => (size >= span ? lo + span / 2 : Math.min(lo + span - size / 2, Math.max(lo + size / 2, want == null ? lo + span / 2 : want)));
    z.cx = mid(z.cx, f.x, f.w, w);
    z.cy = mid(z.cy, f.y, f.h, h);
    return {x: z.cx - w / 2, y: z.cy - h / 2, w: w, h: h, s: s, base: base};
  }
  function applyView() {
    const view = doc.getElementById("v-map"), svg = $(".map", view);
    if (!svg) { return; }
    const v = viewRect(), z = st.zoom;
    svg.setAttribute("viewBox", v.x.toFixed(1) + " " + v.y.toFixed(1) + " " + v.w.toFixed(1) + " " + v.h.toFixed(1));
    svg.classList.toggle("zoomed", z.k > 1.001);
    if (svg.style && svg.style.setProperty) { svg.style.setProperty("--ls", (1 / v.s).toFixed(5)); }
    const off = {in: z.k >= ZMAX - 0.001, out: z.k <= 1.001, reset: z.k <= 1.001};
    $$("[data-zoom]", view).forEach((b) => { b.disabled = off[b.getAttribute("data-zoom")]; });
    renderMarks();
  }
  let settleTimer = 0;
  function settle() {
    window.clearTimeout(settleTimer);
    settleTimer = later(() => { st.zooming = false; renderMarks(); }, 160);
  }
  function startZoom() {
    st.zooming = true;
    const tip = doc.getElementById("maptip");
    if (tip) { tip.hidden = true; }
    applyView();
    settle();
  }
  /* Zooms to k keeping the point (px, py) where it is on the screen, or centering on it when asked. */
  function zoomTo(k, px, py, center) {
    const z = st.zoom, v = viewRect();
    const nk = Math.max(1, Math.min(ZMAX, k));
    if (Math.abs(nk - z.k) < 1e-6 && !center) { return; }
    if (px == null) { px = v.x + v.w / 2; py = v.y + v.h / 2; }
    const f = z.k / nk;
    z.cx = center ? px : px - (px - (v.x + v.w / 2)) * f;
    z.cy = center ? py : py - (py - (v.y + v.h / 2)) * f;
    z.k = nk;
    startZoom();
  }
  function resetZoom() {
    if (st.zoom.k <= 1.001) { return; }
    st.zoom = {k: 1, cx: null, cy: null};
    startZoom();
  }
  /* A region's chip zooms to its accounts, up to four times. */
  function fitTo(list) {
    const on = list.filter((a) => a.hub);
    if (!on.length) { st.zoom = {k: 1, cx: null, cy: null}; return; }
    const xs = on.map((a) => a.hub[2]), ys = on.map((a) => a.hub[3]);
    const x0 = Math.min.apply(null, xs) - 40, x1 = Math.max.apply(null, xs) + 40, y0 = Math.min.apply(null, ys) - 40, y1 = Math.max.apply(null, ys) + 40;
    const f = frame(), r = mapBox(), bw = r ? r.width : f.w, bh = r ? r.height : f.h, base = Math.min(bw / f.w, bh / f.h);
    const k = Math.max(1, Math.min(4, bw / (base * (x1 - x0)), bh / (base * (y1 - y0))));
    st.zoom = {k: k, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2};
  }
  /* Dragging pans and two fingers pinch. A plain click still picks a ring, since nothing captures the pointer until it
     moves. */
  const ptrs = new Map();
  let gest = null;
  const mapSvg = (t) => (t && t.closest ? t.closest(".mapbox svg.map") : null);
  function svgPoint(x, y) {
    const r = mapBox(), v = viewRect();
    return r ? {x: v.x + (x - r.left) / v.s, y: v.y + (y - r.top) / v.s} : {x: v.x + v.w / 2, y: v.y + v.h / 2};
  }
  const middle = (pts) => (pts.length > 1 ? {x: (pts[0].x + pts[1].x) / 2, y: (pts[0].y + pts[1].y) / 2} : {x: pts[0].x, y: pts[0].y});
  const spread = (pts) => (pts.length > 1 ? Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) : 0);
  function gestStart() {
    const pts = Array.from(ptrs.values());
    if (!pts.length) { gest = null; return; }
    const mid = middle(pts);
    gest = {mid: mid, dist: spread(pts), k: st.zoom.k, p: svgPoint(mid.x, mid.y), moved: !!(gest && gest.moved)};
  }
  function onDown(ev) {
    const svg = mapSvg(ev.target);
    if (!svg || (ev.pointerType === "mouse" && ev.button !== 0)) { return; }
    ptrs.set(ev.pointerId, {x: ev.clientX, y: ev.clientY, el: svg});
    gestStart();
  }
  function onMove(ev) {
    if (!gest || !ptrs.has(ev.pointerId)) { return; }
    const me = ptrs.get(ev.pointerId);
    me.x = ev.clientX; me.y = ev.clientY;
    const pts = Array.from(ptrs.values()), r = mapBox();
    if (!r) { return; }
    const mid = middle(pts);
    if (!gest.moved) {
      if (pts.length < 2 && Math.hypot(mid.x - gest.mid.x, mid.y - gest.mid.y) < 5) { return; }
      gest.moved = true;
      if (me.el.setPointerCapture) { try { me.el.setPointerCapture(ev.pointerId); } catch (e) { /* the pointer already left */ } }
      me.el.classList.add("dragging");
      const tip = doc.getElementById("maptip");
      if (tip) { tip.hidden = true; }
    }
    const was = st.zoom.k;
    const k = pts.length > 1 && gest.dist ? Math.max(1, Math.min(ZMAX, gest.k * spread(pts) / gest.dist)) : gest.k;
    const s = viewRect().base * k;
    st.zoom.k = k;
    st.zoom.cx = gest.p.x - (mid.x - r.left) / s + r.width / (2 * s);
    st.zoom.cy = gest.p.y - (mid.y - r.top) / s + r.height / (2 * s);
    if (Math.abs(k - was) > 1e-6) { st.zooming = true; applyView(); settle(); } else { applyView(); }
  }
  function onUp(ev) {
    if (!ptrs.has(ev.pointerId)) { return; }
    const el = ptrs.get(ev.pointerId).el;
    ptrs.delete(ev.pointerId);
    if (ptrs.size) { gestStart(); return; }
    const moved = !!(gest && gest.moved);
    gest = null;
    el.classList.remove("dragging");
    if (moved) { st.dragged = Date.now(); }
  }
  function onWheel(ev) {
    if (!mapSvg(ev.target)) { return; }
    ev.preventDefault();
    const unit = ev.deltaMode === 1 ? 16 : ev.deltaMode === 2 ? 400 : 1;
    const p = svgPoint(ev.clientX, ev.clientY);
    zoomTo(st.zoom.k * Math.exp(-ev.deltaY * unit * (ev.ctrlKey ? 0.01 : 0.002)), p.x, p.y);
  }
  function onDbl(ev) {
    if (!mapSvg(ev.target)) { return; }
    if (ev.preventDefault) { ev.preventDefault(); }
    const p = svgPoint(ev.clientX, ev.clientY);
    zoomTo(st.zoom.k * 2, p.x, p.y);
  }
  /* New weights move scores and tiers, so the rings group again. */
  function repackMap() {
    const view = doc.getElementById("v-map");
    if (!$(".map", view)) { renderMap(); return; }
    st.ver += 1;
    renderMarks();
    const sub = $(".mh .sub", view);
    if (sub) { sub.textContent = fill(W["map.sub"], {n: n0(ranked.length), a: ranked.filter((a) => a.r.tier === "A").length}); }
    renderSide();
  }
  function renderSide() {
    const side = doc.getElementById("side");
    if (!side) { return; }
    const a = current();
    const ring = st.ring ? st.ring.slugs.map((x) => BY[x]).filter(Boolean).sort((p, q) => p.rank - q.rank) : null;
    const top = ring || ranked.filter(inRegion).slice(0, 10);
    /* Every row opens its account, and pointing at one lights up every city it hires in. */
    const rows = top.map((x) => "<a class='acct" + (a && x.slug === a.slug ? " sel" : "") + "' href='#/a/" + x.slug + "' data-go data-slug='" + x.slug +
      "' data-fp='" + x.slug + "'><span class='r'>" + x.rank + "</span><span class='n'><b>" + esc(x.name) + "</b><span>" +
      esc(x.segment + " · " + (x.hub ? x.hub[0] : W["acct.nohub"])) + "</span></span>" +
      "<span class='bar'><i class='w" + Math.round(x.r.score) + "'></i></span>" + tierTag(x.r.tier) + "</a>").join("");
    const head = ring ? "<div class='sidehead'><h3>" + esc(st.ring.title + " · " + fill(W["ring.count"], {n: ring.length})) + "</h3>" +
      "<button type='button' class='back' data-ring-back>" + esc(W["side.back"]) + "</button></div>" : "<h3>" + esc(W["side.top"]) + "</h3>";
    side.innerHTML = head + "<div class='toplist scroll'>" + (rows || "<p class='empty'>" + esc(W["side.empty"]) + "</p>") + "</div>" +
      (a ? cardHtml(a) : "");
    $$(".bar i", side).forEach((i) => { i.style.width = i.getAttribute("class").slice(1) + "%"; });
    const why = doc.getElementById("why");
    const lead = ranked.filter(inRegion)[0];
    if (why && lead) { why.innerHTML = "<b>" + esc(fill(W["why.title"], {name: lead.name})) + "</b>" + esc(whyText(lead)) + "<small>" + esc(W["why.note"]) + "</small>"; }
  }
  function cardHtml(a) {
    const b = briefOf(a);
    let body;
    if (b && b.brief) {
      const first = (b.brief.why_now || [])[0];
      body = (first ? "<p><span class='lbl'>" + esc(W["card.why"]) + ".</span> " + cites(first.text) + "</p>" : "") +
        "<p><span class='lbl'>" + esc(W["card.priority"]) + "</span> <span class='inf'>(" + esc(W["card.inference"]) + ")</span> " +
        cites((b.brief.priority || {}).text || "") + "</p><p>" + verdictTag(b) + "</p>";
    } else {
      body = "<p>" + esc(fill(W["card.nobrief"], {n: NB})) + "</p>";
    }
    return "<div class='card scroll' id='card'><div class='h'><b>" + esc(a.name) + "</b><span class='mono'>" + f1(a.r.score) + " · " +
      esc(fill(W["score.tier"], {t: a.r.tier})) + "</span></div>" + body + "<p class='fpline' data-fp='" + a.slug + "'>" + esc(fpText(a)) + "</p>" +
      "<div class='acts'><a class='btn pri' href='#/a/" + a.slug + "' data-go>" + esc(W["card.open"]) + "</a>" +
      "<a class='btn' href='#/a/" + a.slug + "/score' data-go>" + esc(W["card.score"]) + "</a></div></div>";
  }

  /* An account and its score share a header */
  function headHtml(a, tab) {
    return "<div class='ahead'><a class='backl' href='#/map' data-go>" + esc(W.back) + "</a><div><h1>" + esc(a.name) + "</h1>" +
      "<div class='facts'>" + esc([a.segment, rolesText(a), hubText(a)].join(" · ")) + " · <a href='" + esc(a.board) + "' rel='noopener'>" + esc(W["acct.board"]) + "</a></div>" +
      "<div class='routeline'>" + esc(routeText(a)) + "</div></div>" +
      "<div class='bignum'><span class='mono'>" + f1(a.r.score) + "</span>" + tierTag(a.r.tier) +
      "<small>" + esc(W["score.fit"] + " " + f1(a.r.fit) + " · " + W["score.intent"] + " " + f1(a.r.intent)) + "</small></div></div>" +
      "<nav class='vtabs'><a href='#/a/" + a.slug + "' data-go class='" + (tab === "brief" ? "on" : "") + "'>" + esc(W.tabs.brief) + "</a>" +
      "<a href='#/a/" + a.slug + "/score' data-go class='" + (tab === "score" ? "on" : "") + "'>" + esc(W.tabs.score) + "</a></nav>";
  }
  function touchKey(a, b) { return a.slug + "|" + b.model; }
  function touchState(a, b) {
    const k = touchKey(a, b);
    if (!st.touch[k]) {
      const t = b.brief.first_touch || {};
      st.touch[k] = {subject: t.subject || "", body: t.body || "", cites: (t.cites || []).slice(), edit: false, status: ""};
    }
    return st.touch[k];
  }
  function touchProblems(a, b) {
    const t = touchState(a, b);
    if (!C) { return []; }
    return C.checkTouch({subject: t.subject, body: t.body, cites: t.cites}, AS.sources[a.name] || {}, a.name, READ_ON,
      AS.tools, FIRST);
  }
  function checksHtml(problems) {
    if (!problems.length) { return "<div class='checks ok' id='checks'>" + esc(W["touch.clean"]) + "</div>"; }
    return "<div class='checks' id='checks'>" + esc(problems.length === 1 ? W["touch.flagOne"] : fill(W["touch.flagMany"], {n: problems.length})) +
      "<ul>" + problems.map((p) => "<li>" + esc(p) + "</li>").join("") + "</ul></div>";
  }
  function touchHtml(a, b) {
    const t = touchState(a, b), problems = touchProblems(a, b);
    const ro = t.edit ? "" : " readonly";
    const status = "<div id='tstatus'>" + (t.status === "approved" ? "<p class='status ok'>" + esc(W["touch.approved"]) + "</p>" :
      t.status === "rejected" ? "<p class='status no'>" + esc(W["touch.rejected"]) + "</p>" : "") + "</div>";
    return "<section class='touch' id='touch'><div class='th'><h3>" + esc(W["touch.title"]) + "</h3><span>" +
      t.cites.map((c) => "<span class='cite' data-c='" + c + "'>" + c + "</span>").join("") + "</span></div>" +
      "<p class='seller'>" + esc(W["touch.seller"]) + "</p>" +
      "<label for='t-subject'>" + esc(W["touch.subject"]) + "</label><input id='t-subject' data-touch-field='subject' value='" + esc(t.subject) + "'" + ro + ">" +
      "<label for='t-body'>" + esc(W["touch.body"]) + "</label><textarea id='t-body' data-touch-field='body'" + ro + ">" + esc(t.body) + "</textarea>" +
      checksHtml(problems) +
      "<div class='acts'><button type='button' class='btn pri' data-touch='approve'" + (problems.length ? " disabled" : "") + ">" + esc(W["touch.approve"]) + "</button>" +
      "<button type='button' class='btn' data-touch='edit' aria-pressed='" + (t.edit ? "true" : "false") + "'>" + esc(t.edit ? W["touch.done"] : W["touch.edit"]) + "</button>" +
      "<button type='button' class='btn' data-touch='reject'>" + esc(W["touch.reject"]) + "</button>" +
      "<button type='button' class='btn' data-touch='reset'>" + esc(W["touch.reset"]) + "</button></div>" + status +
      "<p class='note'>" + esc(W["touch.note"]) + "</p></section>";
  }
  function readHtml(b) {
    const r = readState(b);
    let parts = "", reasons = "";
    if (b.read) {
      const judges = Object.keys(b.read.judges);
      PARTS.forEach((p) => {
        const vs = judges.map((j) => (b.read.judges[j].parts[p] || [])[0]).filter(Boolean);
        if (!vs.length) { return; }
        parts += "<span class='part'>" + esc((W.part || {})[p] || p) + vs.map((v) => "<i class='" + (v === "holds up" ? "ok" : v === "wrong" ? "bad" : "warn") + "'></i>").join("") + "</span>";
        reasons += "<dt>" + esc((W.part || {})[p] || p) + "</dt><dd>" + judges.map((j) => {
          const pr = b.read.judges[j].parts[p];
          return pr ? "<div>" + esc(b.read.judges[j].label) + " <span>" + esc((W.verdict || {})[pr[0]] || pr[0]) + "</span>. " + esc(pr[1]) + "</div>" : "";
        }).join("") + "</dd>";
      });
    }
    return "<section class='read' id='read'><div class='rh'><h3>" + esc(W["read.title"]) + "</h3><span class='verdict " + r.cls + "'>" + esc(r.text) + "</span></div>" +
      (parts ? "<div class='parts'>" + parts + "</div>" : "") + "<p>" + esc(W["read.note"]) + "</p>" +
      (reasons ? "<details><summary>" + esc(W["read.reasons"]) + "</summary><dl>" + reasons + "</dl></details>" : "") + "</section>";
  }
  function sourcesHtml(a) {
    const src = AS.sources[a.name] || {};
    const counted = {};
    a.r.intent_rows.forEach((row) => { counted[row.sid] = row.points; });
    const seen = {};
    const keys = Object.keys(src).map(Number).sort((x, y) => x - y);
    return "<section class='sources' id='sources'><h3>" + esc(W["src.title"]) + "</h3><p>" + esc(W["src.note"]) + "</p>" + keys.map((k) => {
      const s = src[k];
      if (s.kind === "board") {
        return "<div class='src' data-src='0'><span class='cite'>0</span><b>" + esc(W["src.board"]) + "</b><span class='meta'>" + esc(s.text) + "</span></div>";
      }
      const sig = s.row == null ? null : SIG[s.row];
      const same = s.posting_id && seen[s.posting_id] != null ? " · " + fill(W["src.same"], {k: seen[s.posting_id]}) : "";
      if (s.posting_id && seen[s.posting_id] == null) { seen[s.posting_id] = k; }
      const pts = sig && counted[sig.sid] != null ? "<span class='pts' title='" + esc(W["src.counts"]) + "'>+" + f1(counted[sig.sid]) + "</span>" : "";
      const quote = s.excerpt && s.excerpt !== s.title ? "<q>" + esc(s.excerpt) + "</q>" : "";
      return "<div class='src' data-src='" + k + "'><span class='cite'>" + k + "</span>" + pts + "<b>" + esc(s.title) + "</b>" + quote +
        "<span class='meta'>" + esc([famLabel(s.family), s.posted ? s.posted + " · " + whenText(sig || {age: s.posted ? READ_DAY - S.dayNumber(s.posted) : null, kind: "published"}) : whenText({age: null})].join(" · ")) + esc(same) +
        (sig ? " · <a href='" + esc(sig.url) + "' rel='noopener'>" + esc(W["src.open"]) + "</a>" : "") + "</span></div>";
    }).join("") + "</section>";
  }
  function renderAccount() {
    const view = doc.getElementById("v-account");
    const a = current();
    if (!a) { view.innerHTML = ""; return; }
    const b = briefOf(a);
    let left;
    if (!b || !b.brief) {
      left = "<div class='brief'><p class='empty'>" + esc(fill(W["brief.none"], {n: NB})) + "</p></div>";
    } else {
      const list = modelsOf(a);
      const sw = "<div class='models'><span class='lbl'>" + esc(W["models.title"]) + "</span>" + list.map((m) =>
        "<button type='button' data-model='" + esc(m.model) + "' aria-pressed='" + (m.model === b.model ? "true" : "false") + "'>" + esc(m.label) +
        (m.model === AS.meta.route ? "<em>" + esc(W["models.routed"]) + "</em>" : "") + "</button>").join("") + "</div>";
      const how = b.needs_review ? W["models.review"] : b.repaired ? W["models.repaired"] : W["models.first"];
      const stat = "<p class='mstat'>" + esc(how + " · " + fill(W["models.cost"], {cost: "$" + Number(b.cost || 0).toFixed(4), secs: Math.round((b.ms || 0) / 1000)})) +
        (b.model === AS.meta.route ? ". " + esc(W["models.routedNote"]) : "") + "</p>";
      const review = b.needs_review ? "<div class='review'><b>" + esc(W["review.title"]) + "</b>. " + esc(W["review.text"]) + "<ul>" +
        b.flags.rows.map((f) => "<li>" + esc(f.text) + " (" + esc(f.problems.join("; ")) + ")</li>").join("") +
        b.flags.problems.map((p) => "<li>" + esc(p) + "</li>").join("") + "</ul></div>" : "";
      const why = (b.brief.why_now || []).map((s, i) => "<p class='sent' tabindex='0' data-i='w" + i + "'>" + cites(s.text) + "</p>").join("");
      const pr = b.brief.priority || {};
      left = "<div class='brief' id='brief'>" + sw + stat + review + readHtml(b) +
        "<section class='whynow'><h3>" + esc(W["brief.why"]) + "</h3><p class='hint'>" + esc(W["brief.hint"]) + "</p>" + why + "</section>" +
        "<section class='priority'><h3>" + esc(W["brief.priority"]) + " <span class='inf'>(" + esc(W["brief.inference"]) + ")</span></h3>" +
        "<p class='sent' tabindex='0' data-i='p'>" + cites(pr.text || "") + "</p></section>" +
        "<section><h3>" + esc(W["brief.questions"]) + "</h3><ul>" + (b.brief.questions || []).map((q) => "<li>" + esc(q) + "</li>").join("") + "</ul></section>" +
        "<section><h3>" + esc(W["brief.unknowns"]) + "</h3><ul>" + (b.brief.unknowns || []).map((q) => "<li>" + esc(q) + "</li>").join("") + "</ul></section>" +
        touchHtml(a, b) + "</div>";
    }
    st.hl = null;
    view.innerHTML = headHtml(a, "brief") + "<div class='acctbody' id='acctbody'><svg class='threads' aria-hidden='true'></svg>" + left +
      (AS.sources[a.name] ? sourcesHtml(a) : signalsHtml(a)) + "</div>";
    later(drawThreads, 30);
  }
  function signalsHtml(a) {
    const rows = a.r.intent_rows.slice().sort((x, y) => y.points - x.points);
    return "<section class='sources' id='sources'><h3>" + esc(W["src.title"]) + "</h3>" + rows.map((row, i) => {
      const s = SIG[row.sid];
      return "<div class='src'><span class='cite'>" + (i + 1) + "</span><span class='pts'>+" + f1(row.points) + "</span><b>" + esc(s.title) + "</b>" +
        (s.quote ? "<q>" + esc(s.quote) + "</q>" : "") + "<span class='meta'>" + esc(famLabel(s.family) + " · " + whenText(s)) +
        " · <a href='" + esc(s.url) + "' rel='noopener'>" + esc(W["src.open"]) + "</a></span></div>";
    }).join("") + "</section>";
  }
  function drawThreads() {
    const body = doc.getElementById("acctbody");
    const svg = body && $("svg.threads", body);
    if (!svg || !body.getBoundingClientRect) { return; }
    const box = body.getBoundingClientRect();
    /* A thread leaves from the brief's edge at its chip's line and crosses only the gutter, never the text. */
    const brief = $(".brief", body);
    const edge = brief && brief.getBoundingClientRect ? brief.getBoundingClientRect().right - box.left + 2 : null;
    let paths = "";
    $$(".brief .cite[data-c]", body).forEach((chip) => {
      const k = chip.getAttribute("data-c");
      const row = $(".sources .src[data-src='" + k + "'] .cite", body);
      if (!row) { return; }
      const p = chip.getBoundingClientRect(), q = row.getBoundingClientRect();
      const x1 = edge != null && edge > 0 ? edge : p.right - box.left, y1 = p.top + p.height / 2 - box.top, x2 = q.left - box.left - 2, y2 = q.top + q.height / 2 - box.top;
      const dx = Math.max(24, (x2 - x1) * 0.45);
      const sent = chip.closest ? chip.closest("[data-i]") : null;
      paths += "<path data-k='" + k + "' data-s='" + (sent ? sent.getAttribute("data-i") : "touch") + "' d='M" + x1.toFixed(1) + " " + y1.toFixed(1) +
        "C" + (x1 + dx).toFixed(1) + " " + y1.toFixed(1) + " " + (x2 - dx).toFixed(1) + " " + y2.toFixed(1) + " " + x2.toFixed(1) + " " + y2.toFixed(1) + "'/>";
    });
    svg.setAttribute("viewBox", "0 0 " + Math.max(1, box.width).toFixed(0) + " " + Math.max(1, box.height).toFixed(0));
    svg.innerHTML = paths;
    if (st.hl && (st.hl[0] || st.hl[1] != null)) { highlight(st.hl[0], st.hl[1]); }
  }
  function highlight(sentId, srcKey) {
    st.hl = [sentId, srcKey];
    const body = doc.getElementById("acctbody");
    if (!body) { return; }
    $$(".hot", body).forEach((el) => el.classList.remove("hot"));
    const svg = $("svg.threads", body);
    if (!sentId && srcKey == null) { if (svg) { svg.classList.remove("focus"); } return; }
    let keys = [], sents = [];
    if (sentId) {
      const s = $("[data-i='" + sentId + "']", body);
      if (s) { sents = [s]; keys = $$(".cite[data-c]", s).map((c) => c.getAttribute("data-c")); }
      if (sentId === "touch") { keys = $$(".touch .cite[data-c]", body).map((c) => c.getAttribute("data-c")); }
    } else {
      keys = [String(srcKey)];
      sents = $$(".brief [data-i]", body).filter((s) => $$(".cite[data-c]", s).some((c) => c.getAttribute("data-c") === String(srcKey)));
    }
    sents.forEach((s) => s.classList.add("hot"));
    keys.forEach((k) => {
      const row = $(".sources .src[data-src='" + k + "']", body);
      if (row) { row.classList.add("hot"); }
      $$(".brief .cite[data-c='" + k + "']", body).forEach((c) => { if (!sentId || sents.indexOf(c.closest("[data-i]")) >= 0 || sentId === "touch") { c.classList.add("hot"); } });
    });
    $$("path", svg).forEach((p) => {
      const on = keys.indexOf(p.getAttribute("data-k")) >= 0 && (!sentId || p.getAttribute("data-s") === sentId);
      if (on) { p.classList.add("hot"); }
    });
    if (svg) { svg.classList.add("focus"); }
  }

  /* The score: the chart, every row's arithmetic, the route and the weights */
  function chartHtml(a) {
    const hist = S.history(a, a.list, AS.model, opts());
    const Wd = st.chartW || 960, H = 230, L = 34, Rr = 12, T = 10, B = 26, n = hist.length;
    const x = (i) => L + (n > 1 ? i / (n - 1) : 0) * (Wd - L - Rr);
    const y = (v) => T + (1 - Math.min(100, Math.max(0, v)) / 100) * (H - T - B);
    let grid = "";
    [0, 25, 50, 75, 100].forEach((v) => {
      grid += "<line x1='" + L + "' x2='" + (Wd - Rr) + "' y1='" + y(v).toFixed(1) + "' y2='" + y(v).toFixed(1) + "'/>";
    });
    let axis = [0, 25, 50, 75, 100].map((v) => "<text x='" + (L - 6) + "' y='" + (y(v) + 4).toFixed(1) + "' text-anchor='end'>" + v + "</text>").join("");
    hist.forEach((h, i) => {
      if (h[0].slice(8) === "01") { axis += "<text x='" + x(i).toFixed(1) + "' y='" + (H - 6) + "' text-anchor='middle'>" + esc((MONTHS[Number(h[0].slice(5, 7)) - 1] || "").slice(0, 3)) + "</text>"; }
    });
    const line = (k) => hist.map((h, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(h[k]).toFixed(1)).join("");
    const area = line(2) + "L" + x(n - 1).toFixed(1) + " " + y(0).toFixed(1) + "L" + x(0).toFixed(1) + " " + y(0).toFixed(1) + "Z";
    const dots = a.r.intent_rows.map((row) => {
      const s = SIG[row.sid];
      if (s.age == null || s.age >= n) { return ""; }
      const i = n - 1 - s.age;
      return "<circle class='dot' r='3.5' cx='" + x(i).toFixed(1) + "' cy='" + y(hist[i][2]).toFixed(1) + "'><title>" + esc(s.title + " · " + s.posted) + "</title></circle>";
    }).join("");
    return "<div class='chart' id='chart'><h3>" + esc(fill(W["score.chart"], {days: n})) + "</h3><svg viewBox='0 0 " + Wd + " " + H + "' role='img' aria-label='" +
      esc(fill(W["score.chart"], {days: n})) + "'><g class='grid'>" + grid + "</g><path class='area' d='" + area + "'/><path class='lintent' d='" + line(1) + "'/>" +
      "<path class='lscore' d='" + line(2) + "'/>" + dots + "<g class='axis'>" + axis + "</g></svg>" +
      "<div class='legend'><span><i></i>" + esc(W["score.total"]) + "</span><span><i class='dash'></i>" + esc(W["score.intent"]) + "</span></div>" +
      "<p>" + esc(W["score.chartNote"]) + "</p></div>";
  }
  function rowsHtml(a) {
    const f = AS.model.fit, r = a.r, w = AS.model.weights;
    const fr = {};
    r.fit_rows.forEach((x) => { fr[x.part] = x; });
    const fit = "<div class='row'><span class='what'>" + esc(fill(W["score.industry"], {industry: a.industry})) + "</span><span class='math'>" + esc(fill(W["score.of"], {max: f.industry.max})) + "</span><span class='p'>" + f1(fr.industry.points) + "</span></div>" +
      "<div class='row'><span class='what'>" + esc(fill(W["score.roles"], {n: n0(a.openings), band: fr.open_roles.band})) + "</span><span class='math'>" + esc(fill(W["score.of"], {max: f.open_roles.max})) + "</span><span class='p'>" + f1(fr.open_roles.points) + "</span></div>" +
      "<div class='row'><span class='what'>" + esc(fill(W["score.us"], {us: n0(fr.us_footprint.us), known: n0(fr.us_footprint.known)})) + "</span><span class='math'>" + f.us_footprint.max + " × " + n0(fr.us_footprint.us) + " ÷ " + n0(fr.us_footprint.known) + "</span><span class='p'>" + f1(fr.us_footprint.points) + "</span></div>";
    const rows = r.intent_rows.slice().sort((x, y) => (y.points - x.points) || (x.sid - y.sid));
    let sum = 0;
    rows.forEach((x) => { sum = S.roundTo(sum + x.points, 1); });
    const intent = rows.map((x) => {
      const s = SIG[x.sid];
      return "<div class='row'><span class='what'><b>" + esc(s.title) + "</b><small>" + esc(famLabel(x.family) + " · " + whenText(s)) +
        (s.temporary ? " · " + esc(W["score.temp"]) : "") + " · <a href='" + esc(s.url) + "' rel='noopener'>" + esc(W["src.open"]) + "</a></small></span>" +
        "<span class='math'>" + f1(x.base) + " × " + x.decay.toFixed(3) + (x.mult !== 1 ? " × " + x.mult : "") + "</span><span class='p'>" + f1(x.points) + "</span></div>";
    }).join("");
    const capped = sum > w.intent_cap ? "<div class='row total'><span class='what'>" + esc(fill(W["score.cap"], {cap: w.intent_cap})) + "</span><span class='math'>" + f1(sum) + "</span><span class='p'>" + f1(r.intent) + "</span></div>" : "";
    const share = Math.round(st.share * 100), rest = 100 - share;
    return "<div class='rows' id='rows'><h2>" + esc(W["score.fit"]) + " <span class='mono'>" + f1(r.fit) + "</span></h2>" + fit +
      "<h2>" + esc(W["score.intent"]) + " <span class='mono'>" + f1(r.intent) + "</span></h2>" + intent + capped +
      "<p class='rule'>" + esc(fill(W["score.rule"], {pace: w.pace_cap, half: st.half})) + "</p>" +
      "<h2>" + esc(W["score.total"]) + " <span class='mono'>" + f1(r.score) + "</span></h2>" +
      "<div class='row total'><span class='what'>" + esc(fill(W["score.formula"], {share: share + "%", rest: rest + "%"})) + " · " + esc(fill(W["score.tier"], {t: r.tier})) + "</span>" +
      "<span class='math'>" + (st.share).toFixed(2) + " × " + f1(r.intent) + " + " + (1 - st.share).toFixed(2) + " × " + f1(r.fit) + "</span><span class='p'>" + f1(r.score) + "</span></div></div>";
  }
  function ctlHtml(a) {
    const fams = FAMS.filter((k) => DEFAULTS.points[k] > 0);
    return "<aside class='ctl' id='ctl'><h2>" + esc(W["ctl.title"]) + "</h2><p>" + esc(W["ctl.note"]) + "</p>" +
      "<label for='c-share'>" + esc(W["ctl.share"]) + " <span id='v-share'>" + Math.round(st.share * 100) + "%</span></label>" +
      "<input type='range' id='c-share' data-ctl='share' min='0' max='100' step='5' value='" + Math.round(st.share * 100) + "'>" +
      "<label for='c-half'>" + esc(W["ctl.half"]) + " <span id='v-half'>" + esc(fill(W["ctl.days"], {n: st.half})) + "</span></label>" +
      "<input type='range' id='c-half' data-ctl='half' min='7' max='120' step='1' value='" + st.half + "'>" +
      "<details><summary>" + esc(W["ctl.points"]) + "</summary><div class='fam'>" + fams.map((k) =>
        "<label for='c-" + k + "'>" + esc(famLabel(k)) + " <span id='v-" + k + "'>" + f1(st.points[k]) + "</span></label>" +
        "<input type='range' id='c-" + k + "' data-ctl='fam' data-fam='" + k + "' min='0' max='" + (k === "pace" ? 5 : 60) + "' step='" + (k === "pace" ? 0.5 : 5) + "' value='" + st.points[k] + "'>").join("") +
      "</div></details><p class='moved' id='moved'" + (moved() ? "" : " hidden") + ">" + esc(W["ctl.moved"]) + "</p>" +
      "<button type='button' class='btn' data-ctl-reset>" + esc(W["ctl.reset"]) + "</button>" +
      "<div class='routebox'><h3>" + esc(W["score.route"]) + "</h3><p id='routetext'>" + esc(routeText(a)) + "</p></div></aside>";
  }
  function renderScore() {
    const view = doc.getElementById("v-score");
    const a = current();
    if (!a) { view.innerHTML = ""; return; }
    view.innerHTML = headHtml(a, "score") + "<div class='scorebody'><div class='scoremain'>" + chartHtml(a) + rowsHtml(a) + "</div>" + ctlHtml(a) + "</div>";
    fitChart();
  }
  /* The chart is drawn at the width it's shown at, so its labels stay the size of the page's text on any screen. */
  function fitChart() {
    const svg = $("#chart svg");
    const r = svg && svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
    if (!r || !r.width) { return; }
    const w = Math.round(Math.min(1600, Math.max(280, r.width)));
    if (Math.abs(w - (st.chartW || 960)) < 8) { return; }
    st.chartW = w;
    const a = current(), chart = doc.getElementById("chart");
    if (!a || !chart) { return; }
    const tmp = doc.createElement("div");
    tmp.innerHTML = chartHtml(a);
    chart.innerHTML = first(tmp).innerHTML;
  }
  function refreshScore() {
    const view = doc.getElementById("v-score");
    const a = current();
    if (!a || !$(".scorebody", view)) { renderScore(); return; }
    const head = $(".ahead", view), chart = doc.getElementById("chart"), rows = doc.getElementById("rows");
    const tmp = doc.createElement("div");
    tmp.innerHTML = headHtml(a, "score");
    if (head) { head.innerHTML = $(".ahead", tmp).innerHTML; }
    tmp.innerHTML = chartHtml(a);
    if (chart) { chart.innerHTML = first(tmp).innerHTML; }
    tmp.innerHTML = rowsHtml(a);
    if (rows) { rows.innerHTML = first(tmp).innerHTML; }
    const set = (id, v) => { const el = doc.getElementById(id); if (el) { el.textContent = v; } };
    set("v-share", Math.round(st.share * 100) + "%");
    set("v-half", fill(W["ctl.days"], {n: st.half}));
    Object.keys(st.points).forEach((k) => set("v-" + k, f1(st.points[k])));
    set("routetext", routeText(a));
    const note = doc.getElementById("moved");
    if (note) { note.hidden = !moved(); }
  }

  /* The list */
  const TIER_ORDER = {A: 0, B: 1, C: 2, D: 3};
  function renderList() {
    const view = doc.getElementById("v-list");
    const rows = ranked.filter((a) => (st.ftier === "all" || a.r.tier === st.ftier) &&
      (st.fregion === "all" || a.region === st.fregion) && (!st.fbrief || a.briefs.length));
    const col = st.sort.col, dir = st.sort.dir;
    const val = (a) => col === "name" ? a.name.toLowerCase() : col === "hub" ? (a.hub ? a.hub[0] : "~") : col === "tier" ? TIER_ORDER[a.r.tier] :
      col === "fit" ? a.r.fit : col === "intent" ? a.r.intent : col === "rank" ? -a.rank : a.r.score;
    rows.sort((x, y) => { const p = val(x), q = val(y); return (p < q ? -1 : p > q ? 1 : 0) * dir || x.rank - y.rank; });
    const cols = W.col || {};
    const th = (k, num, hide) => "<th class='" + (num ? "num" : "") + (hide ? " hidephone" : "") + "'>" + (k === "reason" ? esc(cols[k]) :
      "<button type='button' data-sort='" + k + "'" + (col === k ? " aria-sort='" + (dir < 0 ? "descending" : "ascending") + "'" : "") + ">" + esc(cols[k]) + "</button>") + "</th>";
    const regions = ["all"].concat(Object.keys(AS.model.routing.regions), [AS.model.routing.remote_region]);
    view.innerHTML = "<div class='listview'><h1>" + esc(W["list.title"]) + "</h1><p class='sub'>" +
      esc(fill(W["list.sub"], {n: n0(ranked.length), boards: n0(AS.meta.stats.boards_read), date: mdate(READ_ON)})) + "</p>" +
      "<div class='filters'><div class='chips'>" + ["all", "A", "B", "C", "D"].map((t) => "<button type='button' class='chip" + (st.ftier === t ? " on" : "") + "' data-ftier='" + t + "'>" +
        esc(t === "all" ? W["list.allTiers"] : fill(W["key.tier"], {t: t})) + "</button>").join("") + "</div>" +
      "<div class='chips'>" + regions.map((r) => "<button type='button' class='chip" + (st.fregion === r ? " on" : "") + "' data-fregion='" + esc(r) + "'>" +
        esc(r === "all" ? W["chip.all"] : r) + "</button>").join("") + "</div>" +
      "<div class='chips'><button type='button' class='chip" + (st.fbrief ? " on" : "") + "' data-fbrief aria-pressed='" + st.fbrief + "'>" + esc(W["list.brief"]) + "</button></div></div>" +
      (rows.length ? "<div class='tablewrap'><table class='accts'><thead><tr>" + th("rank", true) + th("name") + th("hub", false, true) + th("fit", true, true) + th("intent", true, true) +
        th("score", true) + th("tier") + th("reason", false, true) + "</tr></thead><tbody>" + rows.map((a) =>
          "<tr data-open='" + a.slug + "'><td class='num'>" + a.rank + "</td><td><a class='n' href='#/a/" + a.slug + "' data-go>" + esc(a.name) + "</a>" +
          (a.briefs.length ? "<span class='hasbrief'>" + esc(W["list.tag"]) + "</span>" : "") + "<small>" + esc(a.segment) + "</small></td>" +
          "<td class='hidephone'>" + esc(a.hub ? a.hub[0] + ", " + a.hub[1] : W["acct.nohub"]) + "</td><td class='num hidephone'>" + d1(a.r.fit) + "</td>" +
          "<td class='num hidephone'>" + d1(a.r.intent) + "</td><td class='num'>" + d1(a.r.score) + "</td><td>" + tierTag(a.r.tier) + "</td>" +
          "<td class='reason hidephone'>" + esc(reasonText(a)) + "</td></tr>").join("") + "</tbody></table></div>" : "<p class='empty'>" + esc(W["list.none"]) + "</p>") + "</div>";
  }

  /* How it works */
  function curveHtml() {
    const Wd = 270, H = 150, L = 30, Rr = 10, T = 10, B = 24, days = 120, base = 40;
    const x = (d) => L + d / days * (Wd - L - Rr), y = (v) => T + (1 - v / base) * (H - T - B);
    let d = "";
    for (let i = 0; i <= days; i += 2) { d += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(S.roundTo(base * S.decay(i, st.half), 1)).toFixed(1); }
    const grid = [0, 10, 20, 30, 40].map((v) => "<line x1='" + L + "' x2='" + (Wd - Rr) + "' y1='" + y(v).toFixed(1) + "' y2='" + y(v).toFixed(1) + "'/>").join("");
    const axis = [0, 20, 40].map((v) => "<text x='" + (L - 5) + "' y='" + (y(v) + 4).toFixed(1) + "' text-anchor='end'>" + v + "</text>").join("") +
      [0, 30, 60, 90, 120].map((v) => "<text x='" + x(v).toFixed(1) + "' y='" + (H - 6) + "' text-anchor='middle'>" + v + "</text>").join("");
    return "<div class='curve'><svg viewBox='0 0 " + Wd + " " + H + "' role='img' aria-label='" + esc(W["how.score.curve"]) + "'><g class='grid'>" + grid + "</g><path d='" + d + "'/><g class='axis'>" + axis + "</g></svg>" +
      "<small>" + esc(W["how.score.curve"]) + "</small></div>";
  }
  function boardHtml() {
    const sp = ((AS.scores || {}).splits || {}).briefs || {};
    const sr = (AS.second_read || {}).by_model || {};
    const cols = W["how.board.cols"] || {};
    const models = Object.keys(AS.meta.models).filter((m) => sp[m]);
    if (!models.length) { return ""; }
    return "<div class='boardwrap'><table class='board'><thead><tr><th>" + esc(cols.model) + "</th><th class='num'>" + esc(cols.first) + "</th><th class='num'>" + esc(cols.review) + "</th><th class='num'>" +
      esc(cols.held) + "</th><th class='num'>" + esc(cols.cost) + "</th><th class='num'>" + esc(cols.secs) + "</th></tr></thead><tbody>" + models.map((m) => {
      const s = sp[m], r = sr[m];
      return "<tr class='" + (m === AS.meta.route ? "routed" : "") + "'><td>" + esc(AS.meta.models[m]) + "</td><td class='num'>" + s.first_passed + " of " + s.briefs + "</td><td class='num'>" + s.needs_review +
        "</td><td class='num'>" + (r ? r.both_hold + " of " + r.briefs : "") + "</td><td class='num'>$" + Number(s.cost_per_brief).toFixed(4) + "</td><td class='num'>" + f1(s.seconds_per_brief) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
  }
  function renderHow() {
    const view = doc.getElementById("v-how");
    const m = AS.meta, s = m.stats || {}, w = AS.model.weights, sr = AS.second_read;
    const p = (k, v) => "<p>" + esc(fill(W[k], v || {})) + "</p>";
    const sec = (id, title, body) => "<section id='how-" + id + "'><h2>" + esc(W[title]) + "</h2>" + body + "</section>";
    const removed = s.removed || {};
    const scoring = s.signals_by_family ? Object.keys(s.signals_by_family).filter((k) => k !== "pace" && k !== "stack").reduce((t, k) => t + s.signals_by_family[k], 0) : 0;
    let gate = W["how.second.none"];
    if (sr && sr.gate && sr.gate.of) {
      gate = fill(sr.gate.passes ? W["how.second.pass"] : W["how.second.miss"], {held: sr.gate.held, of: sr.gate.of, need: sr.gate.need});
    }
    const items = (k) => "<ul>" + Object.values(W[k] || {}).map((t) => "<li>" + esc(t) + "</li>").join("") + "</ul>";
    const files = W["how.code.files"] || {};
    view.innerHTML = "<article class='how'><h1>" + esc(W["how.title"]) + "</h1><p class='lead'>" + esc(W["how.lead"]) + "</p>" +
      sec("sources", "how.sources.title", p("how.sources.text", {date: mdate(READ_ON)})) +
      sec("exclusions", "how.excl.title", p("how.excl.text")) +
      sec("read", "how.read.title", p("how.read.text", {boards: n0(s.boards_read), postings: n0(s.postings), placed: n0(s.postings_in_a_city), signals: n0(s.signals), scoring: n0(scoring)}) +
        p("how.read.people", {names: n0(removed.name), emails: n0(removed.email), phones: n0(removed.phone), links: n0(removed.link), handles: n0(removed.handle), tags: n0(removed.tag)})) +
      sec("scoring", "how.score.title", "<div class='two'><div>" + p("how.score.fit") + p("how.score.intent", {half: w.half_life_days, pace: w.pace_cap}) +
        p("how.score.total", {share: Math.round(w.intent_share * 100) + "%", rest: Math.round((1 - w.intent_share) * 100) + "%", vectors: m.vectors || 0}) + "</div>" + curveHtml() + "</div>") +
      sec("routing", "how.route.title", p("how.route.text")) +
      sec("briefs", "how.ai.title", p("how.ai.text", {n: NB}) + p("how.ai.touch")) +
      sec("second", "how.second.title", (sr && sr.planted ? p("how.second.text", {caught: sr.planted.by_the_gate.caught, planted: sr.planted.by_the_gate.of}) : "") + "<p>" + esc(gate) + "</p>") +
      sec("board", "how.board.title", p("how.board.text", {n: NB}) + boardHtml()) +
      sec("team", "how.team.title", items("how.team.items")) +
      sec("limits", "how.limits.title", items("how.limits.items")) +
      sec("code", "how.code.title", p("how.code.text") + "<div class='files'>" + Object.keys(files).map((f) =>
        "<button type='button' data-file='" + esc(f) + "' aria-pressed='" + (st.file === f ? "true" : "false") + "'><b>" + esc(files[f]) + "</b><code>" + esc(f) + "</code></button>").join("") +
        "</div><div class='codegrid'><nav class='code-tree' id='codetree' aria-label='" + esc(W["how.code.tree"]) + "'></nav><div id='codebox'></div></div>") +
      "<p class='footnote'>" + esc(footText()) + "</p></article>";
    showCode(st.file);
  }
  function footText() { const f = doc.querySelector(".foot p"); return f ? f.textContent : ""; }
  /* The code opens with How it works: excerpts of the real files (site/code.js), each line under its number in its
     file, with a gap mark wherever the excerpt skips lines. */
  function showCode(path) {
    const box = doc.getElementById("codebox");
    if (!box) { return; }
    const code = window.AS_CODE;
    if (!code) {
      st.file = path || st.file;
      box.innerHTML = "<p class='empty'>" + esc(W["how.code.loading"]) + "</p>";
      if (!doc.getElementById("codejs") && doc.head && doc.createElement) {
        const sc = doc.createElement("script");
        sc.setAttribute("id", "codejs");
        sc.setAttribute("src", "code.js");
        sc.onload = () => showCode(st.file);
        doc.head.appendChild(sc);
      }
      return;
    }
    path = code.files[path] ? path : code.default;
    st.file = path;
    const tree = doc.getElementById("codetree");
    if (tree && !tree.innerHTML) { tree.innerHTML = treeHtml(code); }
    $$("[data-file]").forEach((b) => b.setAttribute("aria-pressed", b.getAttribute("data-file") === path ? "true" : "false"));
    const f = code.files[path];
    const gap = "<span class='gap'>⋯</span>";
    let rows = "", shown = 0, next = 1;
    f.parts.forEach((part) => {
      if (part[0] > next) { rows += gap; }
      const lines = part[1].split("\n");
      lines.forEach((l, k) => { rows += "<span data-n='" + (part[0] + k) + "'>" + (esc(l) || " ") + "</span>"; });
      shown += lines.length;
      next = part[0] + lines.length;
    });
    if (next <= f.lines) { rows += gap; }
    box.innerHTML = "<div class='codeview'><div class='meta'>" + esc(path) + " · " + esc(fill(W["how.code.lines"], {shown: shown, n: f.lines})) + "</div><pre>" +
      rows + "</pre></div>";
  }
  function treeHtml(code) {
    let folder = null, out = "";
    Object.keys(code.files).sort().forEach((rel) => {
      const cut = rel.lastIndexOf("/");
      const top = rel.slice(0, cut + 1);
      if (top !== folder) { folder = top; if (top) { out += "<p>" + esc(top) + "</p>"; } }
      out += "<button type='button' data-file='" + esc(rel) + "' aria-pressed='false'>" + esc(rel.slice(cut + 1)) + "</button>";
    });
    return out;
  }

  /* The tour: each step has its own address */
  const TOUR = Object.keys(W["tour.steps"] || {}).map((k) => {
    const v = String(W["tour.steps"][k]).split("|");
    return {key: k, title: v[0], text: v[1] || ""};
  });
  const TARGET = {map: ["map", ".mapbox"], why: ["map", "#why"], top: ["map", ".toplist"], brief: ["account", ".whynow"],
    read: ["account", "#read"], touch: ["account", "#touch"], score: ["score", "#rows"], weights: ["score", "#ctl"],
    list: ["list", "table.accts"], how: ["how", ".how h1"]};
  function showTour() {
    const box = doc.getElementById("tour");
    $$(".spot").forEach((el) => el.classList.remove("spot"));
    if (st.tour < 0 || !TOUR[st.tour]) { box.hidden = true; return; }
    const step = TOUR[st.tour];
    box.hidden = false;
    box.innerHTML = "<button type='button' class='x' data-tour-close aria-label='" + esc(W["tour.close"]) + "'>×</button><b>" + esc(step.title) + "</b><p>" + esc(step.text) + "</p>" +
      "<div class='tc'><span>" + esc(fill(W["tour.count"], {i: st.tour + 1, n: TOUR.length})) + "</span><span>" +
      (st.tour > 0 ? "<button type='button' data-tour-back>" + esc(W["tour.back"]) + "</button> " : "") +
      (st.tour < TOUR.length - 1 ? "<button type='button' class='pri' data-tour-next>" + esc(W["tour.next"]) + "</button>" :
        "<button type='button' class='pri' data-tour-close>" + esc(W["tour.close"]) + "</button>") + "</span></div>";
    const t = TARGET[step.key];
    const el = t && $(t[1], doc.getElementById("v-" + t[0]));
    if (el) {
      el.classList.add("spot");
      if (el.scrollIntoView) { el.scrollIntoView({block: "center", behavior: calm() ? "auto" : "smooth"}); }
    }
  }

  /* Routing between views */
  function parse(hash) {
    const h = String(hash || "").replace(/^#\/?/, "");
    const p = h.split("/").filter(Boolean);
    if (p[0] === "a" && p[1]) { return {view: p[2] === "score" ? "score" : "account", sel: p[1]}; }
    if (p[0] === "map") { return {view: "map", sel: p[1] || ""}; }
    if (p[0] === "list") { return {view: "list"}; }
    if (p[0] === "how") { return {view: "how"}; }
    if (p[0] === "tour") { return {view: "tour", step: Math.max(1, Math.min(TOUR.length, parseInt(p[1], 10) || 1))}; }
    return {view: "map", sel: ""};
  }
  function show(view) {
    st.view = view;
    const inStrip = STRIP.indexOf(view) >= 0;
    const strip = doc.getElementById("strip");
    if (strip) { strip.classList.toggle("on", inStrip); }
    ["map", "account", "score", "list", "how"].forEach((v) => {
      const el = doc.getElementById("v-" + v);
      if (el) { el.classList.toggle("on", phone() && inStrip ? STRIP.indexOf(v) >= 0 : v === view); }
    });
    $$("[data-nav]").forEach((a) => a.classList.toggle("on", a.getAttribute("data-nav") === view || (view !== "list" && view !== "how" && a.getAttribute("data-nav") === "map")));
    $$("[data-tab]").forEach((b) => b.setAttribute("aria-current", b.getAttribute("data-tab") === view ? "true" : "false"));
    if (phone() && inStrip && strip && strip.scrollTo && strip.clientWidth) {
      strip.scrollTo({left: STRIP.indexOf(view) * strip.clientWidth, behavior: "auto"});
    }
  }
  function render(view) {
    if (view === "map" || phone()) { if ($(".map", doc.getElementById("v-map"))) { renderSide(); } else { renderMap(); } }
    if (view === "account" || (phone() && STRIP.indexOf(view) >= 0)) { renderAccount(); }
    if (view === "score" || (phone() && STRIP.indexOf(view) >= 0)) { renderScore(); }
    if (view === "list") { renderList(); }
    if (view === "how") { renderHow(); }
  }
  function route() {
    const hash = window.location.hash || "";
    if (hash === st.hash) { return; }
    st.hash = hash;
    const r = parse(hash);
    if (r.view === "tour") {
      st.tour = r.step - 1;
      const step = TOUR[st.tour], t = TARGET[step.key];
      if (t[0] === "account" || t[0] === "score") { st.sel = briefAccount().slug; }
      if (!BY[st.sel]) { st.sel = ranked[0].slug; }
      show(t[0]);
      render(t[0]);
      showTour();
      return;
    }
    st.tour = -1;
    showTour();
    if (r.sel && BY[r.sel]) { st.sel = r.sel; }
    if (!BY[st.sel]) { st.sel = ranked[0] ? ranked[0].slug : ""; }
    show(r.view);
    render(r.view);
    const a = current();
    doc.title = (r.view === "account" || r.view === "score") && a && TITLE ? a.name + " · " + TITLE : TITLE;
  }
  function nav(hash) {
    if (window.location.hash !== hash) { window.location.hash = hash; }
    route();
  }

  /* Weights */
  function reweigh() {
    rescore();
    repackMap();
    if (st.view === "score" || phone()) { refreshScore(); }
    if (st.view === "list") { renderList(); }
  }

  /* Dark mode (11/20): the switch in the top bar turns it on. */
  function setDark(on) {
    doc.body.classList.toggle("dark", !!on);
    const b = doc.getElementById("theme");
    if (b) { b.setAttribute("aria-pressed", on ? "true" : "false"); }
  }

  /* Events, all delegated from the document */
  function onClick(ev) {
    const t = ev.target && ev.target.closest ? ev.target : null;
    if (!t) { return; }
    if (t.closest("#theme")) { setDark(!doc.body.classList.contains("dark")); return; }
    if (st.dragged && Date.now() - st.dragged < 350 && t.closest(".mapbox")) { st.dragged = 0; return; }
    const zb = t.closest("[data-zoom]");
    if (zb) {
      const k = zb.getAttribute("data-zoom");
      if (k === "reset") { resetZoom(); } else { zoomTo(st.zoom.k * (k === "in" ? 2 : 0.5)); }
      return;
    }
    const go = t.closest("a[data-go]");
    if (go) {
      const lr = go.getAttribute("data-list-region");
      if (lr) { st.fregion = lr; st.ftier = "all"; }
      ev.preventDefault();
      if (st.tour >= 0) { st.tour = -1; }
      nav(go.getAttribute("href"));
      return;
    }
    const ring = t.closest(".map [data-ring]");
    if (ring) { pickMark(ring.getAttribute("data-ring")); return; }
    if (t.closest("[data-ring-back]")) { st.ring = null; renderSide(); renderMarks(); return; }
    if (mapSvg(t)) { clearPick(); return; }
    const pick = t.closest("[data-pick]");
    if (pick) { select(pick.getAttribute("data-pick")); return; }
    const reg = t.closest("[data-region]");
    if (reg) {
      st.region = reg.getAttribute("data-region");
      st.ring = null;
      st.fp = null;
      if (st.region === "all" || st.region === "tierA") { st.zoom = {k: 1, cx: null, cy: null}; } else { fitTo(ranked.filter(inRegion)); }
      renderMap();
      return;
    }
    const mod = t.closest("[data-model]");
    if (mod) { const a = current(); st.model[a.slug] = mod.getAttribute("data-model"); renderAccount(); return; }
    const tb = t.closest("[data-touch]");
    if (tb) { touchAction(tb.getAttribute("data-touch")); return; }
    const so = t.closest("[data-sort]");
    if (so) {
      const c = so.getAttribute("data-sort");
      st.sort = {col: c, dir: st.sort.col === c ? -st.sort.dir : (c === "name" || c === "hub" || c === "tier" ? 1 : -1)};
      renderList();
      return;
    }
    const ft = t.closest("[data-ftier]");
    if (ft) { st.ftier = ft.getAttribute("data-ftier"); renderList(); return; }
    const fr = t.closest("[data-fregion]");
    if (fr) { st.fregion = fr.getAttribute("data-fregion"); renderList(); return; }
    if (t.closest("[data-fbrief]")) { st.fbrief = !st.fbrief; renderList(); return; }
    const row = t.closest("tr[data-open]");
    if (row) { nav("#/a/" + row.getAttribute("data-open")); return; }
    const file = t.closest("[data-file]");
    if (file) { showCode(file.getAttribute("data-file")); return; }
    const tour = t.closest("[data-tour]");
    if (tour) { nav("#/tour/" + (parseInt(tour.getAttribute("data-tour"), 10) + 1)); return; }
    if (t.closest("[data-tour-next]")) { nav("#/tour/" + (st.tour + 2)); return; }
    if (t.closest("[data-tour-back]")) { nav("#/tour/" + Math.max(1, st.tour)); return; }
    if (t.closest("[data-tour-close]")) { closeTour(); return; }
    const tab = t.closest("[data-tab]");
    if (tab) { tabTo(tab.getAttribute("data-tab")); return; }
    if (t.closest("[data-ctl-reset]")) {
      st.share = DEFAULTS.share; st.half = DEFAULTS.half; st.points = Object.assign({}, DEFAULTS.points);
      reweigh();
      renderScore();
    }
  }
  function closeTour() {
    const step = TOUR[st.tour];
    const t = step ? TARGET[step.key] : ["map"];
    st.tour = -1;
    const a = current();
    nav(t[0] === "account" ? "#/a/" + a.slug : t[0] === "score" ? "#/a/" + a.slug + "/score" : "#/" + t[0]);
  }
  function select(slug) {
    if (!BY[slug]) { return; }
    st.sel = slug;
    if (st.view === "map") {
      renderSide();
      if (window.history && window.history.replaceState) { window.history.replaceState(null, "", "#/map/" + slug); st.hash = "#/map/" + slug; }
      if (phone()) { renderAccount(); renderScore(); }
    } else {
      nav("#/map/" + slug);
    }
  }
  function tabTo(tab) {
    if (tab === "how") { nav("#/how"); return; }
    const a = current();
    nav(tab === "map" ? "#/map" : tab === "account" ? "#/a/" + a.slug : "#/a/" + a.slug + "/score");
  }
  function touchAction(what) {
    const a = current(), b = briefOf(a);
    if (!b) { return; }
    const t = touchState(a, b);
    if (what === "edit") { t.edit = !t.edit; if (t.edit) { t.status = ""; } }
    if (what === "approve" && !touchProblems(a, b).length) { t.status = "approved"; t.edit = false; }
    if (what === "reject") { t.status = "rejected"; t.edit = false; }
    if (what === "reset") {
      const o = b.brief.first_touch || {};
      t.subject = o.subject || ""; t.body = o.body || ""; t.status = ""; t.edit = false;
    }
    const box = doc.getElementById("touch");
    if (box) {
      const tmp = doc.createElement("div");
      tmp.innerHTML = touchHtml(a, b);
      box.innerHTML = first(tmp).innerHTML;
    }
    later(drawThreads, 0);
  }
  function onInput(ev) {
    const t = ev.target;
    if (!t || !t.getAttribute) { return; }
    const field = t.getAttribute("data-touch-field");
    if (field) {
      const a = current(), b = briefOf(a);
      if (!b) { return; }
      const s = touchState(a, b);
      s[field] = t.value;
      s.status = "";
      const problems = touchProblems(a, b);
      const old = doc.getElementById("checks");
      if (old) {
        const tmp = doc.createElement("div");
        tmp.innerHTML = checksHtml(problems);
        old.innerHTML = first(tmp).innerHTML;
        old.setAttribute("class", first(tmp).getAttribute("class"));
      }
      const ap = $("[data-touch='approve']");
      if (ap) { if (problems.length) { ap.setAttribute("disabled", ""); } else { ap.removeAttribute("disabled"); } ap.disabled = !!problems.length; }
      const status = doc.getElementById("tstatus");
      if (status) { status.innerHTML = ""; }
      return;
    }
    const ctl = t.getAttribute("data-ctl");
    if (!ctl) { return; }
    const v = Number(t.value), before = JSON.stringify([st.share, st.half, st.points]);
    if (ctl === "share") { st.share = S.roundTo(v / 100, 2); }
    if (ctl === "half") { st.half = Math.max(1, Math.round(v)); }
    if (ctl === "fam") { st.points = Object.assign({}, st.points); st.points[t.getAttribute("data-fam")] = v; }
    if (JSON.stringify([st.share, st.half, st.points]) !== before) { reweigh(); }
  }
  function onOver(ev) {
    const t = ev.target && ev.target.closest ? ev.target : null;
    if (!t) { return; }
    const ring = t.closest(".map [data-ring]");
    const tip = doc.getElementById("maptip");
    const g = ring && marks.find((m) => m.members[0].slug === ring.getAttribute("data-ring"));
    if (g && tip && !(gest && gest.moved)) {
      const v = viewRect(), best = g.members[0], n = g.members.length;
      tip.textContent = n === 1 ? best.name + " · " + best.hub[0] + " · " + f1(best.r.score) :
        fill(W["ring.tip"], {place: placeName(g), n: n, name: best.name});
      tip.style.left = (g.x - v.x * v.s).toFixed(0) + "px";
      tip.style.top = (g.y - v.y * v.s - ringR(g)).toFixed(0) + "px";
      tip.hidden = false;
    } else if (tip && !tip.hidden) { tip.hidden = true; }
    /* Pointing at an account in a list lights up every city it hires in until the pointer leaves it. */
    const row = t.closest("[data-fp]");
    const hover = row ? row.getAttribute("data-fp") : null;
    if (hover !== st.hover && (hover || st.hover)) { st.hover = hover; renderMarks(); }
    const sent = t.closest(".brief [data-i]");
    if (sent) { highlight(sent.getAttribute("data-i"), null); return; }
    if (t.closest(".touch")) { highlight("touch", null); return; }
    const src = t.closest(".sources .src[data-src]");
    if (src) { highlight(null, src.getAttribute("data-src")); return; }
    if (doc.getElementById("acctbody") && $(".acctbody .hot")) { highlight(null, null); }
  }
  function onKey(ev) {
    if (st.tour >= 0) {
      if (ev.key === "Escape") { closeTour(); return; }
      if (ev.key === "ArrowRight" && st.tour < TOUR.length - 1) { nav("#/tour/" + (st.tour + 2)); return; }
      if (ev.key === "ArrowLeft" && st.tour > 0) { nav("#/tour/" + st.tour); return; }
    }
    const t = ev.target;
    if (t && t.closest && t.closest(".mapbox") && ["+", "=", "-", "0"].indexOf(ev.key) >= 0) {
      if (ev.key === "0") { resetZoom(); } else { zoomTo(st.zoom.k * (ev.key === "-" ? 0.5 : 2)); }
      return;
    }
    if ((ev.key === "Enter" || ev.key === " ") && t && t.getAttribute && t.getAttribute("data-ring")) {
      if (ev.preventDefault) { ev.preventDefault(); }
      pickMark(t.getAttribute("data-ring"));
      return;
    }
    if (ev.key === "Escape" && st.view === "map") { clearPick(); }
  }

  /* Start */
  rescore();
  st.sel = ranked[0] ? ranked[0].slug : "";
  const fresh = doc.getElementById("fresh");
  if (fresh) { fresh.innerHTML = "<i></i>" + esc(fill(W.fresh, {boards: n0(AS.meta.stats.boards_read), date: mdate(READ_ON)})); }
  const banner = doc.getElementById("banner");
  if (banner && (AS.meta.preview || AS.meta.stand_in)) { banner.textContent = AS.meta.preview ? W["banner.preview"] : W["banner.standin"]; banner.hidden = false; }
  doc.addEventListener("click", onClick);
  doc.addEventListener("input", onInput);
  doc.addEventListener("change", onInput);
  doc.addEventListener("mouseover", onOver);
  doc.addEventListener("focusin", onOver);
  doc.addEventListener("keydown", onKey);
  doc.addEventListener("pointerdown", onDown);
  doc.addEventListener("pointermove", onMove);
  doc.addEventListener("pointerup", onUp);
  doc.addEventListener("pointercancel", onUp);
  doc.addEventListener("wheel", onWheel, {passive: false});
  doc.addEventListener("dblclick", onDbl);
  window.addEventListener("hashchange", route);
  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = later(() => { show(st.view); applyView(); drawThreads(); fitChart(); }, 120);
  });
  /* The brief and its sources scroll on their own, so the threads follow them. */
  let threadQueued = false;
  doc.addEventListener("scroll", (ev) => {
    const body = doc.getElementById("acctbody");
    if (!body || threadQueued || !ev.target || !ev.target.closest || !ev.target.closest("#acctbody")) { return; }
    threadQueued = true;
    later(() => { threadQueued = false; drawThreads(); }, 16);
  }, true);
  if (mq && mq.addEventListener) { mq.addEventListener("change", () => { st.hash = null; route(); }); }
  const strip = doc.getElementById("strip");
  if (strip && strip.addEventListener) {
    let t2 = 0;
    strip.addEventListener("scroll", () => {
      if (!phone()) { return; }
      window.clearTimeout(t2);
      t2 = later(() => {
        const i = Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth));
        const v = STRIP[Math.max(0, Math.min(2, i))];
        if (v !== st.view) {
          st.view = v;
          $$("[data-tab]").forEach((b) => b.setAttribute("aria-current", b.getAttribute("data-tab") === v ? "true" : "false"));
          const a = current();
          const h = v === "map" ? "#/map/" + a.slug : v === "account" ? "#/a/" + a.slug : "#/a/" + a.slug + "/score";
          if (window.history && window.history.replaceState) { window.history.replaceState(null, "", h); st.hash = h; }
        }
      }, 90);
    });
  }
  route();
  if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) { doc.fonts.ready.then(() => drawThreads()); }

  window.ASP = {state: () => st, ranked: () => ranked, routes: () => routes, current: current, pick: pickMark,
    marks: () => groupsAt(viewRect().s).map((g) => ({x: g.x, y: g.y, r: ringR(g), n: g.members.length, place: placeName(g),
      slugs: g.members.map((a) => a.slug)})),
    nav: nav, rescore: reweigh, whyText: whyText, briefOf: briefOf, touchProblems: touchProblems, tour: TOUR, accounts: ACCTS,
    zoom: () => Object.assign({}, st.zoom), zoomTo: zoomTo, view: () => viewRect(), dark: setDark};
})();
