/* Account Signals: the scoring, ported from engine/score.py so the page re-ranks with the same arithmetic as the build.
   Every step matches the Python: the decay factor rounded to three decimals, every point to one decimal (half away
   from zero), two signals counted per family, hiring pace up to ten postings, intent capped at 100, and the score as
   intent_share times intent plus the rest times fit. tests/vectors/scoring.json holds the cases both must agree on,
   and tests/js/check_scoring.js runs them under Node. */
(function (root) {
  "use strict";

  function roundTo(x, places) {
    const k = Math.pow(10, places);
    return Math.floor(x * k + 0.5) / k;
  }

  function dayNumber(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return Date.UTC(y, m - 1, d) / 86400000;
  }

  function isoDay(n) {
    return new Date(n * 86400000).toISOString().slice(0, 10);
  }

  function decay(age, halfLife) {
    return roundTo(Math.pow(0.5, Math.max(age, 0) / halfLife), 3);
  }

  function ageOf(posted, on, missingAge) {
    return posted ? dayNumber(on) - dayNumber(posted) : missingAge;
  }

  function signalPoints(s, on, model, points, halfLife) {
    const w = model.weights;
    const base = (points || model.points)[s.family];
    const age = ageOf(s.posted || "", on, w.missing_date_age_days);
    const d = decay(age, halfLife || w.half_life_days);
    const mult = s.temporary ? w.temporary_multiplier : 1;
    return {sid: s.sid, family: s.family, base: base, age: age, decay: d, mult: mult, points: roundTo(base * d * mult, 1)};
  }

  function byRow(a, b) {
    if (a.row.points !== b.row.points) return b.row.points - a.row.points;
    if (a.posted !== b.posted) {
      if (!a.posted) return 1;
      if (!b.posted) return -1;
      return a.posted < b.posted ? 1 : -1;
    }
    return a.row.sid < b.row.sid ? -1 : a.row.sid > b.row.sid ? 1 : 0;
  }

  function intent(signals, on, model, points, halfLife) {
    const w = model.weights;
    const by = {};
    for (const s of signals) {
      if (s.posted && s.posted > on) continue;
      if (!s.posted && on < isoDay(dayNumber(s.read_on) - w.missing_date_age_days)) continue;
      const row = signalPoints(s, on, model, points, halfLife);
      if (row.points > 0) (by[s.family] = by[s.family] || []).push({row: row, posted: s.posted || ""});
    }
    const counted = [];
    for (const fam of Object.keys(by).sort()) {
      const rows = by[fam].sort(byRow);
      const limit = fam === "pace" ? w.pace_cap : w.per_family;
      for (const r of rows.slice(0, limit)) counted.push(r.row);
    }
    let total = 0;
    for (const r of counted) total = roundTo(total + r.points, 1);
    return [Math.min(w.intent_cap, total), counted];
  }

  function fit(account, model) {
    const f = model.fit;
    const ind = f.industry.points[account.industry] || 0;
    const n = account.openings;
    const band = f.open_roles.bands.find((b) => b[0] <= n && n <= b[1]) || null;
    const roles = band ? band[2] : 0;
    const known = account.us + account.nonus;
    const share = known ? account.us / known : 0;
    const usPts = roundTo(f.us_footprint.max * share, 1);
    const rows = [{part: "industry", points: ind, industry: account.industry},
      {part: "open_roles", points: roles, openings: n, band: band ? band[3] : ""},
      {part: "us_footprint", points: usPts, us: account.us, known: known}];
    return [roundTo(ind + roles + usPts, 1), rows];
  }

  function tierOf(score, model) {
    return model.weights.tiers.find((t) => score >= t[1])[0];
  }

  function score(account, signals, model, opts) {
    opts = opts || {};
    const on = opts.on || account.read_on;
    const share = opts.intent_share == null ? model.weights.intent_share : opts.intent_share;
    const [fitTotal, fitRows] = fit(account, model);
    const [intentTotal, counted] = intent(signals, on, model, opts.points, opts.half_life);
    const total = roundTo(share * intentTotal + (1 - share) * fitTotal, 1);
    return {fit: fitTotal, intent: intentTotal, score: total, tier: tierOf(total, model), fit_rows: fitRows,
      intent_rows: counted};
  }

  function history(account, signals, model, opts) {
    opts = opts || {};
    const days = opts.days || model.weights.history_days;
    const end = dayNumber(account.read_on);
    const out = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = isoDay(end - i);
      const r = score(account, signals, model, Object.assign({}, opts, {on: d}));
      out.push([d, r.intent, r.score]);
    }
    return out;
  }

  const api = {roundTo: roundTo, decay: decay, intent: intent, fit: fit, tierOf: tierOf, score: score,
    history: history, dayNumber: dayNumber, isoDay: isoDay};
  root.ASScoring = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
