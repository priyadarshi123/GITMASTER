import type { ReactNode } from "react";
import { Link } from "react-router-dom";

// User manual. Keep in sync with the app when features or rules change
// (signal rule: backend/signals.py; thresholds: config/settings.yaml).

const TOC: [string, string][] = [
  ["what", "What this portal is"],
  ["workflow", "The 4-step workflow"],
  ["dashboard", "Step 1 — Dashboard (signal grid)"],
  ["analysis", "Step 2 — Analysis page"],
  ["builder", "Step 3 — Option chain & position builder"],
  ["oi", "OI analytics"],
  ["positions", "Step 4 — Positions & ROI"],
  ["playbook", "Strategy playbook"],
  ["risk", "Risk management rules"],
  ["routine", "Daily / weekly routine"],
  ["data", "Data sources, refresh & limits"],
  ["settings", "Changing settings"],
  ["glossary", "Glossary"],
  ["faq", "FAQ"],
];

export default function GuidePage() {
  return (
    <div className="grid lg:grid-cols-[220px_1fr] print:block gap-8 max-w-6xl mx-auto">
      <nav className="no-print hidden lg:block">
        <div className="sticky top-4 space-y-1 text-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Contents</div>
          {TOC.map(([id, title]) => (
            <a key={id} href={`#${id}`} className="block px-2 py-1 rounded text-slate-600 hover:bg-white hover:text-slate-900">
              {title}
            </a>
          ))}
          <button onClick={() => window.print()} className="mt-4 w-full px-3 py-2 rounded-lg bg-ink text-white text-sm">
            ⎙ Save as PDF
          </button>
        </div>
      </nav>

      <article className="space-y-6 text-[15px] leading-relaxed text-slate-700 min-w-0">
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <h1 className="text-2xl font-semibold text-slate-900">User guide</h1>
          <p className="mt-2">
            How to use the Option Dashboard: what each screen shows, how the signals are calculated, and a
            practical playbook for selling option spreads on Nifty 50 stocks and NSE indices.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Everything here is a research aid, not advice. Option selling can lose much more than the premium
            you collect. Paper-trade first.
          </p>
        </div>

        <Section id="what" title="What this portal is">
          <p>
            The portal helps you <b>sell option premium with defined risk</b>. It scans the indices and Nifty 50 stocks
            in your watchlist, tells you which direction is safer to sell against (using weekly and daily RSI),
            checks the chart for reasons the trend might reverse, and then helps you pick strikes, size the trade,
            and track it until it closes.
          </p>
          <p>The idea in one line: <b>sell options on the side the market is moving away from, beyond a support or
            resistance level, 5–12% from the current price, with a hedge so the loss is capped.</b></p>
          <p>You make money when the stock stays below your sold call / above your sold put until expiry, as the
            option premium decays to zero.</p>
          <Callout>
            <b>Every number has a small ⓘ icon.</b> Hover (or tap) it to see where the data comes from, when it was last
            fetched, and exactly how it is calculated.
          </Callout>
        </Section>

        <Section id="workflow" title="The 4-step workflow">
          <Steps items={[
            <><b>Pick</b> — on the <Link className="link" to="/">Dashboard</Link>, filter for a clean signal (Bear Call,
              Bull Put or Iron Condor) with no results before expiry, and select a few names.</>,
            <><b>Analyse</b> — press <i>Analyse selected</i>. Check the chart summary, reversal confluence and
              the support/resistance (S/R) chart for each stock.</>,
            <><b>Build</b> — in the option chain, press <i>Suggest strikes</i> or pick your own with the S/B buttons. Make the
              validation checklist green and keep the margin inside the cap.</>,
            <><b>Track</b> — press <i>Record position</i> (real) or <i>Paper trade</i>. Watch the % of stop used on the
              <Link className="link" to="/positions/real"> Positions</Link> page and close when your rules say so.</>,
          ]} />
        </Section>

        <Section id="dashboard" title="Step 1 — Dashboard (signal grid)">
          <p>One card per instrument in your watchlist (indices first, then stocks roughly by Nifty 50 weight).</p>
          <Table head={["On the card", "Meaning"]} rows={[
            ["Price & % change", "Last price and change vs previous close (Yahoo, ~15 min delayed; indices FINNIFTY/MIDCPNIFTY from NSE)."],
            ["Sector chip", "Sector, used for filtering and for the sector-context chart."],
            ["Signal chip", "The suggested structure from the RSI rule below."],
            ["W:xx D:xx", "Weekly and daily RSI(14)."],
            ["R / A / D / B badge", "Corporate event between today and the next monthly expiry: R = results, A = AGM/EGM, D = dividend, B = bonus/split. Hover to see date and purpose."],
            ["✎n", "Number of notes you've written for this stock."],
            ["☆ / ★", "Add to / remove from your watchlist (use the ★ Watchlist filter)."],
            ["Circle (right)", "Selected for analysis. Click anywhere on the card to toggle."],
          ]} />
          <h3>How the signal is decided</h3>
          <p>RSI zones: <b>below 40 = bearish</b>, <b>above 60 = bullish</b>, <b>40–60 = neutral</b>. The <b>daily</b> RSI
            triggers the trade; the <b>weekly</b> RSI must not point the other way.</p>
          <Table head={["Daily RSI", "Weekly RSI", "Signal", "What you'd sell"]} rows={[
            ["< 40", "< 60 (bearish or neutral)", <Chip c="red">Bear Call</Chip>, "Call spread above the market"],
            ["> 60", "> 40 (bullish or neutral)", <Chip c="green">Bull Put</Chip>, "Put spread below the market"],
            ["40–60", "40–60", <Chip c="blue">Iron Condor</Chip>, "Both — a call spread above and a put spread below"],
            ["anything else", "", <Chip c="amber">Wait for confirmation</Chip>, "Nothing yet — weekly is trending but daily hasn't confirmed, or they disagree"],
          ]} />
          <h3>Filters</h3>
          <ul>
            <li><b>Events</b> — <i>No events</i> is the safest starting point; results days cause gaps that can jump past your strikes.</li>
            <li><b>Signals</b> — show only one structure.</li>
            <li><b>Sector chips</b> — avoid putting all trades in one sector.</li>
            <li><b>★ Watchlist</b> — only the stocks you starred.</li>
          </ul>
          <p>The <b>"signals as of HH:MM"</b> stamp shows when data was last refreshed. <b>Refresh now</b> (top right) fetches new
            data; if the last refresh was under 2 minutes ago it simply shows the cached data.</p>
        </Section>

        <Section id="analysis" title="Step 2 — Analysis page">
          <p>One tab per selected symbol. Use the <b>Candle / Line</b> toggle (top right) for all price charts.</p>
          <h3>Header & chart summary</h3>
          <ul>
            <li><b>Weekly / Daily rows</b> — RSI value, which zone rule it meets, and the verdict (Bearish / Neutral / Bullish).</li>
            <li><b>BB weekly / BB daily</b> — Bollinger Bands (20-period, 2 standard deviations): upper, middle, lower and their %
              distance from the current price (CMP). The bands are a natural "stretch" limit — strikes outside the weekly band are
              statistically harder to reach.</li>
            <li><b>Prev month</b> — last month's high and low. These often act as support/resistance.</li>
            <li><b>Confluence x/3</b> — how many reversal checks are firing (see below).</li>
          </ul>
          <h3>RSI charts</h3>
          <p>Weekly RSI (3 years) and daily RSI (2 years) with the 40 and 60 lines. Look at where RSI turned in the past — if the
            weekly has bounced from ~30 several times, a fresh Bear Call near 30 carries more reversal risk.</p>
          <h3>Reversal confluence</h3>
          <p>Three independent checks for signs the current move is ending. Each shows ✓ (active) or ✕:</p>
          <Table head={["Check", "Fires when"]} rows={[
            ["Bollinger Bands", "A daily close at/below the lower band (bullish exhaustion) or at/above the upper band (bearish exhaustion) in the last 3 sessions."],
            ["RSI divergence", "Price made a lower low but RSI made a higher low (bullish), or price made a higher high but RSI a lower high (bearish) — within the last 20 bars. Older divergences are counted but don't fire."],
            ["Candlestick", "A quality reversal candle (hammer, shooting star, engulfing, morning/evening star, piercing, dark cloud) in the last 10 days, after a move and near the outer band."],
          ]} />
          <p><b>How to use it:</b> 0/3 = the trend is intact, sell with the signal. 1/3 = be a little more conservative (further
            strikes). <b>2–3/3 pointing against your trade = skip it or wait.</b> Example: a Bear Call with a 2/3 bullish reversal means
            the stock may bounce into your short call.</p>
          <p><b>Squeeze banner</b> — when the Bollinger Bands move inside the Keltner Channels, volatility is compressed ("squeeze ON");
            when they burst back out, the squeeze has <b>FIRED</b> and a large move usually follows. After a fired squeeze, place short
            strikes further away and size smaller.</p>
          <p>The <b>What this means</b> box summarises the above in plain English.</p>
          <h3>Sector context</h3>
          <p>Monthly candles of the sector index (e.g. Nifty Oil & Gas for RELIANCE) with Bollinger Bands. Selling a Bear Call is more
            comfortable when the sector is also weak; be careful if the sector is strong while the stock is weak.</p>
          <h3>S/R analysis chart</h3>
          <ul>
            <li><b>Levels</b> come from swing highs/lows on daily, weekly and monthly charts, merged when within 0.3%.
              <b> Solid line</b> = touched 2+ times, <b>thick</b> = seen on more than one timeframe (stronger). Only levels within 12% of
              CMP are drawn; single-touch levels are listed in the legend (click a legend row to show/hide it).</li>
            <li><b>Shaded 5–12% zone</b> — the option-selling zone above and below CMP.</li>
            <li><b>Prev-month high/low</b> lines, <b>CMP</b> line, Bollinger Bands, and <b>unfilled gaps</b> ≥1.5% (shaded boxes —
              price often comes back to fill them).</li>
            <li><b>Your strikes</b> from the builder are drawn too (magenta = calls, cyan = puts) so you can see whether a level sits
              between the price and your short strike.</li>
            <li>Toggles: Daily / Weekly / Monthly candles, 2Y / 5Y history (levels are recomputed), zone on/off, all levels on/off.
              <i> Turning points</i> lists the dates each level was touched.</li>
          </ul>
          <h3>Notes & PDF</h3>
          <p>Keep a dated journal per stock ("results on 7th — trade after"). The dashboard shows a ✎ count. <b>Save as PDF</b> prints the
            whole analysis.</p>
        </Section>

        <Section id="builder" title="Step 3 — Option chain & position builder">
          <p>Live NSE option chain for the chosen expiry (stocks: monthly; indices: weekly + monthly). Columns per strike, calls on the
            left and puts on the right: <b>OI</b>, <b>ΔOI</b> (change today), <b>IV</b>, <b>Δ</b> (delta), <b>LTP</b>, and
            <b className="text-red-600"> S</b>/<b className="text-emerald-600">B</b> buttons. Purple strikes are inside the 5–12% zone; amber
            cells are in-the-money; the ATM row is outlined.</p>
          <h3>Building a trade</h3>
          <Steps items={[
            <><b>Validate as</b> — pick the structure (defaults to the RSI signal).</>,
            <><b>Suggest strikes</b> — the portal sells the first strike just beyond the nearest S/R level inside the 5–12% zone with
              delta ≤ 0.30, and buys a hedge two strikes further out. Treat it as a starting point.</>,
            <>Or click <b>S</b> on a premium to sell it and <b>B</b> to buy a hedge. Click again to remove. Edit price and lots in the legs panel.</>,
            <>Read the results: <b>net credit</b>, <b>max profit</b> (= credit), <b>max loss</b>, <b>breakeven(s)</b>, <b>POP</b>
              (probability of profit at expiry), <b>estimated margin</b> vs your cap, and the <b>payoff chart</b>.</>,
            <>Work through the <b>validation checklist</b> until it's green: matches the signal · each short leg hedged · short strikes in
              the 5–12% zone · short delta ≤ 0.30 · a support/resistance level between CMP and your short strike · margin within cap ·
              no event before expiry.</>,
            <>Press <b>Record position →</b> (real) or <b>Paper trade →</b> to carry the legs to Positions.</>,
          ]} />
          <Callout>
            Margin shown is an <b>estimate</b> (hedged spread ≈ max loss + 10%; naked short ≈ SPAN + exposure % of notional). Your
            broker's number will differ — check it before placing the order. Greeks and POP are model values (Black-Scholes on NSE IV).
          </Callout>
        </Section>

        <Section id="oi" title="OI analytics">
          <p>OI is shown in the same view as the chain: a summary strip above the table, and an OI bar on every strike row
            (calls grow left from the strike, puts grow right; darker bars are the call/put walls; ◆ marks max pain). Switch the
            bars between <b>Open interest</b> and <b>Change in OI</b>.</p>
          <Table head={["Item", "How to read it"]} rows={[
            ["PCR (OI)", "Put OI ÷ call OI. Below 0.7 = call-heavy (writers expect a cap above → bearish tilt). Above 1.3 = put-heavy (support below → bullish tilt). In between = balanced."],
            ["PCR (volume)", "Same ratio on today's traded volume — a faster, noisier read."],
            ["Max pain", "The strike where option buyers lose the most at expiry; price often drifts toward it in the last days."],
            ["ATM IV", "Implied volatility at the money. Higher IV = richer premiums but bigger expected moves."],
            ["Call wall / Put wall", "Strikes with the highest call / put OI — option writers' resistance and support. Placing your short strike beyond a wall adds protection."],
            ["OI bars (in the chain)", "Calls left (red), puts right (green) on each strike row. Switch to Change in OI to see where fresh positions were added today. Hover a bar for its build-up type."],
          ]} />
          <p><b>Build-up types</b> (price change + OI change): Long build-up (↑ price, ↑ OI), Short build-up (↓ price, ↑ OI),
            Short covering (↑ price, ↓ OI), Long unwinding (↓ price, ↓ OI).</p>
        </Section>

        <Section id="positions" title="Step 4 — Positions & ROI">
          <p>Two books: <b>Real</b> (your actual trades) and <b>Paper</b> (practice). Both work the same way.</p>
          <h3>Recording</h3>
          <ul>
            <li>Arrives prefilled from the builder, or click <b>+ New position</b>, type a symbol and <b>Load expiries & suggest</b>
              (fills expiry and lot size, and prefills the recommended strikes with live premiums). Changing the
              strategy refills the legs for that strategy; changing a strike fetches its premium. A price that looks like a strike is
              flagged and blocks saving.</li>
            <li>Enter <b>lots</b>, <b>capital</b> and <b>risk % per trade</b>, choose a <b>stop rule</b>, check the legs, and Save.</li>
            <li>The readout shows the net credit and the loss at your stop, and warns if that exceeds capital × risk %.</li>
          </ul>
          <h3>Stop rules</h3>
          <Table head={["Rule", "Stop is hit when"]} rows={[
            ["1:1 — 1× credit", "Your loss equals the credit received (tight)."],
            ["1:2 — 2× credit", "Loss = 2× the credit."],
            ["1:3 — 3× credit", "Loss = 3× the credit (default; gives the trade room)."],
            ["Strike breach", "The underlying comes within 0.5% of a short strike, regardless of P&L."],
          ]} />
          <h3>Open position cards</h3>
          <ul>
            <li><b>P&L</b> (live from the NSE chain) and per-leg P&L.</li>
            <li><b>% of stop used</b> bar — green → amber (50%) → orange (80%) → red (100%). The card border turns red at 95%.</li>
            <li><b>POP now / at entry</b> — if POP has dropped more than 10 points, it turns red: the trade has moved against you.</li>
            <li>Breakevens, margin, spot and its move since entry, and how far the nearest short strike is.</li>
            <li><b>Close</b> (enter realised P&L — prefilled with current P&L), <b>Close legs</b> (exit one side of an Iron Condor; credit,
              max loss and stop are recalculated for what's left), <b>Edit entry</b>, <b>Delete</b>.</li>
          </ul>
          <p>Tags: <b>LIVE</b> during market hours, <b>AS OF CLOSE</b> after 15:30 and at weekends, <b>AT PREV CLOSE</b> before 09:15.</p>
          <h3>ROI</h3>
          <p>Monthly and annual tables: margin used, realised (positions closed that month), unrealised (open positions, counted in the
            current month), total, and <b>ROI = total ÷ margin</b>. Brokerage and taxes are not included.</p>
        </Section>

        <Section id="playbook" title="Strategy playbook">
          <Callout>
            These are commonly used guidelines that fit the portal's checks — not guarantees. Adapt them to your own risk tolerance
            and test on the Paper book first.
          </Callout>
          <h3>Bear Call spread — when the signal is Bear Call</h3>
          <ul>
            <li><b>Sell</b> a call 5–12% above CMP, beyond the nearest resistance level (ideally also beyond the call wall or the weekly upper BB).</li>
            <li><b>Buy</b> a higher call (1–3 strikes further) as the hedge — this caps your loss.</li>
            <li>Profit if the stock stays below the short call at expiry. Max profit = credit; max loss = strike gap − credit.</li>
            <li>Avoid if reversal confluence is 2/3+ bullish, or a results date falls before expiry.</li>
          </ul>
          <h3>Bull Put spread — when the signal is Bull Put</h3>
          <ul>
            <li><b>Sell</b> a put 5–12% below CMP, beyond the nearest support (ideally beyond the put wall / weekly lower BB).</li>
            <li><b>Buy</b> a lower put as the hedge.</li>
            <li>Profit if the stock stays above the short put. Avoid if reversal confluence is 2/3+ bearish.</li>
          </ul>
          <h3>Iron Condor — when the signal is Iron Condor (both RSIs 40–60)</h3>
          <ul>
            <li>A Bear Call above <b>and</b> a Bull Put below, same expiry. You collect two credits; only one side can lose at expiry.</li>
            <li>Best when the stock is range-bound: price near the BB middle, no squeeze firing, PCR balanced.</li>
            <li>If one side is threatened, close that side with <b>Close legs</b> and keep the other.</li>
          </ul>
          <h3>Wait for confirmation</h3>
          <p>Don't force a trade. Revisit in a few days — the daily RSI often catches up with the weekly.</p>
          <h3>Choosing strikes — quick checklist</h3>
          <Steps items={[
            "5–12% from CMP (purple strikes in the chain).",
            "At least one drawn S/R level between CMP and your short strike.",
            "Short-strike delta ≤ 0.30 (roughly ≤ 30% chance of finishing in the money).",
            "Beyond the call/put wall if possible.",
            "Credit worth the risk — as a rough guide, credit of at least ~15–20% of the strike gap.",
            "Margin within 20% of capital; loss at stop within your risk % per trade.",
          ]} />
          <h3>Managing the trade (common practice)</h3>
          <ul>
            <li><b>Take profit early</b> — many sellers close at 50–70% of max profit rather than holding to expiry.</li>
            <li><b>Respect the stop</b> — when % of stop used reaches 100% (or the strike-breach stop fires), exit; don't hope.</li>
            <li><b>Watch events</b> — close or avoid positions over results days.</li>
            <li><b>Expiry week</b> — gamma risk rises sharply; consider closing a few days before expiry if the short strike is close.</li>
          </ul>
        </Section>

        <Section id="risk" title="Risk management rules">
          <ul>
            <li><b>Margin cap:</b> each position's margin ≤ 20% of capital (default capital ₹1,00,000 → cap ₹20,000).</li>
            <li><b>Risk per trade:</b> loss at stop ≤ capital × risk % (default 1%).</li>
            <li><b>Always hedge:</b> a naked short option has unlimited loss — the builder flags it.</li>
            <li><b>Diversify:</b> spread trades across sectors and directions; don't open five Bear Calls in one sector.</li>
            <li><b>Paper first:</b> run the Paper book for a few expiries before trading real money.</li>
          </ul>
        </Section>

        <Section id="routine" title="Daily / weekly routine">
          <Table head={["When", "What to do"]} rows={[
            ["Before 09:15", "Positions shows AT PREV CLOSE values. Review notes and any events today."],
            ["After the open (~09:30+)", "Refresh. Check Positions — anything above 50% of stop? Any short strike within ~2%?"],
            ["Entry days", "Dashboard → filter No events + a signal → Analyse 3–5 names → build, validate, record."],
            ["Intraday", "Data refreshes every 15 min automatically; use Refresh now when needed."],
            ["After 15:30", "AS OF CLOSE values. Update notes; close or adjust per your rules."],
            ["Month end", "Check the ROI table; review closed trades and what worked."],
          ]} />
        </Section>

        <Section id="data" title="Data sources, refresh & limits">
          <Table head={["Data", "Source", "Delay"]} rows={[
            ["Stock, NIFTY, BANKNIFTY candles & prices", "Yahoo Finance (free)", "~15 min"],
            ["Option chains, OI, IV, expiries, lot sizes", "NSE website (free)", "~1–3 min; cached 60 s"],
            ["FINNIFTY, MIDCPNIFTY, sector indices", "NSE website", "end of day + live index board"],
            ["Corporate events (R/A/D/B)", "NSE event calendar & corporate actions", "once a day"],
            ["Greeks, POP, margin, S/R, signals", "Calculated by the portal", "—"],
          ]} />
          <ul>
            <li><b>Auto-refresh</b> every 15 minutes during market hours (09:15–15:30), plus once after the close.</li>
            <li><b>Optional Angel One</b> — add SmartAPI keys to <code>.env</code> for live prices (and, later, exact margins).</li>
            <li><b>Limits:</b> margins are estimates; Greeks/POP are model values; P&L excludes charges; NSE may block cloud servers,
              so a VPS setup may need Angel One.</li>
          </ul>
        </Section>

        <Section id="settings" title="Changing settings">
          <p>Two plain-text files in the <code>OPTIONDASHBOARD/config</code> folder (changes apply on the next refresh):</p>
          <Table head={["File", "What you can change"]} rows={[
            ["watchlist.yaml", "Which indices/stocks are tracked (enabled: true/false), their order, sector and number of expiries. Fewer symbols = fewer data calls."],
            ["settings.yaml", "RSI period and the 40/60 thresholds, refresh interval, default capital, margin cap %, risk % per trade, margin-estimate percentages, sector-index mapping."],
          ]} />
        </Section>

        <Section id="glossary" title="Glossary">
          <Table head={["Term", "Meaning"]} rows={[
            ["CMP", "Current market price of the stock or index."],
            ["CE / PE", "Call option / put option."],
            ["Strike", "The price at which the option can be exercised."],
            ["OTM / ITM / ATM", "Out of / in / at the money. A call is OTM when its strike is above CMP; a put when below."],
            ["Premium / LTP", "The option's price (last traded price)."],
            ["Credit spread", "Sell one option and buy a further-OTM one: you receive a net credit and your loss is capped."],
            ["Hedge", "The bought option in a spread that limits loss."],
            ["Lot size", "Number of shares per contract (e.g. RELIANCE 500). P&L = price change × lot size × lots."],
            ["RSI", "Relative Strength Index (0–100), a momentum gauge. Below 40 weak, above 60 strong (portal thresholds)."],
            ["Bollinger Bands", "A 20-period average ± 2 standard deviations; marks how stretched price is."],
            ["Keltner Channel / squeeze", "An ATR-based channel; Bollinger Bands inside it = squeeze (low volatility before a big move)."],
            ["Support / resistance", "Price levels where the stock has turned before."],
            ["OI", "Open interest — number of outstanding contracts."],
            ["PCR", "Put-call ratio of OI (or volume)."],
            ["Max pain", "Strike where option holders lose the most at expiry."],
            ["IV", "Implied volatility — the market's expected annualised move, priced into premiums."],
            ["Delta", "How much the option price moves per ₹1 move in the stock; also a rough probability of expiring ITM."],
            ["POP", "Probability of profit at expiry, from a lognormal model using IV."],
            ["Breakeven", "The underlying price at expiry where the trade makes zero."],
            ["Margin", "Money the broker blocks to hold the position."],
            ["Expiry", "Last trading day of the contract (NSE monthly: last Tuesday, shifted for holidays)."],
          ]} />
        </Section>

        <Section id="faq" title="FAQ">
          <Faq q="Why are prices different from my broker?">Prices come from free sources: Yahoo is ~15 minutes delayed and NSE ~1–3 minutes.
            Always confirm the live premium in your broker before placing an order.</Faq>
          <Faq q="The option chain says 'unavailable'.">NSE occasionally rate-limits or blocks requests. Wait a minute and press ↻. On a
            cloud server NSE may block access entirely.</Faq>
          <Faq q="Why is the margin different from my broker's?">The portal estimates margin. Brokers use exact SPAN files and their own
            add-ons. Treat the portal figure as a guide.</Faq>
          <Faq q="A stock I want isn't on the dashboard.">Add it to <code>config/watchlist.yaml</code> (it must be in NSE F&O) and press Refresh now.</Faq>
          <Faq q="Can I trade from the portal?">No — it's for analysis and tracking. Place orders in your broker, then record them here.</Faq>
          <Faq q="What does 'Wait for confirmation' mean?">Weekly and daily RSI don't agree yet. Skip the stock for now.</Faq>
        </Section>

        <p className="text-xs text-slate-400 text-center pb-4">
          Market data and analytics for personal research only — not investment advice. Consult a SEBI-registered adviser before
          investing. Derivatives carry substantial risk.
        </p>
      </article>
    </div>
  );
}

// ---- building blocks ------------------------------------------------------------------

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="guide bg-white border border-slate-200 rounded-xl p-6 scroll-mt-4 break-inside-avoid-page">
      <h2 className="text-lg font-semibold text-slate-900 mb-3">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>{head.map((h) => <th key={h} className="text-left font-semibold text-slate-600 bg-slate-50 px-3 py-2 border-b border-slate-200">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="align-top">
              {r.map((c, j) => <td key={j} className={`px-3 py-2 border-b border-slate-100 ${j === 0 ? "font-medium text-slate-800 whitespace-nowrap" : ""}`}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Steps({ items }: { items: ReactNode[] }) {
  return (
    <ol className="space-y-2">
      {items.map((it, i) => (
        <li key={i} className="flex gap-3">
          <span className="shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-semibold grid place-items-center">{i + 1}</span>
          <span>{it}</span>
        </li>
      ))}
    </ol>
  );
}

function Callout({ children }: { children: ReactNode }) {
  return <div className="border-l-4 border-amber-400 bg-amber-50 rounded-r-lg px-4 py-3 text-sm text-amber-900">{children}</div>;
}

const CHIP = { red: "bg-red-50 text-red-700", green: "bg-emerald-50 text-emerald-700", blue: "bg-blue-50 text-blue-700", amber: "bg-amber-50 text-amber-800" };
function Chip({ c, children }: { c: keyof typeof CHIP; children: ReactNode }) {
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${CHIP[c]}`}>{children}</span>;
}

function Faq({ q, children }: { q: string; children: ReactNode }) {
  return (
    <details className="border border-slate-200 rounded-lg px-4 py-2" open>
      <summary className="cursor-pointer font-medium text-slate-800">{q}</summary>
      <p className="mt-1 text-sm">{children}</p>
    </details>
  );
}
