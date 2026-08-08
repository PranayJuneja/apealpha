import type { Metadata } from "next";
import { PageHero } from "@/components/page-hero";
import { SearchConsole } from "@/components/research/search-console";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Research",
  description: "Run every live source against one security.",
};

export default function ResearchPage() {
  return (
    <>
      <PageHero
        eyebrow="Live research"
        title={<>One security. Every source. Right now.</>}
        sub="Nothing is precomputed. Each query searches WebCMD X, Reddit, Google News and Yahoo News, reads filings and price, scores the distance between them, then asks GPT-5.6 Luna for the final interpretation."
      />
      <SearchConsole />
    </>
  );
}
