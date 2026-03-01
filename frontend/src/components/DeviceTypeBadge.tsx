/** DeviceTypeBadge — small coloured pill showing device type with an icon. */

const TYPE_CONFIG: Record<
  string,
  { icon: string; label: string; className: string }
> = {
  iot: {
    icon: "📡",
    label: "IoT",
    className:
      "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  },
  server: {
    icon: "🖥",
    label: "Server",
    className:
      "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  },
  router: {
    icon: "🔀",
    label: "Router",
    className:
      "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  },
  workstation: {
    icon: "💻",
    label: "Workstation",
    className:
      "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  },
  unknown: {
    icon: "❓",
    label: "Unknown",
    className:
      "bg-[var(--color-surface)] text-[var(--color-text-secondary)] border border-[var(--color-border)]",
  },
};

export function DeviceTypeBadge({
  type,
  size = "sm",
}: {
  type: string | null | undefined;
  size?: "sm" | "md";
}) {
  const cfg = TYPE_CONFIG[type ?? "unknown"] ?? TYPE_CONFIG["unknown"];
  const sizeClass =
    size === "sm" ? "px-1.5 py-0.5 text-xs" : "px-2 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-medium ${sizeClass} ${cfg.className}`}
      title={`Device type: ${cfg.label}`}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}
