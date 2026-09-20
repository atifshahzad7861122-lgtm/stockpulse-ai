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
        //
        // Theme-aware (2026-09-20): every semantic color resolves through a
        // CSS variable so the dark/light toggle works app-wide. The
        // `rgb(from var(--x) r g b / <alpha-value>)` form keeps Tailwind
        // opacity modifiers (e.g. bg-accent-primary/10) working with vars.
        // Actual values live in styles/globals.css (:root + [data-theme]).
        bg: {
          primary: "rgb(from var(--bg-primary) r g b / <alpha-value>)",
          secondary: "rgb(from var(--bg-secondary) r g b / <alpha-value>)",
        },
        surface: {
          base: "rgb(from var(--surface-base) r g b / <alpha-value>)",
          elevated: "rgb(from var(--surface-elevated) r g b / <alpha-value>)",
        },
        text: {
          primary: "rgb(from var(--text-primary) r g b / <alpha-value>)",
          secondary: "rgb(from var(--text-secondary) r g b / <alpha-value>)",
          muted: "rgb(from var(--text-muted) r g b / <alpha-value>)",
        },
        accent: {
          primary: "rgb(from var(--accent-primary) r g b / <alpha-value>)",
          secondary: "rgb(from var(--accent-secondary) r g b / <alpha-value>)",
        },
        status: {
          success: "rgb(from var(--status-success) r g b / <alpha-value>)",
          warning: "rgb(from var(--status-warning) r g b / <alpha-value>)",
          danger: "rgb(from var(--status-danger) r g b / <alpha-value>)",
          info: "rgb(from var(--status-info) r g b / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(from var(--border-default) r g b / <alpha-value>)",
          strong: "rgb(from var(--border-strong) r g b / <alpha-value>)",
        },
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
