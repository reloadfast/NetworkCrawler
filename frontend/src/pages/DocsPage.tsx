/**
 * DocsPage — in-app documentation: overview, how scans work, risk levels,
 * configuration reference, and practical how-to guides.
 * Route: /docs
 */
import type { ReactNode } from "react";
import { Card, PageHeader } from "../components";

// ── Shared primitives ────────────────────────────────────────────────────────

function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h2
      id={id}
      className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-secondary)]"
    >
      {children}
    </h2>
  );
}

function H3({ children }: { children: ReactNode }) {
  return (
    <h3 className="mb-2 text-sm font-semibold text-[var(--color-text-primary)]">
      {children}
    </h3>
  );
}

function P({ children }: { children: ReactNode }) {
  return (
    <p className="text-sm leading-relaxed text-[var(--color-text-secondary)]">
      {children}
    </p>
  );
}

function UL({ children }: { children: ReactNode }) {
  return (
    <ul className="mt-2 space-y-1 text-sm text-[var(--color-text-secondary)]">
      {children}
    </ul>
  );
}

function LI({ children }: { children: ReactNode }) {
  return (
    <li className="flex gap-2">
      <span className="mt-0.5 shrink-0 text-[var(--color-accent-primary)]">
        ›
      </span>
      <span>{children}</span>
    </li>
  );
}

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-[var(--color-border)]/40 px-1.5 py-0.5 font-mono text-xs text-[var(--color-text-primary)]">
      {children}
    </code>
  );
}

function CodeBlock({ children }: { children: ReactNode }) {
  return (
    <pre className="mt-2 overflow-x-auto rounded-md bg-[var(--color-border)]/30 p-3 font-mono text-xs leading-relaxed text-[var(--color-text-primary)]">
      {children}
    </pre>
  );
}

function SeverityBadge({
  level,
  description,
}: {
  level: string;
  description: string;
}) {
  const colours: Record<string, string> = {
    Critical: "bg-[var(--color-accent-danger)] text-white",
    High: "bg-[var(--color-accent-warning)] text-black",
    Medium: "bg-[var(--color-accent-caution)] text-black",
    Low: "bg-[var(--color-accent-info)] text-white",
    Info: "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)]",
  };
  return (
    <div className="flex items-start gap-3 py-2">
      <span
        className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${colours[level] ?? ""}`}
      >
        {level}
      </span>
      <span className="text-sm text-[var(--color-text-secondary)]">
        {description}
      </span>
    </div>
  );
}

interface EnvVar {
  name: string;
  default_: string;
  description: string;
}

function EnvRow({ name, default_, description }: EnvVar) {
  return (
    <div className="flex flex-col gap-0.5 py-3 sm:flex-row sm:items-start sm:gap-4">
      <Code>{name}</Code>
      <div className="flex-1 text-sm text-[var(--color-text-secondary)]">
        {description}
        {default_ && (
          <span className="ml-1 text-xs text-[var(--color-text-secondary)]/60">
            (default: <Code>{default_}</Code>)
          </span>
        )}
      </div>
    </div>
  );
}

// ── Table of Contents ────────────────────────────────────────────────────────

const TOC = [
  { id: "overview", label: "Overview" },
  { id: "how-scans-work", label: "How scans work" },
  { id: "risk-levels", label: "Risk levels" },
  { id: "configuration", label: "Configuration" },
  { id: "guides", label: "How-to guides" },
];

// ── Page ─────────────────────────────────────────────────────────────────────

export function DocsPage() {
  return (
    <div>
      <PageHeader
        title="Documentation"
        subtitle="How NetworkCrawler works and how to get the most out of it"
      />

      {/* Table of contents */}
      <nav aria-label="Table of contents" className="mb-8 flex flex-wrap gap-2">
        {TOC.map(({ id, label }) => (
          <a
            key={id}
            href={`#${id}`}
            className="rounded-md border border-[var(--color-border)] px-3 py-1 text-sm text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent-primary)]/50 hover:text-[var(--color-text-primary)]"
          >
            {label}
          </a>
        ))}
      </nav>

      <div className="flex flex-col gap-8">
        {/* ── Overview ──────────────────────────────────────────────────── */}
        <section aria-labelledby="overview">
          <SectionHeading id="overview">Overview</SectionHeading>
          <Card>
            <div className="space-y-3">
              <P>
                NetworkCrawler is a passive home-lab security scanner. It
                discovers every device on your local network, identifies open
                services and their versions, infers the operating system, and
                evaluates the result against a set of security checks —
                producing a prioritised list of risks and hardening
                recommendations.
              </P>
              <P>
                All scanning is passive from an exploitation perspective: no
                credentials are tested, no vulnerabilities are probed. The goal
                is visibility and awareness, not penetration testing.
              </P>
              <UL>
                <LI>
                  Runs entirely on your LAN — no data leaves your network.
                </LI>
                <LI>
                  Deployed as a single Docker container with{" "}
                  <Code>network_mode: host</Code> to reach all devices.
                </LI>
                <LI>
                  Scans run on a configurable schedule or can be triggered
                  manually from the Dashboard.
                </LI>
                <LI>
                  History, trends, and per-device detail are retained in a local
                  SQLite database.
                </LI>
              </UL>
            </div>
          </Card>
        </section>

        {/* ── How scans work ────────────────────────────────────────────── */}
        <section aria-labelledby="how-scans-work">
          <SectionHeading id="how-scans-work">How scans work</SectionHeading>
          <Card>
            <div className="space-y-5">
              <div>
                <H3>1 · ARP discovery</H3>
                <P>
                  A broadcast ARP request is sent across the configured subnet
                  (e.g. <Code>192.168.1.0/24</Code>). Every active device
                  responds with its MAC address, giving a definitive list of
                  hosts that are online at that moment. ARP operates at layer 2
                  and cannot be filtered by a host firewall.
                </P>
              </div>
              <div>
                <H3>2 · Port scan</H3>
                <P>
                  Each discovered IP is scanned with nmap against the top 1 000
                  most common TCP ports. Service banners and version strings are
                  captured where available. This step is the most time-consuming
                  part of the scan.
                </P>
              </div>
              <div>
                <H3>3 · Hostname resolution</H3>
                <P>
                  A reverse DNS PTR lookup is attempted for each IP. If that
                  fails, a direct mDNS query is sent to the multicast address{" "}
                  <Code>224.0.0.251:5353</Code> — the same mechanism your
                  browser uses to resolve <Code>.local</Code> names. This works
                  for most modern devices including Apple, Linux, and Windows
                  machines.
                </P>
              </div>
              <div>
                <H3>4 · OS inference</H3>
                <P>
                  The MAC vendor (derived from the OUI prefix), open ports, and
                  service banners are combined to produce a best-guess operating
                  system label. This is heuristic, not authoritative.
                </P>
              </div>
              <div>
                <H3>5 · Risk analysis</H3>
                <P>
                  Each device is evaluated against all active security checks.
                  Checks look for things like unencrypted remote-access
                  protocols, default management ports exposed, outdated software
                  indicators, and unnecessary services. Each failing check
                  produces a Risk record with a severity level, and a linked
                  Recommendation with concrete steps to remediate.
                </P>
              </div>
            </div>
          </Card>
        </section>

        {/* ── Risk levels ───────────────────────────────────────────────── */}
        <section aria-labelledby="risk-levels">
          <SectionHeading id="risk-levels">Risk levels</SectionHeading>
          <Card>
            <div className="divide-y divide-[var(--color-border)]">
              <SeverityBadge
                level="Critical"
                description="Immediate threat to the device or network. Examples: Telnet open, unauthenticated Redis or Docker daemon exposed. Remediate before the next scan."
              />
              <SeverityBadge
                level="High"
                description="Significant attack surface. Examples: FTP in cleartext, SNMP with default community string, unpatched service banners. Remediate soon."
              />
              <SeverityBadge
                level="Medium"
                description="Elevated risk that should be reviewed. Examples: unnecessary open ports, management interfaces accessible from the whole LAN."
              />
              <SeverityBadge
                level="Low"
                description="Minor hardening opportunity. Examples: non-standard ports in use, informational service exposure."
              />
              <SeverityBadge
                level="Info"
                description="Observation only — no direct risk. Examples: a VPN server detected, a device with an unknown OS."
              />
            </div>
          </Card>
        </section>

        {/* ── Configuration ─────────────────────────────────────────────── */}
        <section aria-labelledby="configuration">
          <SectionHeading id="configuration">Configuration</SectionHeading>
          <Card>
            <P>
              All configuration is done via environment variables in your{" "}
              <Code>docker-compose.yml</Code>. No file editing inside the
              container is required.
            </P>
            <div className="mt-4 divide-y divide-[var(--color-border)]">
              {(
                [
                  {
                    name: "SCAN_SUBNET",
                    default_: "192.168.1.0/24",
                    description:
                      "CIDR range to scan. Must match your LAN subnet.",
                  },
                  {
                    name: "SCAN_INTERVAL_MINUTES",
                    default_: "60",
                    description:
                      "How often to run an automatic scan, in minutes. Set to 0 to disable automatic scanning.",
                  },
                  {
                    name: "DATA_DIR",
                    default_: "/app/data",
                    description:
                      "Path inside the container where the SQLite database is stored. Mount a host volume here to persist data across container restarts.",
                  },
                ] as EnvVar[]
              ).map((v) => (
                <EnvRow key={v.name} {...v} />
              ))}
            </div>
            <div className="mt-4">
              <H3>Minimal docker-compose.yml</H3>
              <CodeBlock>{`services:
  networkcrawler:
    image: ghcr.io/reloadfast/networkcrawler:latest
    network_mode: host          # required — allows ARP and mDNS
    environment:
      SCAN_SUBNET: "192.168.1.0/24"
      SCAN_INTERVAL_MINUTES: "60"
    volumes:
      - networkcrawler_data:/app/data
    restart: unless-stopped

volumes:
  networkcrawler_data:`}</CodeBlock>
            </div>
          </Card>
        </section>

        {/* ── How-to guides ─────────────────────────────────────────────── */}
        <section aria-labelledby="guides">
          <SectionHeading id="guides">How-to guides</SectionHeading>

          <div className="flex flex-col gap-4">
            {/* Hostnames */}
            <Card>
              <H3>Set a readable hostname so devices are easy to identify</H3>
              <P>
                By default many devices advertise generic names like{" "}
                <Code>android-a3f2</Code> or show no hostname at all. Setting a
                descriptive hostname makes your device list immediately
                understandable and survives across re-scans.
              </P>

              <div className="mt-4 space-y-4">
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                    Linux (systemd)
                  </p>
                  <CodeBlock>{`sudo hostnamectl set-hostname my-server
# Restart avahi-daemon if installed so the new name is advertised over mDNS:
sudo systemctl restart avahi-daemon`}</CodeBlock>
                </div>

                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                    macOS
                  </p>
                  <P>
                    Go to <strong>System Settings → General → Sharing</strong>{" "}
                    and edit the <em>Local Hostname</em> field. The change takes
                    effect immediately and is broadcast via Bonjour (mDNS).
                  </P>
                </div>

                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                    Windows 10 / 11
                  </p>
                  <P>
                    Go to <strong>Settings → System → About</strong> and click{" "}
                    <em>Rename this PC</em>. A reboot is required. Windows
                    advertises the new name via NetBIOS and mDNS (WSD).
                  </P>
                </div>

                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                    Raspberry Pi / Debian
                  </p>
                  <CodeBlock>{`sudo raspi-config
# Navigate to: System Options → Hostname
# Or directly:
echo "my-pi" | sudo tee /etc/hostname
sudo sed -i 's/127\\.0\\.1\\.1.*/127.0.1.1\\tmy-pi/' /etc/hosts
sudo reboot`}</CodeBlock>
                </div>

                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                    Router / DHCP static mapping
                  </p>
                  <P>
                    If you cannot change the hostname on a device (e.g. an IoT
                    appliance), most routers allow you to assign a static IP and
                    hostname to a MAC address via the DHCP reservation table.
                    Check your router admin panel under{" "}
                    <em>DHCP → Static Leases</em> or similar. NetworkCrawler
                    will pick up the PTR record if your router populates its
                    local DNS accordingly.
                  </P>
                </div>
              </div>
            </Card>

            {/* Trusted devices */}
            <Card>
              <H3>Mark devices as trusted</H3>
              <P>
                Once you have identified all expected devices on your network,
                mark them as <em>Trusted</em> using the toggle on the device
                detail page. Trusted devices are visually distinguished in the
                device list. Any new device that appears after that point and is
                not trusted stands out immediately as something to investigate.
              </P>
            </Card>

            {/* Scan tips */}
            <Card>
              <H3>Get the best scan results</H3>
              <UL>
                <LI>
                  Run NetworkCrawler on the same physical network segment as
                  your devices, not across a routed boundary — ARP does not
                  cross routers.
                </LI>
                <LI>
                  Use <Code>network_mode: host</Code> in your compose file.
                  Bridge networking prevents ARP discovery and mDNS from working
                  correctly.
                </LI>
                <LI>
                  Schedule scans during a time when all your devices are likely
                  to be on (e.g. evening) for the most complete inventory.
                </LI>
                <LI>
                  Devices that are powered off during a scan will not appear in
                  that scan's results but will remain in the database from
                  previous scans.
                </LI>
              </UL>
            </Card>
          </div>
        </section>
      </div>
    </div>
  );
}
