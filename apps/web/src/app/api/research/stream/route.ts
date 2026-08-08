import { NextResponse } from "next/server";
import { apiBase } from "@/lib/api";

export const dynamic = "force-dynamic";
// A cold run fans out through WebCMD Reddit/Google/Yahoo plus GDELT, EDGAR and a
// price provider, and a widely-covered name can legitimately take a while.
export const maxDuration = 150;

/** Pass the research API's NDJSON progress stream through to the browser. */
export async function POST(request: Request) {
  let query: unknown;
  let market: unknown;
  try {
    ({ query, market } = await request.json());
  } catch {
    return NextResponse.json({ error: "Request body must be JSON." }, { status: 400 });
  }

  if (typeof query !== "string" || !query.trim()) {
    return NextResponse.json({ error: "Enter a ticker or company name." }, { status: 400 });
  }
  if (query.length > 120) {
    return NextResponse.json({ error: "That query is too long." }, { status: 400 });
  }
  if (market !== undefined && market !== "US" && market !== "IN") {
    return NextResponse.json({ error: "Unsupported market." }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}/api/v1/research/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        query: query.trim(),
        market: (market as "US" | "IN") ?? "US",
        use_llm: true,
        record: true,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(145_000),
    });
  } catch {
    return NextResponse.json(
      { error: "The research API is not reachable. Start it with `npm run api` and try again." },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      { error: `The research API returned HTTP ${upstream.status}.` },
      { status: 502 },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": "application/x-ndjson",
      "cache-control": "no-store",
    },
  });
}
