"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="section-shell grid min-h-[70svh] max-w-3xl content-center py-32">
      <p className="eyebrow text-muted">Something broke</p>
      <h1 className="h-display mt-5 text-[clamp(2.4rem,5vw,4rem)]">This page could not be built.</h1>
      <p className="mt-6 max-w-xl text-base leading-7 text-muted">
        The research API may be offline. Start it with <code className="tabular">npm run api</code>, then
        retry.
      </p>
      <button type="button" onClick={reset} className="button-primary mt-9 w-fit">
        Try again <span aria-hidden>→</span>
      </button>
    </main>
  );
}
