"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { nav, site } from "@/lib/site";

function Brand() {
  return (
    <Link href="/" className="flex items-center" aria-label="APE Alpha home">
      <span className="text-[19px] font-extrabold tracking-[-0.045em] sm:text-[21px]">
        APE <span className="font-medium text-muted">Alpha</span>
      </span>
    </Link>
  );
}

export function Nav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const pathname = usePathname();
  const [previousPathname, setPreviousPathname] = useState(pathname);
  const immersive = pathname === "/";

  if (pathname !== previousPathname) {
    setPreviousPathname(pathname);
    setOpen(false);
  }

  useEffect(() => {
    const updateHeader = () => setScrolled(window.scrollY > 24);
    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });
    return () => window.removeEventListener("scroll", updateHeader);
  }, []);

  return (
    <header
      className="site-header fixed inset-x-0 top-0 z-50 border-b border-line bg-paper/90"
      data-home={immersive}
      data-scrolled={scrolled}
      data-open={open}
    >
      <div className="site-nav-shell section-shell">
        <div className="relative flex h-[72px] items-center justify-center px-4 lg:justify-between lg:px-5">
          <Brand />
          <div className="ml-auto hidden items-center gap-5 lg:flex xl:gap-7">
            <nav className="flex items-center gap-5 xl:gap-7" aria-label="Primary navigation">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`text-[14px] font-bold tracking-[-0.02em] transition-colors ${
                    pathname === item.href ? "text-volt" : "text-ink/70 hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <Link
              href={site.researchHref}
              className="nav-cta inline-flex min-h-11 items-center gap-2 rounded-full bg-ink px-5 text-[14px] font-bold tracking-[-0.02em] text-white"
            >
              Run a ticker <span aria-hidden>↗</span>
            </Link>
          </div>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="absolute right-2.5 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-white lg:hidden"
          >
            <span className="relative block h-[15px] w-5" aria-hidden>
              <span className={`absolute left-0 top-0 h-px w-5 bg-ink transition-transform duration-200 ${open ? "translate-y-[7px] rotate-45" : ""}`} />
              <span className={`absolute left-0 top-[7px] h-px w-5 bg-ink transition-opacity duration-200 ${open ? "opacity-0" : ""}`} />
              <span className={`absolute left-0 top-[14px] h-px w-5 bg-ink transition-transform duration-200 ${open ? "-translate-y-[7px] -rotate-45" : ""}`} />
            </span>
          </button>
        </div>
        <div className="site-mobile-menu lg:hidden" aria-hidden={!open}>
          <div className="site-mobile-menu-inner">
            <nav className="grid px-5 pb-6 pt-1" aria-label="Mobile navigation">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  tabIndex={open ? 0 : -1}
                  className={`border-b border-line py-3.5 text-lg font-semibold ${pathname === item.href ? "text-volt" : ""}`}
                >
                  {item.label}
                </Link>
              ))}
              <Link href={site.researchHref} onClick={() => setOpen(false)} tabIndex={open ? 0 : -1} className="button-primary mt-5">
                Run a ticker
              </Link>
            </nav>
          </div>
        </div>
      </div>
    </header>
  );
}
