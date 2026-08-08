import Link from "next/link";
import { site } from "@/lib/site";

const linkClass =
  "inline-flex py-1 text-sm font-medium text-[#526078] transition-colors hover:text-[#101827] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#165dff]";

export function Footer() {
  return (
    <footer className="overflow-hidden border-t border-[#d9dfeb] bg-[#f1f3f8] text-[#101827]">
      <div className="section-shell">
        <div className="grid gap-12 py-16 sm:grid-cols-2 lg:grid-cols-[1.6fr_.7fr_.7fr_.9fr] lg:gap-14 lg:py-20">
          <div className="sm:col-span-2 lg:col-span-1">
            <Link
              href="/"
              className="flex w-fit items-baseline text-[clamp(2.25rem,3vw,3.25rem)] font-extrabold leading-none tracking-[-0.05em] text-[#101827]"
              aria-label="APE Alpha home"
            >
              APE <span className="ml-1.5 font-medium text-[#6f7b90]">Alpha</span>
            </Link>
            <p className="mt-5 max-w-xs text-sm leading-6 text-[#526078]">
              A narrative research engine. It measures whether attention found a story before the market
              priced it — or long after.
            </p>
          </div>

          <nav aria-label="Product links">
            <p className="eyebrow text-[#8994a6]">Product</p>
            <ul className="mt-5 space-y-1">
              <li><Link href={site.researchHref} className={linkClass}>Research a ticker</Link></li>
              <li><Link href={site.labHref} className={linkClass}>Validation lab</Link></li>
              <li><Link href={site.sourcesHref} className={linkClass}>Source health</Link></li>
            </ul>
          </nav>

          <nav aria-label="Method links">
            <p className="eyebrow text-[#8994a6]">Method</p>
            <ul className="mt-5 space-y-1">
              <li><Link href="/method" className={linkClass}>Narrative gap</Link></li>
              <li><Link href="/method#coverage" className={linkClass}>Data coverage</Link></li>
              <li><Link href="/method#limits" className={linkClass}>Known limits</Link></li>
            </ul>
          </nav>

          <div>
            <p className="eyebrow text-[#8994a6]">Status</p>
            <p className="mt-5 max-w-xs text-sm leading-6 text-[#526078]">
              Research and paper trading only. There is no live-money execution path in this system, by
              design.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-[#d9dfeb] py-7 text-xs font-medium text-[#6f7b90] sm:flex-row sm:items-center sm:justify-between">
          <p>&copy; {new Date().getFullYear()} {site.legalName}</p>
          <p>Experimental software. Historical simulation is not investment advice.</p>
        </div>
      </div>
    </footer>
  );
}
