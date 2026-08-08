# APE Alpha

APE Alpha measures whether social attention discovered a market narrative before
news and price confirmed it — or long after everyone had already paid for it.

You pick a market (**US** or **India**), then type a ticker, a cashtag or a
company name. The engine resolves it against that market's listing universe,
then reads Reddit, world news, filings and market bars for that specific
security, standardizes each layer, and reports the distance between them.
Nothing is precomputed.

Research and paper trading only. There is no broker integration and no code path
to one.

## Quick start

```powershell
python -m pip install -e ".\apps\api[dev]"
npm install
Copy-Item .env.example .env    # optional, see "What each key buys you"
npm run api                    # terminal 1
npm run dev                    # terminal 2
```

Open `http://localhost:3000`, pick a market and run a ticker. It works with no
credentials at all — Google News, GDELT, SEC/NSE filings and Yahoo price bars
are all keyless.

## Commands

Add `--market IN` to any research or backfill command to work on Indian
listings.

| Command | What it does |
| --- | --- |
| `npm run dev` | Next.js dashboard on port 3000 |
| `npm run api` | FastAPI research API on port 8000 |
| `npm run research -- ASTS` | One live run from the CLI, recorded to the store |
| `npm run research -- "reliance industries" --market IN` | The same for an NSE listing |
| `npm run backfill -- AAPL MSFT` | Reconstruct real historical news and price observations |
| `npm run backfill -- infosys --market IN` | Indian history, benchmarked against Nifty 50 |
| `npm run manifest` | What the point-in-time store currently holds |
| `npm run backtest` | Evaluate the fixed rules against the store |
| `npm test` | Frontend, adapter and API test suites |

## What each key buys you

Every credential is optional and disables exactly one source when absent. The
`/sources` page shows current status.

| Source | Keys | Without it |
| --- | --- | --- |
| Reddit | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | Social leg goes dark; gap metrics become partial and no paper position can be sized |
| Alpaca | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` | Price falls back to Yahoo daily bars; intraday timing is unrepresented |
| Groq | `GROQ_API_KEY` | Deterministic rule-written narrative is used instead; stance is unaffected |
| GDELT, Google News, SEC EDGAR, NSE, Yahoo | none | No setup required; a transient outage is surfaced as degraded coverage |

Reddit access requires an approved Data API application. Start from Reddit's
[official access guidance](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data), then copy the approved server-side
credentials into `.env`. Never expose the client secret to the browser.

## Markets

| | United States | India |
| --- | --- | --- |
| Resolution | SEC company-ticker file | Yahoo venue index (NSE, BSE) |
| Benchmark | S&P 500 (SPY) | Nifty 50 (`^NSEI`) |
| Filings | SEC EDGAR | NSE corporate announcements |
| News locale | `en-US` | `en-IN` — Economic Times, Moneycontrol, The Hindu |
| Currency | USD | INR |

## News sources

Two providers, kept for different reasons:

- **Google News** is the precision leg. It is region- and language-scoped, so an
  Indian listing returns Indian press. It has **no archive** — current window only.
- **GDELT** is the history leg. It supports absolute windows back to 2017 and a
  volume timeline, which is the baseline `news_z` is measured against and the
  only thing that makes a historical backfill possible.

Stories are merged and de-duplicated on headline-plus-day, so a story carried by
both providers is counted once. Yahoo's news endpoint was evaluated and rejected:
it is not ticker-scoped and returns unrelated headlines.

## Data honesty

The point-in-time store is append-only. Each observation records which sources
were actually live when it was written, and the backtest refuses to evaluate a
social-dependent rule against a row where the social leg was dark.

- **News and price history is real.** GDELT supports absolute windows back to
  2017 and market bars go back years, so `npm run backfill` reconstructs genuine
  historical observations for both legs.
- **Social history is not obtainable.** Reddit publishes no licensed deep
  archive and Pushshift is restricted to moderators. The social leg accrues
  forward from the moment you start running the engine. Backfilled rows are
  marked `origin="backfill"` with `social_coverage="unavailable"` so they can
  never be mistaken for runs that saw it.
- **An unmeasured source is never scored as zero.** If the social leg does not
  report, its z-score would be an unmeasured `0.0` — indistinguishable from a
  genuinely quiet crowd, and enough to invert the reading. The engine returns
  phase `INDETERMINATE` instead, renders the layer as unmeasured, and computes
  no narrative gap.
- **No look-ahead.** Entry is always the next bar's open. A signal cannot fill on
  the bar that produced it.
- **Returns are excess of each market's own index** — SPY for US rows, Nifty 50
  for Indian ones — over the same window and net of round-trip costs.
- **Position sizing is capped at 1% of NAV** by a rule nothing downstream can
  raise, and applies only to paper positions.

## Layout

```
apps/api/ape_alpha/
  markets.py    venue profiles — benchmark, currency, filings, subreddits
  sources/      adapters — reddit, gdelt, google_news, market, sec, nse, lookup
  research/     resolve, features, playbook, llm, engine
  store.py      append-only point-in-time snapshot store
  backfill.py   real historical reconstruction
  backtest.py   rule evaluation against the store
apps/web/src/
  app/          dashboard, research, lab, sources, method
  components/   design system and research views
plugins/ape-alpha/  WebCMD acquisition commands
```

The design system is ported from the Celron light editorial language: Manrope
and Geist Mono, paper/ink/solar/volt tokens, with two added semantic colours for
up and down states.
