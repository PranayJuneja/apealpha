import { NextResponse } from "next/server";
import { ApiOffline, ApiTimeout, runResearch } from "@/lib/api";

export const dynamic = "force-dynamic";
// A cold run fans out through WebCMD Reddit/Google/Yahoo plus GDELT, EDGAR and a price provider, and a
// widely-covered name can legitimately take a while.
export const maxDuration = 150;

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

  try {
    return NextResponse.json(await runResearch(query.trim(), (market as "US" | "IN") ?? "US"));
  } catch (caught) {
    const status = caught instanceof ApiOffline ? 503 : caught instanceof ApiTimeout ? 504 : 502;
    return NextResponse.json(
      { error: caught instanceof Error ? caught.message : "Research failed." },
      { status },
    );
  }
}
