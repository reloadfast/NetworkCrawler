/**
 * Layout — persistent shell with sticky top nav and main content area.
 * Renders theme toggle and nav links; wraps all route pages.
 * Includes a skip-to-main-content link for keyboard users.
 */
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../hooks";
import { useAppVersion } from "../hooks/useAppVersion";

/** Copy text to clipboard; works on HTTP as well as HTTPS. */
function copyViaExecCommand(text: string): void {
  const el = document.createElement("textarea");
  el.value = text;
  el.style.position = "fixed";
  el.style.opacity = "0";
  document.body.appendChild(el);
  el.select();
  document.execCommand("copy");
  document.body.removeChild(el);
}

const navLinks = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/devices", label: "Devices", end: false },
  { to: "/risks", label: "Risks", end: false },
  { to: "/history", label: "History", end: false },
  { to: "/recommendations", label: "Recommendations", end: false },
  { to: "/settings", label: "Settings", end: false },
];

function SunIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="4.22" y1="4.22" x2="7.05" y2="7.05" />
      <line x1="16.95" y1="16.95" x2="19.78" y2="19.78" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
      <line x1="4.22" y1="19.78" x2="7.05" y2="16.95" />
      <line x1="16.95" y1="7.05" x2="19.78" y2="4.22" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function NetworkIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="text-[var(--color-accent-primary)]"
    >
      <circle cx="12" cy="5" r="2" />
      <circle cx="5" cy="19" r="2" />
      <circle cx="19" cy="19" r="2" />
      <line x1="12" y1="7" x2="5" y2="17" />
      <line x1="12" y1="7" x2="19" y2="17" />
      <line x1="5" y1="19" x2="19" y2="19" />
    </svg>
  );
}

export function Layout() {
  const { theme, toggleTheme } = useTheme();
  const { version } = useAppVersion();
  const [copied, setCopied] = useState(false);

  const handleCopyVersion = () => {
    if (!version) return;
    const text = `v${version}`;
    const flash = () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    };
    // navigator.clipboard requires a secure context (HTTPS / localhost).
    // Fall back to execCommand for plain-HTTP home-lab deployments.
    if (navigator.clipboard) {
      navigator.clipboard
        .writeText(text)
        .then(flash)
        .catch(() => {
          copyViaExecCommand(text);
          flash();
        });
    } else {
      copyViaExecCommand(text);
      flash();
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-text-primary)]">
      {/* Skip link — visible only on keyboard focus */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only fixed left-2 top-2 z-[100] rounded px-3 py-1.5 text-sm font-medium bg-[var(--color-accent-primary)] text-white"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-surface)]/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          {/* Brand + nav */}
          <div className="flex items-center gap-6">
            <NavLink
              to="/"
              className="flex items-center gap-2 text-sm font-semibold tracking-tight hover:opacity-80 transition-opacity"
              aria-label="NetworkCrawler home"
            >
              <NetworkIcon />
              <span>NetworkCrawler</span>
            </NavLink>

            <nav className="flex gap-1" aria-label="Main navigation">
              {navLinks.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    [
                      "rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                      isActive
                        ? "bg-[var(--color-accent-primary)]/10 text-[var(--color-accent-primary)]"
                        : "text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]/40 hover:text-[var(--color-text-primary)]",
                    ].join(" ")
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right: version badge + theme toggle */}
          <div className="flex items-center gap-2">
            {version && (
              <button
                onClick={handleCopyVersion}
                aria-label={
                  copied ? "Copied!" : `Copy version v${version} to clipboard`
                }
                title={copied ? "Copied!" : `v${version} — click to copy`}
                className="select-none rounded px-2 py-1 font-mono text-xs text-[var(--color-text-secondary)] transition-colors duration-150 hover:bg-[var(--color-border)]/40 hover:text-[var(--color-text-primary)]"
              >
                {copied ? "✓ copied" : `v${version}`}
              </button>
            )}
            <button
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-text-secondary)] transition-colors duration-150 hover:border-[var(--color-accent-primary)]/50 hover:text-[var(--color-text-primary)]"
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
