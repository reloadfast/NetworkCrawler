import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/theme.css";
import { useTheme } from "./hooks";
import { Badge, Card, Chart, ProgressBar } from "./components";

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors duration-150 hover:text-[var(--color-text-primary)]"
    >
      {theme === "dark" ? "☀ Light" : "☾ Dark"}
    </button>
  );
}

function App() {
  return (
    <div className="min-h-screen bg-background p-8">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-text-primary)]">
          NetworkCrawler
        </h1>
        <ThemeToggle />
      </header>

      {/* Component showcase — replaced by real pages in Phase 4 */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
            Risk Badges
          </p>
          <div className="flex flex-wrap gap-2">
            <Badge variant="critical">Critical</Badge>
            <Badge variant="high">High</Badge>
            <Badge variant="medium">Medium</Badge>
            <Badge variant="low">Low</Badge>
            <Badge variant="neutral">Neutral</Badge>
          </div>
        </Card>

        <Card>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
            Progress Bars
          </p>
          <div className="flex flex-col gap-3">
            <ProgressBar value={85} variant="positive" showLabel />
            <ProgressBar value={55} variant="warning" showLabel />
            <ProgressBar value={20} variant="danger" showLabel />
          </div>
        </Card>

        <Card>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]">
            Radial Charts
          </p>
          <div className="flex gap-4">
            <Chart value={75} variant="positive" label="75%" aria-label="75 percent healthy" />
            <Chart value={40} variant="warning" label="40%" aria-label="40 percent warning" />
            <Chart value={15} variant="danger" label="15%" aria-label="15 percent critical" />
          </div>
        </Card>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
