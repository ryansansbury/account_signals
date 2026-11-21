/* Account Signals: routing, ported from engine/route.py so a re-rank re-routes with the same rules as the build.
   Territory by the hub's region and the account's size, round robin across two seats in score order, a cap on tier A
   per seat, an overflow queue, and a first-touch deadline in business days by tier. tests/vectors/routing.json holds
   the cases both must agree on. */
(function (root) {
  "use strict";

  function regionOf(state, cfg) {
    if (!state) return cfg.remote_region;
    for (const [r, states] of Object.entries(cfg.regions)) if (states.includes(state)) return r;
    return cfg.remote_region;
  }

  function businessDays(start, n) {
    const [y, m, d] = start.split("-").map(Number);
    let t = Date.UTC(y, m - 1, d);
    while (n > 0) {
      t += 86400000;
      const wd = new Date(t).getUTCDay();
      if (wd !== 0 && wd !== 6) n--;
    }
    return new Date(t).toISOString().slice(0, 10);
  }

  function route(accounts, cfg, readOn) {
    const order = accounts.slice().sort((a, b) => (b.score - a.score) || (a.account < b.account ? -1 : a.account > b.account ? 1 : 0));
    const pointer = {}, held = {}, out = {};
    for (const a of order) {
      const segment = a.openings >= cfg.enterprise_from ? "enterprise" : "mid-market";
      const territory = regionOf(a.state, cfg) + " " + segment;
      const seats = [];
      for (let i = 1; i <= cfg.seats; i++) seats.push(territory + " " + i);
      const start = pointer[territory] || 0;
      const cap = cfg.caps[a.tier];
      let seat = null;
      for (let k = 0; k < seats.length; k++) {
        const i = (start + k) % seats.length;
        const key = seats[i] + "|" + a.tier;
        if (cap == null || (held[key] || 0) < cap) {
          seat = seats[i];
          pointer[territory] = (i + 1) % seats.length;
          held[key] = (held[key] || 0) + 1;
          break;
        }
      }
      const days = cfg.deadline_days[a.tier];
      out[a.account] = {territory: territory, seat: seat || "", overflow: seat === null,
        deadline: days ? businessDays(readOn, days) : ""};
    }
    return out;
  }

  const api = {route: route, regionOf: regionOf, businessDays: businessDays};
  root.ASRoute = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
