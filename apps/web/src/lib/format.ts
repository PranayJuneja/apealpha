export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signed(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function sigma(value: number, digits = 1): string {
  return `${signed(value, digits)}σ`;
}

export function signedPercent(value: number, digits = 1): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

export function sourceLabel(source: string): string {
  return (
    { social: "REDDIT", news: "NEWS", filing: "SEC", ir: "IR", market: "PRICE" } as Record<string, string>
  )[source] ?? source.toUpperCase();
}

export function strategyLabel(name: string): string {
  return name.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

export function utcTime(value: string): string {
  return new Date(value).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

export function utcDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  });
}

/** Includes the year. A coverage range spanning years reads as backwards without it. */
export function utcDateFull(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Minutes between two ISO timestamps, for "who knew first" offsets. */
export function minutesBetween(from: string, to: string): number {
  return Math.round((new Date(to).getTime() - new Date(from).getTime()) / 60_000);
}

export function offsetLabel(minutes: number): string {
  if (minutes <= 0) return "FIRST OBSERVED";
  if (minutes < 60) return `+${minutes} MIN`;
  if (minutes < 60 * 24) return `+${(minutes / 60).toFixed(1)} HR`;
  return `+${(minutes / 1440).toFixed(1)} DAYS`;
}
