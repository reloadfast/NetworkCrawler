/**
 * Shared TypeScript types that mirror the backend Pydantic response models.
 * Keep in sync with backend/app/api/__init__.py.
 */

export interface Port {
  id: number;
  port_number: number;
  protocol: string;
  service_name: string | null;
  version_banner: string | null;
}

export interface Device {
  id: number;
  ip_address: string;
  mac_address: string | null;
  vendor: string | null;
  hostname: string | null;
  os_guess: string | null;
  label: string | null;
  trusted: boolean;
  first_seen: string | null; // ISO-8601
  last_seen: string | null;
  ports: Port[];
  security_score: number; // 0–100
}

export interface Scan {
  id: number;
  status: string;
  triggered_by: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  devices_found: number | null;
  current_stage: string | null;
  error_message: string | null;
  warning_message: string | null;
  risks_critical: number | null;
  risks_high: number | null;
  risks_medium: number | null;
  risks_low: number | null;
}

export interface TriggerResponse {
  message: string;
  scan_id: number | null;
}

export type Severity = "critical" | "high" | "medium" | "low";

export interface Risk {
  id: number;
  device_id: number;
  ip_address: string;
  hostname: string | null;
  severity: Severity;
  check_id: string;
  title: string;
  description: string;
  detected_at: string | null;
  acknowledged_at: string | null;
  acknowledged_note: string | null;
}

export type Effort = "low" | "medium" | "high";
export type Impact = "low" | "medium" | "high" | "critical";

export interface Recommendation {
  id: number;
  device_id: number;
  risk_id: number;
  check_id: string;
  severity: Severity;
  title: string;
  description: string;
  steps: string[];
  effort: Effort;
  impact: Impact;
  attack_scenario: string | null;
  likelihood: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RiskSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface ScanEvent {
  id: number;
  scan_id: number;
  device_id: number | null;
  event_type:
    | "device_appeared"
    | "device_disappeared"
    | "port_opened"
    | "port_closed"
    | "risk_appeared"
    | "risk_resolved";
  detail: string | null; // JSON string
  occurred_at: string | null;
  reviewed: boolean;
}

export interface ChangesSummary {
  unreviewed: number;
}
