/**
 * SettingsPage — application configuration and system information.
 * Route: /settings
 */
import React, { useState } from "react";
import { Card } from "../components";
import { useAppVersion } from "../hooks/useAppVersion";

export function SettingsPage() {
  const { version, loading } = useAppVersion();
  const [copied, setCopied] = useState(false);

  const handleCopyVersion = () => {
    if (!version) return;
    navigator.clipboard.writeText(`v${version}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="page-enter">
      <h1 className="mb-6 text-2xl font-bold tracking-tight">Settings</h1>

      {/* ── System ─────────────────────────────────────────────────────── */}
      <section aria-labelledby="system-heading">
        <h2
          id="system-heading"
          className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]"
        >
          System
        </h2>
        <Card>
          <dl className="divide-y divide-[var(--color-border)]">
            <div className="flex items-center justify-between py-3">
              <dt className="text-sm text-[var(--color-text-secondary)]">
                Version
              </dt>
              <dd className="flex items-center gap-2">
                {loading ? (
                  <span className="h-4 w-16 animate-pulse rounded bg-[var(--color-border)]" />
                ) : version ? (
                  <button
                    onClick={handleCopyVersion}
                    aria-label={
                      copied
                        ? "Copied!"
                        : `Copy version v${version} to clipboard`
                    }
                    title={copied ? "Copied!" : "Click to copy"}
                    className="select-none font-mono text-sm text-[var(--color-text-primary)] transition-colors duration-150 hover:text-[var(--color-accent-positive)]"
                  >
                    {copied ? `✓ v${version}` : `v${version}`}
                  </button>
                ) : (
                  <span className="font-mono text-sm text-[var(--color-text-secondary)]">
                    —
                  </span>
                )}
              </dd>
            </div>

            <div className="flex items-center justify-between py-3">
              <dt className="text-sm text-[var(--color-text-secondary)]">
                Source
              </dt>
              <dd className="text-sm text-[var(--color-text-secondary)]">
                <a
                  href="https://github.com/reloadfast/NetworkCrawler"
                  target="_blank"
                  rel="noreferrer"
                  className="underline underline-offset-2 hover:text-[var(--color-text-primary)]"
                >
                  github.com/reloadfast/NetworkCrawler
                </a>
              </dd>
            </div>
          </dl>
        </Card>
      </section>
    </div>
  );
}
