import type { ReactNode } from "react";

export function PageHero({
  eyebrow,
  title,
  sub,
}: {
  eyebrow: string;
  title: ReactNode;
  sub?: string;
}) {
  return (
    <section className="relative overflow-hidden bg-ink pt-28 text-white md:pt-36">
      <div className="home-hero-overlay absolute inset-0" aria-hidden />
      <div
        className="absolute inset-0 opacity-20"
        aria-hidden
        style={{
          background:
            "radial-gradient(circle at 82% 18%, rgba(22,93,255,.55) 0, transparent 44%), radial-gradient(circle at 8% 92%, rgba(246,184,23,.4) 0, transparent 46%)",
        }}
      />
      <div className="section-shell relative z-10 grid min-h-[38svh] items-end gap-10 pb-14 md:pb-18 lg:grid-cols-[1.2fr_.8fr]">
        <div>
          <p className="eyebrow hero-line text-white/70">{eyebrow}</p>
          <h1 className="h-display hero-line mt-5 max-w-4xl text-[clamp(2.8rem,6.5vw,5.6rem)] text-white">
            {title}
          </h1>
        </div>
        {sub ? (
          <p className="hero-line max-w-xl border-t border-white/25 pt-6 text-base leading-7 text-white/70 lg:mb-2">
            {sub}
          </p>
        ) : null}
      </div>
    </section>
  );
}
