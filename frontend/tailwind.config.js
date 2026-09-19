/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./services/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Precision-instrument design system (2026-09-19 restyle).
        // Champagne gold is the single restrained accent; F1 racing red
        // (status.danger) is reserved strictly for alerts / live / critical.
        bg: { primary: "#0A0A0C", secondary: "#0D0D10" },
        surface: { base: "#141417", elevated: "#1B1B20" },
        text: { primary: "#F5F3EE", secondary: "#A9A49A", muted: "#6F6A60" },
        accent: { primary: "#D6B25E", secondary: "#E9CE8F" },
        status: { success: "#34D399", warning: "#F5A524", danger: "#E10600", info: "#9A958A" },
        border: { DEFAULT: "#242428", strong: "#35353B" },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "system-ui", "sans-serif"],
        // Bodoni Moda — high-contrast Didone serif, hero moments only
        // (key headlines, hero numerals). Body + telemetry stay Inter.
        display: ["var(--font-display)", "\"Bodoni Moda\"", "Georgia", "serif"],
      },
      boxShadow: {
        // Layered physical depth — soft, never glow.
        depth1: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 2px rgba(0,0,0,0.5), 0 12px 32px -16px rgba(0,0,0,0.8)",
        depth2: "inset 0 1px 0 rgba(255,255,255,0.07), 0 2px 4px rgba(0,0,0,0.5), 0 24px 64px -24px rgba(0,0,0,0.85)",
        depth3: "inset 0 1px 0 rgba(255,255,255,0.08), 0 32px 80px -24px rgba(0,0,0,0.9)",
      },
    },
  },
  plugins: [],
};
