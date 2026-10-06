"""Option maths: Black-Scholes Greeks, chain analytics (PCR, max pain, build-up),
strategy payoff, probability of profit and a margin estimate.

All local — inputs come from the NSE option chain, so no broker account is needed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time

SQRT2 = math.sqrt(2.0)
EXPIRY_TIME = time(15, 30)
MIN_T = 1 / (365 * 24)      # floor at one hour so expiry-day maths stays finite


def ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / SQRT2))


def npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def years_to_expiry(expiry: date, now: datetime | None = None) -> float:
    now = now or datetime.now()
    secs = (datetime.combine(expiry, EXPIRY_TIME) - now).total_seconds()
    return max(secs / (365 * 86400), MIN_T)


def greeks(spot: float, strike: float, t: float, iv_pct: float, r: float, kind: str) -> dict:
    """kind 'CE'/'PE'; iv in percent. theta per calendar day, vega per 1 IV point."""
    sigma = iv_pct / 100
    if spot <= 0 or strike <= 0 or sigma <= 0:
        return {"delta": None, "gamma": None, "theta": None, "vega": None}
    st = sigma * math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + sigma * sigma / 2) * t) / st
    d2 = d1 - st
    disc = math.exp(-r * t)
    if kind == "CE":
        delta = ncdf(d1)
        theta = -spot * npdf(d1) * sigma / (2 * math.sqrt(t)) - r * strike * disc * ncdf(d2)
    else:
        delta = ncdf(d1) - 1
        theta = -spot * npdf(d1) * sigma / (2 * math.sqrt(t)) + r * strike * disc * ncdf(-d2)
    return {
        "delta": round(delta, 3),
        "gamma": round(npdf(d1) / (spot * st), 5),
        "theta": round(theta / 365, 2),
        "vega": round(spot * npdf(d1) * math.sqrt(t) / 100, 2),
    }


# ---- chain analytics ------------------------------------------------------------------

def buildup(price_change: float | None, oi_change: float | None) -> str | None:
    if not price_change or not oi_change:
        return None
    if oi_change > 0:
        return "Long build-up" if price_change > 0 else "Short build-up"
    return "Short covering" if price_change > 0 else "Long unwinding"


def max_pain(rows: list[dict]) -> float | None:
    strikes = [r["strike"] for r in rows]
    if not strikes:
        return None
    ce = {r["strike"]: (r["ce"] or {}).get("oi") or 0 for r in rows}
    pe = {r["strike"]: (r["pe"] or {}).get("oi") or 0 for r in rows}

    def pain(k: float) -> float:
        return sum(ce[s] * max(0.0, k - s) + pe[s] * max(0.0, s - k) for s in strikes)

    return min(strikes, key=pain)


def atm_strike(rows: list[dict], spot: float) -> float | None:
    return min((r["strike"] for r in rows), key=lambda k: abs(k - spot), default=None)


def enrich_chain(chain: dict, r: float) -> dict:
    """Adds Greeks + build-up per leg and chain-level analytics."""
    rows, spot = chain["rows"], float(chain["underlying"] or 0)
    expiry = date.fromisoformat(chain["expiry"])
    t = years_to_expiry(expiry)
    atm = atm_strike(rows, spot)
    atm_row = next((x for x in rows if x["strike"] == atm), None)
    atm_ivs = [l["iv"] for l in ((atm_row or {}).get("ce"), (atm_row or {}).get("pe")) if l and l.get("iv")]
    atm_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else None

    for row in rows:
        for kind in ("CE", "PE"):
            leg = row[kind.lower()]
            if not leg:
                continue
            iv = leg.get("iv") or atm_iv
            leg.update(greeks(spot, row["strike"], t, iv, r, kind) if iv else {})
            leg["buildup"] = buildup(leg.get("change"), leg.get("oi_change"))

    ce_oi = sum((x["ce"] or {}).get("oi") or 0 for x in rows)
    pe_oi = sum((x["pe"] or {}).get("oi") or 0 for x in rows)
    ce_vol = sum((x["ce"] or {}).get("volume") or 0 for x in rows)
    pe_vol = sum((x["pe"] or {}).get("volume") or 0 for x in rows)

    def top(side: str, n: int = 3) -> list[dict]:
        ranked = sorted((x for x in rows if x[side]), key=lambda x: x[side].get("oi") or 0, reverse=True)
        return [{"strike": x["strike"], "oi": x[side]["oi"]} for x in ranked[:n]]

    chain["analytics"] = {
        "spot": spot,
        "atm": atm,
        "atm_iv": round(atm_iv, 2) if atm_iv else None,
        "pcr_oi": round(pe_oi / ce_oi, 2) if ce_oi else None,
        "pcr_volume": round(pe_vol / ce_vol, 2) if ce_vol else None,
        "max_pain": max_pain(rows),
        "total_ce_oi": ce_oi,
        "total_pe_oi": pe_oi,
        "top_ce_oi": top("ce"),       # resistance: heaviest call writing
        "top_pe_oi": top("pe"),       # support: heaviest put writing
        "days_to_expiry": round(t * 365, 1),
    }
    return chain


# ---- strategy evaluation ----------------------------------------------------------------------

@dataclass
class Leg:
    kind: str          # CE | PE
    side: str          # S | B
    strike: float
    price: float
    lots: int = 1

    @property
    def sign(self) -> int:
        return -1 if self.side == "S" else 1

    def payoff(self, s: float) -> float:
        intrinsic = max(0.0, s - self.strike) if self.kind == "CE" else max(0.0, self.strike - s)
        return self.sign * (intrinsic - self.price) * self.lots


def payoff_at(legs: list[Leg], s: float) -> float:
    """Per-share P&L at expiry (summed over lots)."""
    return sum(l.payoff(s) for l in legs)


def _lognormal_prob(spot: float, lo: float, hi: float, sigma: float, t: float, r: float) -> float:
    """P(lo < S_T < hi) under a lognormal with drift r."""
    st = sigma * math.sqrt(t)
    mu = math.log(spot) + (r - sigma * sigma / 2) * t

    def cdf(x: float) -> float:
        if x <= 0:
            return 0.0
        if math.isinf(x):
            return 1.0
        return ncdf((math.log(x) - mu) / st)

    return max(0.0, cdf(hi) - cdf(lo))


def evaluate(legs: list[Leg], spot: float, iv_pct: float | None, t: float, r: float,
             lot_size: int, margin_cfg: dict, is_index: bool) -> dict:
    if not legs:
        return {}
    strikes = sorted({l.strike for l in legs})
    # payoff is piecewise linear with kinks at strikes: evaluate at kinks and far out
    far_lo, far_hi = 0.0, max(strikes[-1], spot) * 3
    xs = [far_lo, *strikes, far_hi]
    ys = [payoff_at(legs, x) for x in xs]
    slope_up = payoff_at(legs, far_hi + 1) - ys[-1]
    unlimited_loss = slope_up < -1e-9
    unlimited_profit = slope_up > 1e-9

    max_profit = None if unlimited_profit else max(ys)
    max_loss = None if unlimited_loss else min(ys)

    breakevens = []
    for (x1, y1), (x2, y2) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if (y1 < 0 <= y2) or (y1 > 0 >= y2):
            if y2 != y1:
                breakevens.append(round(x1 + (0 - y1) * (x2 - x1) / (y2 - y1), 2))
    breakevens = sorted(set(breakevens))

    # probability of profit: integrate over intervals where payoff > 0
    pop = None
    if iv_pct:
        sigma = iv_pct / 100
        edges = [0.0, *breakevens, math.inf]
        pop = 0.0
        for lo, hi in zip(edges, edges[1:]):
            mid = (lo + hi) / 2 if not math.isinf(hi) else lo * 1.5 + 1
            if payoff_at(legs, mid) > 0:
                pop += _lognormal_prob(spot, lo, hi, sigma, t, r)
        pop = round(pop * 100, 1)

    net = -sum(l.sign * l.price * l.lots for l in legs)       # + = credit received per share
    margin = estimate_margin(legs, spot, lot_size, max_loss, margin_cfg, is_index)

    curve_x = [round(spot * (0.8 + i * 0.4 / 80), 2) for i in range(81)]
    return {
        "net_premium": round(net, 2),
        "net_premium_lot": round(net * lot_size, 2),
        "max_profit": None if max_profit is None else round(max_profit * lot_size, 2),
        "max_loss": None if max_loss is None else round(max_loss * lot_size, 2),
        "unlimited_loss": unlimited_loss,
        "breakevens": breakevens,
        "breakeven_pct": [round((b / spot - 1) * 100, 2) for b in breakevens],
        "pop": pop,
        "margin": margin,
        "risk_reward": (round(abs(max_profit / max_loss), 2)
                        if max_profit is not None and max_loss not in (None, 0) else None),
        "payoff": [{"x": x, "y": round(payoff_at(legs, x) * lot_size, 2)} for x in curve_x],
    }


def estimate_margin(legs: list[Leg], spot: float, lot_size: int, max_loss: float | None,
                    cfg: dict, is_index: bool) -> dict:
    """Rough SPAN+exposure estimate. Hedged (defined-risk) structures need roughly
    their max loss; naked shorts a % of notional. Brokers differ — treat as a guide."""
    shorts = [l for l in legs if l.side == "S"]
    if not shorts:
        premium = sum(l.price * l.lots for l in legs) * lot_size
        return {"amount": round(premium, 0), "method": "premium paid (long options only)"}
    span = cfg.get("span_pct_index" if is_index else "span_pct_stock", 12 if is_index else 18) / 100
    exposure = cfg.get("exposure_pct_index" if is_index else "exposure_pct_stock", 2 if is_index else 3.5) / 100
    naked = sum(spot * (span + exposure) * l.lots for l in shorts) * lot_size
    if max_loss is not None:
        hedged = abs(max_loss) * lot_size * (1 + cfg.get("hedged_buffer_pct", 10) / 100)
        if hedged < naked:
            return {"amount": round(hedged, 0), "method": "hedged: ≈ max loss + buffer"}
    return {"amount": round(naked, 0), "method": f"naked: ≈ {(span + exposure) * 100:.1f}% of notional"}
