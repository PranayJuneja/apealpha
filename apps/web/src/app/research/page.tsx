import type { Metadata } from "next";
import { PageHero } from "@/components/page-hero";
import { SearchConsole } from "@/components/research/search-console";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Check a stock",
  description: "Turn live market signals into one clear stock read.",
};

export default function ResearchPage() {
  return (
    <>
      <PageHero
        eyebrow="Check a stock"
        title={<>One search. The full market story.</>}
        sub="We scan live investor conversations, news, company filings, and price action—then turn the evidence into a clear sentiment and next step."
      />
      <SearchConsole />
    </>
  );
}
