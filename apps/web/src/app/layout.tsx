import type { Metadata } from "next";
import { Geist_Mono, Manrope } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { site } from "@/lib/site";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

const mono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["500", "600"],
});

export const metadata: Metadata = {
  title: {
    default: "APE Alpha — Narrative arbitrage engine",
    template: "%s | APE Alpha",
  },
  description:
    "Measure whether social attention discovered a market narrative before news and price confirmed it, or long after. Research and paper trading only.",
  applicationName: site.name,
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${manrope.variable} ${mono.variable}`}>
      <body className="min-h-full">
        <Nav />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
