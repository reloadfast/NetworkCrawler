/**
 * TopologyPage — interactive network graph built with React Flow (@xyflow/react).
 * Gateway node sits at centre; device nodes are arranged in a radial ring,
 * colour-coded by highest active risk severity. Clicking a node navigates to
 * the device detail page.
 * Route: /topology
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { TopologyNode } from "../types/api";

// ── Severity → border colour ──────────────────────────────────────────────────

const SEVERITY_COLOUR: Record<string, string> = {
  critical: "var(--color-accent-danger)",
  high: "var(--color-accent-warning)",
  medium: "#eab308",
  low: "var(--color-accent-positive)",
};

const DEVICE_TYPE_ICON: Record<string, string> = {
  router: "🌐",
  server: "🖥️",
  workstation: "💻",
  iot: "📡",
  unknown: "❓",
};

// ── Cluster angles by device type (degrees from top) ─────────────────────────

const CLUSTER_BASE_ANGLE: Record<string, number> = {
  server: 0,
  workstation: 90,
  iot: 180,
  unknown: 270,
  router: 315,
};

// ── Custom node component ─────────────────────────────────────────────────────

interface NodeData {
  device: TopologyNode;
  onClick: (id: number) => void;
  [key: string]: unknown;
}

function DeviceNode({ data }: { data: NodeData }) {
  const { device, onClick } = data;
  const borderColour = device.highest_severity
    ? SEVERITY_COLOUR[device.highest_severity]
    : "var(--color-accent-positive)";
  const isPulsing =
    device.highest_severity === "critical" ||
    device.highest_severity === "high";
  const displayName = device.label ?? device.hostname ?? device.ip_address;
  const icon = DEVICE_TYPE_ICON[device.device_type] ?? "❓";

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div
        onClick={() => onClick(device.id)}
        className={`cursor-pointer rounded-xl border-2 bg-[var(--color-surface)] p-3 shadow-md transition-transform hover:scale-105 hover:shadow-lg min-w-[120px] max-w-[160px]${isPulsing ? " animate-pulse" : ""}`}
        style={{ borderColor: borderColour }}
        title={`${displayName} — ${device.ip_address}`}
      >
        <div className="flex items-center gap-2">
          <span className="text-xl" aria-hidden="true">
            {device.is_gateway ? "🌐" : icon}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-[var(--color-text-primary)]">
              {displayName}
            </p>
            <p className="truncate text-[10px] text-[var(--color-text-secondary)]">
              {device.ip_address}
            </p>
          </div>
        </div>
        {device.highest_severity && (
          <div
            className="mt-2 rounded px-1.5 py-0.5 text-center text-[10px] font-bold uppercase tracking-wide text-white"
            style={{ backgroundColor: borderColour }}
          >
            {device.highest_severity}
          </div>
        )}
        {!device.highest_severity && (
          <div className="mt-2 rounded bg-[var(--color-accent-positive)]/20 px-1.5 py-0.5 text-center text-[10px] font-medium text-[var(--color-accent-positive)]">
            clean
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

const NODE_TYPES = { device: DeviceNode };

// ── Layout helpers ────────────────────────────────────────────────────────────

const GATEWAY_POS = { x: 400, y: 350 };
const RING_RADIUS = 280;

function buildLayout(nodes: TopologyNode[]) {
  const gateway = nodes.find((n) => n.is_gateway);
  const others = nodes.filter((n) => !n.is_gateway);

  // Group others by device_type
  const groups: Record<string, TopologyNode[]> = {};
  for (const n of others) {
    const key = n.device_type ?? "unknown";
    (groups[key] ??= []).push(n);
  }

  const positions: Record<number, { x: number; y: number }> = {};
  if (gateway) {
    positions[gateway.id] = GATEWAY_POS;
  }

  // Evenly space all non-gateway nodes around the ring
  others.forEach((node) => {
    // Start offset based on cluster, then spread evenly
    const baseAngle = CLUSTER_BASE_ANGLE[node.device_type ?? "unknown"] ?? 270;
    const clusterNodes = groups[node.device_type ?? "unknown"] ?? [];
    const clusterIdx = clusterNodes.indexOf(node);
    const clusterSize = clusterNodes.length;
    // Spread cluster ±30° around its base angle
    const spread = clusterSize > 1 ? 60 / (clusterSize - 1) : 0;
    const angleDeg = baseAngle - 30 + spread * clusterIdx;
    const angleRad = ((angleDeg - 90) * Math.PI) / 180;
    positions[node.id] = {
      x: GATEWAY_POS.x + RING_RADIUS * Math.cos(angleRad) - 60,
      y: GATEWAY_POS.y + RING_RADIUS * Math.sin(angleRad) - 40,
    };
  });

  return positions;
}

// ── Main component ────────────────────────────────────────────────────────────

export function TopologyPage() {
  const navigate = useNavigate();
  const [topology, setTopology] = useState<TopologyNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/topology")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<TopologyNode[]>;
      })
      .then((data) => {
        setTopology(data);
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  const handleNodeClick = useCallback(
    (id: number) => navigate(`/devices/${id}`),
    [navigate],
  );

  const positions = useMemo(() => buildLayout(topology), [topology]);

  const initialNodes = useMemo(
    () =>
      topology.map((device) => ({
        id: String(device.id),
        type: "device",
        position: positions[device.id] ?? { x: 0, y: 0 },
        data: { device, onClick: handleNodeClick } satisfies NodeData,
      })),
    [topology, positions, handleNodeClick],
  );

  const gateway = topology.find((n) => n.is_gateway);
  const initialEdges = useMemo(
    () =>
      gateway
        ? topology
            .filter((n) => !n.is_gateway)
            .map((n) => ({
              id: `e-${gateway.id}-${n.id}`,
              source: String(gateway.id),
              target: String(n.id),
              style: {
                stroke: "var(--color-border)",
                strokeWidth: 1.5,
              },
            }))
        : [],
    [topology, gateway],
  );

  const [rfNodes, , onNodesChange] = useNodesState(initialNodes);
  const [rfEdges, , onEdgesChange] = useEdgesState(initialEdges);

  // Sync when topology loads
  const [synced, setSynced] = useState(false);
  useEffect(() => {
    if (topology.length > 0 && !synced) {
      setSynced(true);
    }
  }, [topology, synced]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center text-[var(--color-text-secondary)]">
        Loading topology…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-96 items-center justify-center text-[var(--color-accent-danger)]">
        Failed to load topology: {error}
      </div>
    );
  }

  if (topology.length === 0) {
    return (
      <div className="flex h-96 items-center justify-center text-[var(--color-text-secondary)]">
        No devices found. Run a scan first.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
            Network Topology
          </h1>
          <p className="mt-0.5 text-sm text-[var(--color-text-secondary)]">
            {topology.length} device{topology.length !== 1 ? "s" : ""} — click a
            node to view details
          </p>
        </div>
        <div className="flex gap-3 text-xs text-[var(--color-text-secondary)]">
          {(["critical", "high", "medium", "low"] as const).map((s) => (
            <span key={s} className="flex items-center gap-1">
              <span
                className="inline-block h-3 w-3 rounded-full"
                style={{ backgroundColor: SEVERITY_COLOUR[s] }}
              />
              {s}
            </span>
          ))}
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full bg-[var(--color-accent-positive)]" />
            clean
          </span>
        </div>
      </div>
      <div
        className="flex-1 overflow-hidden rounded-xl border border-[var(--color-border)]"
        style={{ minHeight: 500 }}
      >
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Controls />
          <Background color="var(--color-border)" gap={24} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}
