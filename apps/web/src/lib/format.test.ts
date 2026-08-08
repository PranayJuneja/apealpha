import { describe, expect, it } from "vitest";
import {
  minutesBetween,
  offsetLabel,
  percent,
  signed,
  signedPercent,
  sigma,
  sourceLabel,
  strategyLabel,
} from "./format";

describe("research formatting", () => {
  it("keeps signs and percentage scales explicit", () => {
    expect(percent(0.1234)).toBe("12.3%");
    expect(signed(2.4)).toBe("+2.40");
    expect(signed(-1)).toBe("-1.00");
    expect(signedPercent(-0.0234, 2)).toBe("-2.34%");
    expect(signedPercent(0.05)).toBe("+5.0%");
  });

  it("marks standardized values with sigma so they are never read as percentages", () => {
    expect(sigma(2.44)).toBe("+2.4σ");
    expect(sigma(-0.05)).toBe("-0.1σ");
  });

  it("maps evidence sources to readable tape labels", () => {
    expect(sourceLabel("filing")).toBe("SEC");
    expect(sourceLabel("social")).toBe("REDDIT");
    expect(sourceLabel("market")).toBe("PRICE");
    expect(sourceLabel("unknown")).toBe("UNKNOWN");
  });

  it("humanizes strategy identifiers", () => {
    expect(strategyLabel("narrative_gap_catalyst")).toBe("Narrative gap catalyst");
  });

  it("describes how far behind the first observation each event was", () => {
    const first = "2026-08-08T12:00:00Z";
    expect(minutesBetween(first, "2026-08-08T12:45:00Z")).toBe(45);
    expect(offsetLabel(0)).toBe("FIRST OBSERVED");
    expect(offsetLabel(45)).toBe("+45 MIN");
    expect(offsetLabel(150)).toBe("+2.5 HR");
    expect(offsetLabel(2880)).toBe("+2.0 DAYS");
  });
});
