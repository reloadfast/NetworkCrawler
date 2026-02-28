/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Map Tailwind utilities to CSS variable tokens
        background: "var(--color-background)",
        surface: "var(--color-surface)",
        border: "var(--color-border)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "accent-positive": "var(--color-accent-positive)",
        "accent-warning": "var(--color-accent-warning)",
        "accent-danger": "var(--color-accent-danger)",
      },
    },
  },
  plugins: [],
};
