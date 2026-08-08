export const site = {
  name: "APE Alpha",
  legalName: "APE Alpha Research",
  tagline: "Narrative arbitrage engine",
  url: "https://ape-alpha.local",
  researchHref: "/research",
  labHref: "/lab",
  sourcesHref: "/sources",
};

export const nav = [
  { label: "Check a stock", href: "/research" },
  { label: "Track record", href: "/lab" },
  { label: "Live sources", href: "/sources" },
  { label: "How it works", href: "/method" },
];

/** Listing venues the engine can research, with venue-appropriate examples. */
export const markets = [
  {
    code: "US" as const,
    label: "United States",
    short: "US",
    currency: "USD",
    benchmark: "S&P 500",
    filings: "SEC EDGAR",
    examples: ["ASTS", "Rocket Lab", "$GME", "Palantir"],
  },
  {
    code: "IN" as const,
    label: "India",
    short: "India",
    currency: "INR",
    benchmark: "Nifty 50",
    filings: "NSE announcements",
    examples: ["Reliance Industries", "Infosys", "HDFC Bank", "Zomato"],
  },
];

/** The three-layer model the whole product rests on. */
export const truthLayers = [
  { source: "Reddit", claim: "what investors are noticing" },
  { source: "News", claim: "what has been confirmed" },
  { source: "Price", claim: "what the market already knows" },
];

export const phaseCopy = {
  WHISPER: {
    label: "Whisper",
    summary: "Social attention is running ahead of broad confirmation.",
    tone: "up" as const,
  },
  CONFIRMED: {
    label: "Confirmed",
    summary: "Independent evidence has started to support the narrative.",
    tone: "up" as const,
  },
  MANIA: {
    label: "Mania",
    summary: "Attention and price are moving together. The informational edge is thin.",
    tone: "warn" as const,
  },
  EXIT_LIQUIDITY: {
    label: "Exit liquidity",
    summary: "The crowd arrived after the move. There is no long case here.",
    tone: "down" as const,
  },
  INDETERMINATE: {
    label: "Not measurable",
    summary: "The social leg did not report, so no phase can be assigned.",
    tone: "warn" as const,
  },
};
