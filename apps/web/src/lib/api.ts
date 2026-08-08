import type { Backtest, MarketCode, ResearchResult, SourceHealth } from "@/types/research";

const DEFAULT_BASE = "http://127.0.0.1:8000";

export function apiBase(): string {
  return process.env.APE_API_URL || DEFAULT_BASE;
}

export class ApiOffline extends Error {
  constructor(detail: string) {
    super(detail);
    this.name = "ApiOffline";
  }
}

export class ApiTimeout extends Error {
  constructor(detail: string) {
    super(detail);
    this.name = "ApiTimeout";
  }
}

async function call<T>(path: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (caught) {
    // A timeout and an unreachable server need different messages: telling
    // someone to start a server that is already running sends them the wrong way.
    if (caught instanceof DOMException && caught.name === "TimeoutError") {
      throw new ApiTimeout(
        `The research API did not answer within ${Math.round(timeoutMs / 1000)}s. ` +
          "Widely-covered securities can exceed that on a cold cache — try again, or try a narrower name.",
      );
    }
    throw new ApiOffline(
      "The research API is not reachable. Start it with `npm run api` and try again.",
    );
  }

  if (!response.ok) {
    let detail = `The research API returned HTTP ${response.status}.`;
    try {
      const body = await response.json();
      const raw = body?.detail;
      if (typeof raw === "string") detail = raw;
      else if (raw?.message) detail = String(raw.message);
    } catch {
      // Keep the status-code message when the body is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function runResearch(query: string, market: MarketCode = "US"): Promise<ResearchResult> {
  return call<ResearchResult>("/api/v1/research", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, market, use_llm: true, record: true }),
  });
}

export function loadSourceHealth(): Promise<{ sources: SourceHealth[] }> {
  return call<{ sources: SourceHealth[] }>("/api/v1/source-health", undefined, 6_000);
}

export function loadBacktest(): Promise<Backtest> {
  return call<Backtest>("/api/v1/backtests/latest", undefined, 10_000);
}

export function loadManifest(): Promise<Record<string, unknown>> {
  return call<Record<string, unknown>>("/api/v1/manifest", undefined, 6_000);
}
