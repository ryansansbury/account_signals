/* The parity check for site/scoring.js and site/route.js against the vectors the Python wrote. Every number has to
   match exactly, since the page re-ranks with this code and the build ranks with the Python. Exits 1 on any miss.

       node tests/js/check_scoring.js */
"use strict";
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "..");
const S = require(path.join(root, "site", "scoring.js"));
const R = require(path.join(root, "site", "route.js"));
const sv = JSON.parse(fs.readFileSync(path.join(root, "tests", "vectors", "scoring.json"), "utf8"));
const rv = JSON.parse(fs.readFileSync(path.join(root, "tests", "vectors", "routing.json"), "utf8"));
const misses = [];
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let n = 0;

for (const [x, p, want] of sv.round) { n++; if (S.roundTo(x, p) !== want) misses.push(`round ${x} to ${p}: ${S.roundTo(x, p)} vs ${want}`); }
for (const [a, h, want] of sv.decay) { n++; if (S.decay(a, h) !== want) misses.push(`decay ${a} days at ${h}: ${S.decay(a, h)} vs ${want}`); }
for (const [s, want] of sv.tiers) { n++; if (S.tierOf(s, sv.model) !== want) misses.push(`tier of ${s}`); }
for (const c of sv.cases) {
  n++;
  const r = S.score(c.account, c.signals, sv.model, c.opts);
  const got = {fit: r.fit, intent: r.intent, score: r.score, tier: r.tier, fit_points: r.fit_rows.map((x) => x.points),
    counted: r.intent_rows.map((x) => [x.sid, x.points, x.decay])};
  if (!same(got, c.expected)) misses.push(`${c.account.account} ${JSON.stringify(c.opts)}: ${JSON.stringify(got)} vs ${JSON.stringify(c.expected)}`);
}
for (const h of sv.history) {
  n++;
  const got = S.history(h.account, h.signals, sv.model, h.opts);
  if (!same(got, h.expected)) misses.push(`history of ${h.account.account}`);
}
for (const s of rv.sets) {
  n++;
  const got = R.route(s.accounts, rv.cfg, rv.read_on);
  if (!same(Object.keys(got).sort().map((k) => [k, got[k]]), Object.keys(s.expected).sort().map((k) => [k, s.expected[k]])))
    misses.push("a routing set differs");
}
for (const [d, k, want] of rv.business_days) { n++; if (R.businessDays(d, k) !== want) misses.push(`${k} business days from ${d}`); }

misses.slice(0, 8).forEach((m) => console.log("MISS " + m));
console.log(`${n - misses.length} of ${n} parity vectors match (scoring and routing)`);
process.exit(misses.length ? 1 : 0);
