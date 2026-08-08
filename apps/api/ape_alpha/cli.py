from __future__ import annotations

import argparse
import asyncio
import json

from .backfill import backfill_ticker
from .backtest import persist_backtest, run_backtest
from .repository import project_root
from .research.engine import research
from .store import append_snapshots, read_manifest, row_from_result


async def _run(args: argparse.Namespace) -> None:
    root = project_root()

    if args.command == "research":
        result = await research(args.query, market=args.market, use_llm=not args.no_llm)
        append_snapshots(root, [row_from_result(result)])
        print(result.model_dump_json(indent=2))
        return

    if args.command == "backfill":
        for query in args.queries:
            summary = await backfill_ticker(
                root, query, market=args.market, lookback_days=args.lookback_days
            )
            print(json.dumps(summary, indent=2))
        return

    if args.command == "manifest":
        print(json.dumps(read_manifest(root), indent=2))
        return

    run = await run_backtest(root, locked=args.locked)
    output = persist_backtest(root, run)
    print(run.model_dump_json(indent=2))
    print(f"Saved {output}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ape-alpha")
    subparsers = parser.add_subparsers(dest="command", required=True)

    research_parser = subparsers.add_parser("research", help="Run live research for one query")
    research_parser.add_argument("query", help="Ticker, cashtag or company name")
    research_parser.add_argument("--no-llm", action="store_true", help="Skip the Groq narrative layer")
    research_parser.add_argument("--market", choices=["US", "IN"], default="US", help="Listing venue")

    backfill_parser = subparsers.add_parser("backfill", help="Reconstruct real news and price history")
    backfill_parser.add_argument("queries", nargs="+", help="One or more tickers or company names")
    backfill_parser.add_argument("--lookback-days", type=int, default=365)
    backfill_parser.add_argument("--market", choices=["US", "IN"], default="US", help="Listing venue")

    subparsers.add_parser("manifest", help="Show what the point-in-time store holds")

    backtest_parser = subparsers.add_parser("backtest", help="Evaluate rules against the store")
    backtest_parser.add_argument("--locked", action="store_true", help="Include the held-out tail")

    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
