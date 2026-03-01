/**
 * SettingsPage — application configuration and system information.
 * Route: /settings
 */
import { useEffect, useState } from "react";
import { Card, PageHeader } from "../components";
import { useAppVersion } from "../hooks/useAppVersion";
import type {
  ChecklistAnswer,
  ChecklistItem,
  ChecklistState,
  PostureBadge,
} from "../types/api";

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

function useWebhookSettings() {
  const [webhookUrl, setWebhookUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d: { webhook_url: string | null }) =>
        setWebhookUrl(d.webhook_url ?? ""),
      )
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const flash = (type: "success" | "error", msg: string) => {
    setFeedback({ type, msg });
    setTimeout(() => setFeedback(null), 3500);
  };

  const save = () => {
    setSaving(true);
    fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ webhook_url: webhookUrl.trim() || null }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        flash("success", "Saved");
      })
      .catch(() => flash("error", "Failed to save"))
      .finally(() => setSaving(false));
  };

  const test = () => {
    setTesting(true);
    fetch("/api/settings/webhook/test", { method: "POST" })
      .then((r) => r.json())
      .then((d: { success: boolean; message: string }) =>
        flash(d.success ? "success" : "error", d.message),
      )
      .catch(() => flash("error", "Test request failed"))
      .finally(() => setTesting(false));
  };

  return {
    webhookUrl,
    setWebhookUrl,
    loading,
    saving,
    testing,
    feedback,
    save,
    test,
  };
}

// ── Checklist helpers ─────────────────────────────────────────────────────────

const POSTURE_CONFIG: Record<
  PostureBadge,
  { label: string; color: string; bg: string; icon: string }
> = {
  at_risk: {
    label: "At Risk",
    color: "text-[var(--color-accent-danger)]",
    bg: "bg-[var(--color-accent-danger)]/10",
    icon: "🔴",
  },
  basic: {
    label: "Basic",
    color: "text-[var(--color-accent-warning)]",
    bg: "bg-[var(--color-accent-warning)]/10",
    icon: "🟡",
  },
  intermediate: {
    label: "Intermediate",
    color: "text-[var(--color-accent-positive)]",
    bg: "bg-[var(--color-accent-positive)]/10",
    icon: "🟢",
  },
  hardened: {
    label: "Hardened",
    color: "text-[var(--color-accent-primary)]",
    bg: "bg-[var(--color-accent-primary)]/10",
    icon: "🛡️",
  },
};

function useChecklist() {
  const [state, setState] = useState<ChecklistState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/settings/checklist")
      .then((r) => r.json())
      .then((d: ChecklistState) => setState(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const setAnswer = (key: string, answer: ChecklistAnswer) => {
    if (!state) return;
    // Optimistic update
    setState((prev) => {
      if (!prev) return prev;
      const items = prev.items.map((it) =>
        it.key === key ? { ...it, answer } : it,
      );
      const yes_count = items.filter((it) => it.answer === "yes").length;
      const posture = computePosture(yes_count);
      return {
        ...prev,
        items,
        yes_count,
        posture: posture.badge,
        posture_label: posture.label,
      };
    });

    setSaving(true);
    fetch("/api/settings/checklist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: { [key]: answer } }),
    })
      .then((r) => r.json())
      .then((d: ChecklistState) => setState(d))
      .catch(() => {})
      .finally(() => setSaving(false));
  };

  return { state, loading, saving, setAnswer };
}

function computePosture(yesCount: number): {
  badge: PostureBadge;
  label: string;
} {
  if (yesCount >= 8) return { badge: "hardened", label: "Hardened" };
  if (yesCount >= 6) return { badge: "intermediate", label: "Intermediate" };
  if (yesCount >= 4) return { badge: "basic", label: "Basic" };
  return { badge: "at_risk", label: "At Risk" };
}

function AnswerToggle({
  item,
  onChange,
}: {
  item: ChecklistItem;
  onChange: (key: string, answer: ChecklistAnswer) => void;
}) {
  const answers: { value: ChecklistAnswer; label: string }[] = [
    { value: "yes", label: "Yes" },
    { value: "no", label: "No" },
    { value: "unknown", label: "?" },
  ];

  return (
    <div className="flex rounded-md border border-[var(--color-border)] overflow-hidden text-xs font-medium">
      {answers.map(({ value, label }) => {
        const isActive = item.answer === value;
        const activeClass =
          value === "yes"
            ? "bg-[var(--color-accent-positive)] text-white"
            : value === "no"
              ? "bg-[var(--color-accent-danger)] text-white"
              : "bg-[var(--color-border)] text-[var(--color-text-primary)]";
        return (
          <button
            key={value}
            onClick={() => onChange(item.key, value)}
            className={[
              "px-2.5 py-1 transition-colors duration-150",
              isActive
                ? activeClass
                : "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-border)]/40",
            ].join(" ")}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function SettingsPage() {
  const { version, loading: vLoading } = useAppVersion();
  const [copied, setCopied] = useState(false);
  const {
    state: checklist,
    loading: clLoading,
    saving: clSaving,
    setAnswer,
  } = useChecklist();
  const {
    webhookUrl,
    setWebhookUrl,
    loading: whLoading,
    saving,
    testing,
    feedback,
    save,
    test,
  } = useWebhookSettings();

  const handleCopyVersion = () => {
    if (!version) return;
    const text = `v${version}`;
    const flash = () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    };
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
    <div className="page-enter">
      <PageHeader title="Settings" />

      {/* ── Notifications ───────────────────────────────────────────────── */}
      <section aria-labelledby="notifications-heading" className="mb-6">
        <h2
          id="notifications-heading"
          className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]"
        >
          Notifications
        </h2>
        <Card>
          <p className="mb-4 text-sm text-[var(--color-text-secondary)]">
            Send a webhook when a new device is detected or critical risks are
            found. Compatible with{" "}
            <a
              href="https://ntfy.sh"
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:text-[var(--color-text-primary)]"
            >
              ntfy.sh
            </a>
            , Gotify, Home Assistant, Slack, and Discord.
          </p>

          <label
            htmlFor="webhook-url"
            className="mb-1 block text-sm font-medium text-[var(--color-text-secondary)]"
          >
            Webhook URL
          </label>
          <div className="flex gap-2">
            <input
              id="webhook-url"
              type="url"
              value={whLoading ? "" : webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://ntfy.sh/my-topic"
              disabled={whLoading}
              className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)] disabled:opacity-50"
            />
            <button
              onClick={save}
              disabled={saving || whLoading}
              className="rounded-md bg-[var(--color-accent-primary)] px-3 py-2 text-sm font-medium text-white disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={test}
              disabled={testing || whLoading || !webhookUrl.trim()}
              className="rounded-md border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-secondary)] disabled:opacity-40 hover:text-[var(--color-text-primary)] transition-colors"
            >
              {testing ? "Testing…" : "Test"}
            </button>
          </div>

          {feedback && (
            <p
              className={`mt-2 text-xs ${
                feedback.type === "success"
                  ? "text-[var(--color-accent-positive)]"
                  : "text-[var(--color-accent-danger)]"
              }`}
            >
              {feedback.msg}
            </p>
          )}

          <p className="mt-3 text-xs text-[var(--color-text-secondary)]">
            The webhook fires at the end of each scan if new devices appear or
            critical risks are detected. A JSON payload is posted with{" "}
            <code className="rounded bg-[var(--color-border)]/40 px-1 font-mono">
              event
            </code>
            ,{" "}
            <code className="rounded bg-[var(--color-border)]/40 px-1 font-mono">
              new_devices
            </code>
            ,{" "}
            <code className="rounded bg-[var(--color-border)]/40 px-1 font-mono">
              risk_counts
            </code>
            , and ntfy.sh-compatible{" "}
            <code className="rounded bg-[var(--color-border)]/40 px-1 font-mono">
              title
            </code>{" "}
            /{" "}
            <code className="rounded bg-[var(--color-border)]/40 px-1 font-mono">
              message
            </code>{" "}
            fields.
          </p>
        </Card>
      </section>

      {/* ── Network Health Checklist ─────────────────────────────────── */}
      <section aria-labelledby="checklist-heading" className="mb-6">
        <h2
          id="checklist-heading"
          className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]"
        >
          Network Health Checklist
        </h2>
        <Card>
          {/* Posture badge */}
          {!clLoading && checklist && (
            <div
              className={`mb-5 flex items-center gap-3 rounded-lg px-4 py-3 ${POSTURE_CONFIG[checklist.posture].bg}`}
            >
              <span className="text-2xl" aria-hidden="true">
                {POSTURE_CONFIG[checklist.posture].icon}
              </span>
              <div>
                <p
                  className={`text-base font-semibold ${POSTURE_CONFIG[checklist.posture].color}`}
                >
                  {POSTURE_CONFIG[checklist.posture].label}
                </p>
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {checklist.yes_count} of {checklist.items.length} best
                  practices confirmed
                  {clSaving && (
                    <span className="ml-2 opacity-60">(saving…)</span>
                  )}
                </p>
              </div>
            </div>
          )}

          {clLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 animate-pulse rounded bg-[var(--color-border)]"
                />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {checklist?.items.map((item) => (
                <li key={item.key} className="py-3">
                  <div className="flex items-start justify-between gap-4">
                    <span className="flex-1 text-sm text-[var(--color-text-primary)]">
                      {item.question}
                    </span>
                    <AnswerToggle item={item} onChange={setAnswer} />
                  </div>
                  {item.answer !== "yes" && (
                    <p className="mt-1.5 text-xs text-[var(--color-text-secondary)]">
                      💡 {item.advice}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

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
                {vLoading ? (
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
