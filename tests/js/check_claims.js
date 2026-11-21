/* The parity check for site/claims.js against the cases engine/claims.py answered in tests/vectors/claims.json:
   sentences, first touches and whole briefs, problem for problem. Exits 1 on any miss.

       node tests/js/check_claims.js */
"use strict";
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "..");
const C = require(path.join(root, "site", "claims.js"));
const v = JSON.parse(fs.readFileSync(path.join(root, "tests", "vectors", "claims.json"), "utf8"));
const firstNames = new Set(fs.readFileSync(path.join(root, "config", "first_names.txt"), "utf8").split("\n")
  .filter((l) => !l.startsWith("#")).join(" ").split(/\s+/).filter(Boolean));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const misses = [];
let n = 0;

for (const c of v.sentences) {
  n++;
  const got = C.checkSentence(c.text, c.cites, v.sources, v.account, v.read_on, v.tools, c.need_cite, false, firstNames);
  if (!same(got, c.expected)) misses.push(`${c.text}: ${JSON.stringify(got)} vs ${JSON.stringify(c.expected)}`);
}
for (const c of v.touches) {
  n++;
  const got = C.checkTouch(c.touch, v.sources, v.account, v.read_on, v.tools, firstNames);
  if (!same(got, c.expected)) misses.push(`touch ${c.touch.subject}: ${JSON.stringify(got)} vs ${JSON.stringify(c.expected)}`);
}
for (const c of v.briefs) {
  n++;
  const got = C.checkBrief(c.brief, v.sources, v.account, v.read_on, v.tools, firstNames);
  if (!same(got, c.expected)) misses.push(`brief: ${JSON.stringify(got)} vs ${JSON.stringify(c.expected)}`);
}
misses.slice(0, 6).forEach((m) => console.log("MISS " + m));
console.log(`${n - misses.length} of ${n} claim vectors match`);
process.exit(misses.length ? 1 : 0);
