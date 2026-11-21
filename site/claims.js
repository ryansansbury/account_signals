/* Account Signals: the claim checker, ported from engine/claims.py so an edited first touch is checked live with the
   same rules as the recorded briefs. Citations, numbers, recency and dates, quotes, names, tools, promises and the
   first touch's rules, each problem as "kind: detail" in the same order as the Python. The writing rules run in the
   build only. tests/vectors/claims.json holds the cases both must agree on. */
(function (root) {
  "use strict";
  const NUM_WORDS = {one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
    eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
    nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50};
  const MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december"];
  const MON = {};
  MONTHS.forEach((m, i) => { MON[m.slice(0, 3)] = i + 1; });
  const UNITS = {day: 1, days: 1, week: 7, weeks: 7, month: 30, months: 30, quarter: 91, quarters: 91};
  const NW = Object.keys(NUM_WORDS).join("|");
  const COUNTED = "(?:roles?|postings?|openings?|positions?|jobs?|hires?|reqs?|listings?)";
  const MARK = /\s*\[(\d+)\]/g;
  const ISO = /\b\d{4}-\d{2}-\d{2}\b/g;
  const QUOTE = /["“]([^"”]{3,})["”]/g;
  const READ = "before\\s+(?:the\\s+|that\\s+)?(?:read\\s+date|board\\s+was\\s+read)";
  const AGO = new RegExp("(?<![Tt]he )\\b(\\d+|" + NW + ")\\s+days?\\s+(?:ago|old|" + READ + ")\\b", "gi");
  const WINDOW = new RegExp("\\b(?:in|over|within|during) the (?:(?:last|past) (?:(\\d+|" + NW +
    "|a|one)\\s+)?(days?|weeks?|months?|quarters?)|(\\d+|" + NW + ")\\s+(days?|weeks?)\\s+" + READ + ")\\b", "gi");
  const THIS = /\bthis (week|month|quarter)\b/gi;
  const SINCE = new RegExp("\\bsince (" + MONTHS.join("|") + ")\\b", "gi");
  const MONTH_DAY = new RegExp("\\b(" + MONTHS.map((m) => m.slice(0, 3)).join("|") +
    ")[a-z]*\\.?\\s+(\\d{1,2})(?:st|nd|rd|th)?\\b", "gi");
  const IN_MONTH = new RegExp("\\b(?:in|from|during) (" + MONTHS.map((m) => m[0].toUpperCase() + m.slice(1)).join("|") +
    ")\\b(?!\\s+\\d{1,2}\\b)", "g");
  const NUMBER = new RegExp("\\$?\\d[\\d,]*(?:\\.\\d+)?(?:[%kKmM]\\b|%)?|\\b(?:" + NW + ")\\b|\\ba dozen\\b", "gi");
  const CAP = /\b[A-Z][A-Za-z'’&.-]*[A-Za-z]|\b[A-Z]\b/g;
  const PROMISES = ["\\bguarantee\\w*", "\\bsave (?:you|your team)\\b",
    "\\bincrease (?:your )?(?:revenue|pipeline|win rates?|bookings)\\b", "\\bdouble (?:your )?\\w+",
    "\\b\\d+\\s*(?:%|percent)\\s+(?:more|faster|less|lift|increase|improvement|growth)\\b", "\\bfree\\b",
    "\\bno cost\\b", "\\bROI\\b", "\\bwe(?:'ll| will) (?:deliver|get you|make sure|guarantee)\\b"].map((p) => new RegExp(p, "i"));
  const SHARED = new Set(`I I'd I'm I'll I've A An The This That These Those It It's Its We We're Our You You're Your
They Their If When Since With For From In On At As And But Or So Hi Hello Thanks Thank Best Would Could Can Is Are Was
Were Do Does Did Has Have Had Will What Why How Who Where Which Happy Glad Curious Saw Noticed Reading Worth Quick Open
Glad One Two Three Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
August September October November December US U.S. USA CRM CRO VP SVP EVP CFO COO CEO GTM SaaS ERP CPQ AI ML BI KPI KPIs
QBR QBRs SDR SDRs BDR BDRs AE AEs RevOps Ops Sales Revenue Operations Operation Marketing Finance Customer Success
Analytics Data Engineering Engineer Manager Director Head Lead Leader Analyst Analysts Administrator Admin Systems
Strategy Enablement Deal Desk Partnerships Leadership Team Teams Pipeline Forecast Forecasting Territory Territories
Region Regions West East North South Midwest Southeast Northeast Southwest Northwest Mountain Central Coast Pacific
Atlantic America Americas Enterprise Mid-Market Commercial SMB Senior Principal Staff Associate Specialist Coordinator
Vice President Chief Officer`.split(/\s+/));
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const all = (re, s) => { re.lastIndex = 0; return [...s.matchAll(re)]; };

  function numval(tok) {
    let t = tok.toLowerCase().replace(/,/g, "").replace(/\$/g, "").trim();
    if (t === "a dozen") return 12;
    if (has(NUM_WORDS, t)) return NUM_WORDS[t];
    let mult = 1;
    if (t.endsWith("%")) t = t.slice(0, -1);
    else if (t.endsWith("k")) { t = t.slice(0, -1); mult = 1000; }
    else if (t.endsWith("m")) { t = t.slice(0, -1); mult = 1000000; }
    if (t === "") return null;
    const v = Number(t);
    return Number.isNaN(v) ? null : v * mult;
  }

  function dayNumber(iso) {
    const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
    return Date.UTC(y, m - 1, d) / 86400000;
  }
  const daysBetween = (a, b) => dayNumber(b) - dayNumber(a);
  const sourceText = (s) => ["title", "excerpt", "text"].map((k) => String(s[k] || "")).join(" ");
  const toolIn = (tool, text) => new RegExp("(?<![\\w-])" + esc(tool) + "(?![\\w-])").test(text);
  const countOf = (tok) => Math.trunc(tok && !["a", "one"].includes(tok.toLowerCase()) ? numval(tok) : 1);

  function sentences(text) {
    return (text || "").split(/(?<=[.!?])\s+(?=[A-Z"“(\[{])/).map((s) => s.trim()).filter(Boolean);
  }

  function checkSentence(text, cites, sources, account, readOn, tools, needCite, promises, firstNames, pooled) {
    if (needCite === undefined) needCite = true;
    const problems = [];
    const plain = text.replace(MARK, "").trim();
    for (const c of cites) if (!has(sources, c)) problems.push(`cite: [${c}]`);
    const cited = cites.filter((c) => has(sources, c)).map((c) => sources[c]);
    if (needCite && !cited.length) problems.push("cite: none");
    const src = cited.map(sourceText).join(" ");
    const srcLow = src.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
    const posts = cited.filter((s) => s.posted);
    for (const m of all(QUOTE, plain)) {
      const q = m[1];
      const core = q.trim().replace(/^…+/, "").replace(/…+$/, "").replace(/[.,;:!?]+$/, "").trim();
      if (!srcLow.includes(core.toLowerCase().split(/\s+/).filter(Boolean).join(" "))) problems.push(`quote: "${q}"`);
    }
    const bare = plain.replace(QUOTE, " ");
    const skip = [];
    const span = (m) => [m.index, m.index + m[0].length];
    for (const m of all(ISO, bare)) {
      skip.push(span(m));
      if (!posts.some((s) => s.posted === m[0]) && !src.includes(m[0])) problems.push(`date: ${m[0]}`);
    }
    for (const m of all(AGO, bare)) {
      skip.push(span(m));
      if (!posts.some((s) => daysBetween(s.posted, readOn) === countOf(m[1]))) problems.push(`recency: ${m[0]}`);
    }
    const ages = posts.map((s) => daysBetween(s.posted, readOn)).sort((a, b) => a - b);
    for (const m of all(WINDOW, bare)) {
      skip.push(span(m));
      const [n, unit] = m[4] ? [m[3], m[4]] : [m[1], m[2]];
      const limit = countOf(n) * UNITS[unit.toLowerCase()];
      if (!ages.length || (pooled ? ages[0] : ages[ages.length - 1]) > limit) problems.push(`recency: ${m[0]}`);
    }
    for (const m of all(THIS, bare)) {
      skip.push(span(m));
      const limit = UNITS[m[1].toLowerCase()];
      if (!ages.length || (pooled ? ages[0] : ages[ages.length - 1]) > limit) problems.push(`recency: ${m[0]}`);
    }
    const dates = posts.map((s) => s.posted).sort();
    for (const m of all(SINCE, bare)) {
      skip.push(span(m));
      const month = MONTHS.indexOf(m[1].toLowerCase()) + 1;
      const year = Number(readOn.slice(0, 4)) - (month > Number(readOn.slice(5, 7)) ? 1 : 0);
      const start = `${year}-${String(month).padStart(2, "0")}-01`;
      if (!dates.length || (pooled ? dates[dates.length - 1] : dates[0]) < start) problems.push(`date: ${m[0]}`);
    }
    for (const m of all(IN_MONTH, bare)) {  // "in July": a cited posting went up that month, in the year before the read
      skip.push(span(m));
      const month = MONTHS.indexOf(m[1].toLowerCase()) + 1;
      const year = Number(readOn.slice(0, 4)) - (month > Number(readOn.slice(5, 7)) ? 1 : 0);
      const want = `${year}-${String(month).padStart(2, "0")}`;
      if (!dates.some((d) => d.slice(0, 7) === want)) problems.push(`date: ${m[0]}`);
    }
    const srcDays = new Set(all(ISO, src).map((m) => Number(m[0].slice(5, 7)) * 100 + Number(m[0].slice(8, 10))));
    for (const m of all(MONTH_DAY, bare)) {
      skip.push(span(m));
      const wantM = MON[m[1].toLowerCase().slice(0, 3)], wantD = Number(m[2]);
      if (!posts.some((s) => Number(s.posted.slice(5, 7)) === wantM && Number(s.posted.slice(8, 10)) === wantD) &&
          !srcDays.has(wantM * 100 + wantD))
        problems.push(`date: ${m[0]}`);
    }
    const noDates = src.replace(/\d{4}-\d{2}-\d{2}/g, " ");
    const have = new Set(all(NUMBER, noDates).map((m) => numval(m[0])).concat(all(NUMBER, account).map((m) => numval(m[0]))));
    const years = new Set([Number(readOn.slice(0, 4))].concat(posts.map((s) => Number(s.posted.slice(0, 4)))));
    const distinct = new Set(cited.filter((s) => s.posting_id).map((s) => s.posting_id)).size;
    const counted = new RegExp("^\\s+(?:[a-z-]+\\s+){0,4}" + COUNTED + "\\b", "i");
    for (const m of all(NUMBER, bare)) {
      if (skip.some(([a, b]) => a <= m.index && m.index < b)) continue;
      const v = numval(m[0]);
      if (v === null || have.has(v) || years.has(v)) continue;
      const counts = counted.test(bare.slice(m.index + m[0].length, m.index + m[0].length + 40));
      if (/^[A-Za-z]/.test(m[0]) && !counts) continue;
      if (counts && v >= 1 && v <= distinct) continue;
      problems.push(`number: ${m[0]}`);
    }
    // A sentence starts at the front and after any full stop inside the text, since one item can hold two sentences.
    const starts = new Set([bare.length - bare.replace(/^\s+/, "").length]
      .concat(all(/[.!?]\s+/g, bare).map((m) => m.index + m[0].length)));
    const acctWords = new Set(account.match(/[A-Za-z0-9'’&.-]+/g) || []);
    const namedTools = tools.filter((t) => toolIn(t, plain));
    const known = (w) => SHARED.has(w) || acctWords.has(w) || namedTools.some((t) => t.split(" ").includes(w)) ||
      new RegExp("(?<![A-Za-z])" + esc(w) + "(?![A-Za-z])").test(src);
    for (const m of all(CAP, bare)) {
      const w = m[0].replace(/\.+$/, "").replace(/['’]s$/, "");
      if (known(w) || (w.includes("-") && w.split("-").filter((p) => /^[A-Z]/.test(p)).every(known))) continue;
      if (starts.has(m.index) && !(firstNames && firstNames.has(w))) continue;
      problems.push(`name: ${w}`);
    }
    for (const t of namedTools) if (!toolIn(t, src)) problems.push(`tool: ${t}`);
    if (promises) for (const p of PROMISES) { const m = p.exec(plain); if (m) problems.push(`promise: ${m[0]}`); }
    if (plain.includes("removed]")) problems.push("rule: a redaction marker");
    return problems;
  }

  function checkTouch(touch, sources, account, readOn, tools, firstNames) {
    const out = [];
    const body = (touch.body || "").trim();
    const cites = (touch.cites || []).map(Number);
    if ((touch.subject || "").length > 60) out.push("rule: subject over 60 characters");
    const words = (body.match(/\S+/g) || []).length;
    if (words > 120) out.push(`rule: ${words} words`);
    if (!body.startsWith("Hi {first_name},")) out.push("rule: greeting");
    if (!body.includes("{sender_name}")) out.push("rule: sign-off");
    if (/\{(?!first_name\}|sender_name\})[^}]*\}/.test(body)) out.push("rule: an unknown placeholder");
    if (/\s*\[(\d+)\]/.test(body)) out.push("rule: a citation marker in the email");
    if (!cites.length) out.push("cite: none");
    for (let line of body.split("\n")) {
      line = line.trim();
      if (!line || line.startsWith("Hi {first_name}") || line.includes("{sender_name}")) continue;
      for (const s of sentences(line)) out.push(...checkSentence(s, cites, sources, account, readOn, tools, false, true, firstNames, true));
    }
    return out;
  }

  function checkBrief(brief, sources, account, readOn, tools, firstNames) {
    const rows = [], problems = [];
    const why = brief.why_now || [];
    if (why.length < 2 || why.length > 3) problems.push(`rule: ${why.length} why-now sentences`);
    const items = why.map((s) => ["why_now", s]).concat([["priority", brief.priority || {}]]);
    for (const [field, item] of items) {
      const text = (item.text || "").trim();
      const cites = all(MARK, text).map((m) => Number(m[1]));
      rows.push({field: field, text: text, cites: cites, problems: checkSentence(text, cites, sources, account, readOn, tools, true, false, firstNames)});
    }
    const qs = brief.questions || [];
    if (qs.length !== 3 || !qs.every((q) => q.trim().endsWith("?"))) problems.push("rule: three questions");
    const unknowns = brief.unknowns || [];
    if (unknowns.length < 2 || unknowns.length > 4) problems.push(`rule: ${unknowns.length} unknowns`);
    for (const [field, text] of qs.map((q) => ["question", q]).concat(unknowns.map((u) => ["unknown", u])))
      rows.push({field: field, text: text, cites: [], problems: text.includes("removed]") ? ["rule: a redaction marker"] : []});
    const touch = brief.first_touch || {};
    rows.push({field: "first_touch", text: touch.body || "", cites: touch.cites || [],
      problems: checkTouch(touch, sources, account, readOn, tools, firstNames)});
    return {sentences: rows, problems: problems, ok: !problems.length && !rows.some((r) => r.problems.length)};
  }

  const api = {checkSentence: checkSentence, checkTouch: checkTouch, checkBrief: checkBrief, sentences: sentences,
    numval: numval};
  root.ASClaims = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
