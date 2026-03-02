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

export type DeviceType =
  | "iot"
  | "server"
  | "router"
  | "workstation"
  | "unknown";

export interface Device {
  id: number;
  ip_address: string;
  mac_address: string | null;
  vendor: string | null;
  hostname: string | null;
  os_guess: string | null;
  label: string | null;
  trusted: boolean;
  device_type: DeviceType | null;
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
  display_severity: Severity;
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

export type NetworkProfile = "standard_home" | "home_lab" | "privacy_focused";

export interface Settings {
  webhook_url: string | null;
  network_profile: NetworkProfile;
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

export type ChecklistAnswer = "yes" | "no" | "unknown";
export type PostureBadge = "at_risk" | "basic" | "intermediate" | "hardened";

export interface ChecklistItem {
  key: string;
  question: string;
  advice: string;
  answer: ChecklistAnswer;
}

export interface ChecklistState {
  items: ChecklistItem[];
  posture: PostureBadge;
  posture_label: string;
  yes_count: number;
}

export interface MixedRiskPair {
  iot_device_id: number;
  iot_ip: string;
  server_device_id: number;
  server_ip: string;
  shared_subnet: string;
}

export interface SegmentationInsight {
  flat_network: boolean;
  iot_count: number;
  server_count: number;
  mixed_risk_pairs: MixedRiskPair[];
  recommendations: string[];
}

export interface TopologyNode {
  id: number;
  ip_address: string;
  label: string | null;
  hostname: string | null;
  device_type: DeviceType;
  highest_severity: Severity | null;
  port_count: number;
  security_score: number;
  is_gateway: boolean;
}

export interface WanInfo {
  wan_ip: string | null;
  detected_at: string | null; // ISO-8601 or null
}
