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
    <html lang="en" className={`${inter.variable} ${bodoni.variable}`}>
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
