import { phaseCopy } from "@/lib/site";
import type { Phase } from "@/types/research";

export function PhaseBadge({ phase }: { phase: Phase }) {
  const copy = phaseCopy[phase];
  return <span className={`phase-pill phase-${copy.tone}`}>{copy.label}</span>;
}

export function StanceBadge({ stance }: { stance: "PAPER_LONG" | "WATCH" | "STAND_ASIDE" }) {
  const tone = stance === "PAPER_LONG" ? "up" : stance === "STAND_ASIDE" ? "down" : "warn";
  const label = stance === "PAPER_LONG" ? "Paper long" : stance === "STAND_ASIDE" ? "Stand aside" : "Watch";
  return <span className={`phase-pill phase-${tone}`}>{label}</span>;
}
