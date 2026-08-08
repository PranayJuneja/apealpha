import type { ReactNode } from "react";
import { Reveal } from "./reveal";

export function SectionHeading({
  eyebrow,
  title,
  sub,
  center = false,
}: {
  eyebrow: string;
  title: ReactNode;
  sub?: string;
  center?: boolean;
}) {
  return (
    <Reveal className={center ? "text-center" : ""}>
      <p className="eyebrow text-muted">{eyebrow}</p>
      <h2 className={`h-display mt-5 text-[clamp(2.5rem,5vw,5.4rem)] ${center ? "mx-auto max-w-5xl" : "max-w-5xl"}`}>{title}</h2>
      {sub ? <p className={`mt-6 max-w-2xl text-base leading-7 text-muted ${center ? "mx-auto" : ""}`}>{sub}</p> : null}
    </Reveal>
  );
}
