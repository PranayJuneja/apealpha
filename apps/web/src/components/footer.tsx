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
              APE Alpha turns live market conversation, news, filings, and price action into a clear
              sentiment and next step.
            </p>
          </div>

          <nav aria-label="Product links">
            <p className="eyebrow text-[#8994a6]">Product</p>
            <ul className="mt-5 space-y-1">
              <li><Link href={site.researchHref} className={linkClass}>Check a stock</Link></li>
              <li><Link href={site.labHref} className={linkClass}>See the track record</Link></li>
              <li><Link href={site.sourcesHref} className={linkClass}>See live sources</Link></li>
            </ul>
          </nav>

          <nav aria-label="Method links">
            <p className="eyebrow text-[#8994a6]">Learn</p>
            <ul className="mt-5 space-y-1">
              <li><Link href="/method" className={linkClass}>How it works</Link></li>
              <li><Link href="/method#coverage" className={linkClass}>What data it checks</Link></li>
              <li><Link href="/method#limits" className={linkClass}>What it cannot know</Link></li>
            </ul>
          </nav>

          <div>
            <p className="eyebrow text-[#8994a6]">Status</p>
            <p className="mt-5 max-w-xs text-sm leading-6 text-[#526078]">
              Research and simulated plans only. APE Alpha cannot place a real trade or move your money.
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
