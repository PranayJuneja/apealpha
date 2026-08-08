# APE Alpha

APE Alpha measures whether social attention discovered a market narrative before
news and price confirmed it — or long after everyone had already paid for it.

You pick a market (**US** or **India**), then type a ticker, a cashtag or a
company name. The engine resolves it against that market's listing universe,
then asks WebCMD for current X, Reddit, Google News and Yahoo News evidence, reads
filings and market bars for that specific security, standardizes each layer,
and reports the distance between them. Nothing is precomputed.

Research and paper trading only. There is no broker integration and no code path
to one.

## Quick start

```powershell
python -m pip install -e ".\apps\api[dev]"
npm install
npm install -g @agentrhq/webcmd
npm run webcmd:setup:arm64  # Windows ARM64 only; installs a checksum-verified x64 Node runtime
npm run webcmd -- reddit login
npm run webcmd -- reddit whoami
npm run webcmd -- twitter login
npm run webcmd -- twitter whoami
Copy-Item .env.example .env    # optional, see "What each key buys you"
npm run api                    # terminal 1
npm run dev                    # terminal 2
```

Open `http://localhost:3000`, pick a market and run a ticker. X and Reddit use the
one-time WebCMD logins above; no social API approval is required. Google News,
Yahoo News, GDELT, SEC/NSE filings and Yahoo price bars are keyless.

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
| `npm run webcmd -- reddit whoami` | Verify the Reddit session used by live research |
| `npm run webcmd -- twitter whoami` | Verify the X session used by live research |
| `npm run webcmd -- ape-alpha yahoo-news "Palantir Technologies" --ticker PLTR` | Inspect normalized Yahoo news directly |
| `npm test` | Frontend, adapter and API test suites |

## What each key buys you

Every credential is optional and disables exactly one source when absent. The
`/sources` page shows current status.

| Source | Keys | Without it |
| --- | --- | --- |
| WebCMD Reddit session | no key; `npm run webcmd -- reddit login` | Social leg goes dark; gap metrics become partial and no paper position can be sized |
| WebCMD X session | no key; `npm run webcmd -- twitter login` | Reddit can keep social coverage live, but X posts are absent and disclosed |
| Reddit API fallback | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | Nothing if WebCMD Reddit is healthy; these are optional fallback credentials |
| Alpaca | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` | Price falls back to Yahoo daily bars; intraday timing is unrepresented |
| OpenAI GPT-5.6 Luna | `OPENAI_API_KEY` | Deterministic narrative and final understanding are used; stance and metrics are unaffected |
| WebCMD Google/Yahoo News, GDELT, SEC EDGAR, NSE, Yahoo bars | none | No setup required; a transient outage is surfaced as degraded coverage |

The normal pathway does not wait for social API approval: WebCMD searches
through the X and Reddit account sessions you authorize interactively. It never automates a
password, OTP or CAPTCHA, and the application never receives the session
cookie. If approved later, Reddit's
[official access guidance](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)
can be used to configure the optional server-side OAuth fallback.

## Markets

| | United States | India |
| --- | --- | --- |
| Resolution | SEC company-ticker file | Yahoo venue index (NSE, BSE) |
| Benchmark | S&P 500 (SPY) | Nifty 50 (`^NSEI`) |
| Filings | SEC EDGAR | NSE corporate announcements |
| News locale | `en-US` | `en-IN` — Economic Times, Moneycontrol, The Hindu |
| Currency | USD | INR |

## News sources

Three providers, kept for different reasons:

- **Google News through WebCMD** is the locale-aware current-news precision leg,
  so an Indian listing returns Indian press. It has **no archive** — current
  window only.
- **Yahoo News through WebCMD** is a second current-news leg. Rows must mention
  the resolved ticker/company in the headline; broad market stories are not
  counted just because Yahoo associates the ticker in hidden metadata.
- **GDELT** is the history leg. It supports absolute windows back to 2017 and a
  volume timeline, which is the baseline `news_z` is measured against and the
  only thing that makes a historical backfill possible.

Stories are merged and de-duplicated on headline-plus-day, so a story carried by
multiple providers is counted once. Google or Yahoo can fail independently; the
coverage line records exactly which WebCMD commands answered on that run.

## Data honesty

The point-in-time store is append-only. Each observation records which sources
were actually live when it was written, and the backtest refuses to evaluate a
social-dependent rule against a row where the social leg was dark.

- **News and price history is real.** GDELT supports absolute windows back to
  2017 and market bars go back years, so `npm run backfill` reconstructs genuine
  historical observations for both legs.
- **Social history is not obtainable.** The connected X and Reddit surfaces do
  not provide the licensed deep archive required for reconstruction. The social leg accrues
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
  sources/      adapters — WebCMD X/Reddit/news, GDELT, market, SEC, NSE, lookup
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
