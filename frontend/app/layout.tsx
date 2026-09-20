import type { Metadata } from "next";
import { Bodoni_Moda, Inter } from "next/font/google";
import "../styles/globals.css";
import Shell from "../components/Shell";
import { Providers } from "../components/providers";
import { CommandBar } from "../components/CommandBar";
import { BannerStack } from "../components/ui";

export const metadata: Metadata = {
  title: "StockPulse AI",
  description: "Personal Adobe Stock intelligence — single-user command center.",
};

// Typography: Inter for UI + telemetry numerals; Bodoni Moda (Didone serif)
// for hero moments only — key headlines and hero numbers.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const bodoni = Bodoni_Moda({ subsets: ["latin"], variable: "--font-bodoni", display: "swap" });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: the inline theme script below may set
    // data-theme before React hydrates; the attribute is cosmetic.
    <html lang="en" className={`${inter.variable} ${bodoni.variable}`} suppressHydrationWarning>
      <head>
        {/* Theme bootstrap — runs before first paint so there is no
            dark/light flash. Reads localStorage, falls back to the OS
            preference, defaults to dark. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('stockpulse-theme');if(t!=='dark'&&t!=='light'){t=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';}document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme='dark';}})();`,
          }}
        />
      </head>
      <body>
        <Providers>
          <BannerStack>
            <Shell>{children}</Shell>
            <CommandBar />
          </BannerStack>
        </Providers>
      </body>
    </html>
  );
}
