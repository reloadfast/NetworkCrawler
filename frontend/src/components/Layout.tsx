/**
 * Layout — persistent shell with top nav and main content area.
 * Renders theme toggle and nav links; wraps all route pages.
 * Includes a skip-to-main-content link for keyboard users.
 */
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useTheme } from '../hooks'
import { useAppVersion } from '../hooks/useAppVersion'

const navLinks = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/devices', label: 'Devices', end: false },
  { to: '/risks', label: 'Risks', end: false },
  { to: '/recommendations', label: 'Recommendations', end: false },
  { to: '/settings', label: 'Settings', end: false },
]

export function Layout() {
  const { theme, toggleTheme } = useTheme()
  const { version } = useAppVersion()
  const [copied, setCopied] = useState(false)

  const handleCopyVersion = () => {
    if (!version) return
    navigator.clipboard.writeText(`v${version}`).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-text-primary)]">
      {/* Skip link — visible only on keyboard focus */}
      <a
        href="#main-content"
        className={[
          'sr-only focus:not-sr-only',
          'fixed left-2 top-2 z-[100] rounded px-3 py-1.5 text-sm font-medium',
          'bg-[var(--color-accent-primary)] text-white',
        ].join(' ')}
      >
        Skip to main content
      </a>

      <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <span className="text-lg font-bold tracking-tight">NetworkCrawler</span>
            <nav className="flex gap-1" aria-label="Main navigation">
              {navLinks.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    [
                      'rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150',
                      isActive
                        ? 'bg-[var(--color-background)] text-[var(--color-text-primary)]'
                        : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]',
                    ].join(' ')
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            {version && (
              <button
                onClick={handleCopyVersion}
                aria-label={copied ? 'Copied!' : `Copy version v${version} to clipboard`}
                title={copied ? 'Copied!' : `v${version} — click to copy`}
                className="font-mono text-xs text-[var(--color-text-secondary)] transition-colors duration-150 hover:text-[var(--color-text-primary)] select-none"
              >
                {copied ? '✓' : `v${version}`}
              </button>
            )}
            <button
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm text-[var(--color-text-secondary)] transition-colors duration-150 hover:text-[var(--color-text-primary)]"
            >
              {theme === 'dark' ? '☀ Light' : '☾ Dark'}
            </button>
          </div>
        </div>
      </header>
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <div className="page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
