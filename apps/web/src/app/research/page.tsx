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
        sub="Nothing is precomputed. Each query searches WebCMD Reddit, Google News and Yahoo News, then reads filings and price for that security and scores the distance between them."
      />
      <SearchConsole />
    </>
  );
}
