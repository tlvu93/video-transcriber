/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "rgb(var(--background) / <alpha-value>)",
        foreground: "rgb(var(--foreground) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
        "card-foreground": "rgb(var(--card-foreground) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        "muted-foreground": "rgb(var(--muted-foreground) / <alpha-value>)",
        primary: "rgb(var(--primary) / <alpha-value>)",
        "primary-foreground": "rgb(var(--primary-foreground) / <alpha-value>)",
        secondary: "rgb(var(--secondary) / <alpha-value>)",
        "secondary-foreground":
          "rgb(var(--secondary-foreground) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        destructive: "rgb(var(--destructive) / <alpha-value>)",
        success: "rgb(var(--success) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
        info: "rgb(var(--info) / <alpha-value>)",
      },
      fontFamily: {
        sans: [
          '"Avenir Next"',
          '"Segoe UI Variable"',
          '"SF Pro Display"',
          "sans-serif",
        ],
        mono: ['"SFMono-Regular"', '"JetBrains Mono"', '"Menlo"', "monospace"],
      },
      boxShadow: {
        panel: "0 28px 80px -36px rgba(2, 6, 23, 0.8)",
        glow: "0 0 0 1px rgba(245, 158, 11, 0.12), 0 18px 60px -24px rgba(245, 158, 11, 0.35)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
