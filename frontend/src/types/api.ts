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
  first_seen: string | null; // ISO-8601
  last_seen: string | null;
  ports: Port[];
}

export interface Scan {
  id: number;
  status: string;
  triggered_by: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  devices_found: number | null;
  error_message: string | null;
}

export interface TriggerResponse {
  message: string;
  scan_id: number | null;
}

export type Severity = "critical" | "high" | "medium" | "low";

export interface Risk {
  id: number;
  device_id: number;
  severity: Severity;
  check_id: string;
  title: string;
  description: string;
  detected_at: string | null;
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
