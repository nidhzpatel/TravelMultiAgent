/** Checked mirror of backend/app/domain/contracts.py for the v2 API. */

export type FactStatus = "VERIFIED" | "UNVERIFIED" | "UNKNOWN" | "STALE";
export type PriceStatus = "VERIFIED" | "ESTIMATED" | "USER_PROVIDED" | "UNKNOWN";
export type Provenance = "LIVE" | "MOCK" | "USER" | "LEGACY";
export type TripReadiness = "DRAFT" | "ACTION_REQUIRED" | "READY_TO_BOOK";

export interface Money {
  amount: string | null;
  currency: string;
  status: PriceStatus;
  provenance: Provenance;
  evidence_ids: string[];
}

export type ProviderOutcomeStatus = "SUCCESS" | "NO_RESULTS" | "UNAVAILABLE" | "ERROR" | "MOCK";

export interface Evidence {
  id: string;
  source: string;
  reference_url: string | null;
  retrieved_at: string;
  expires_at: string | null;
  covered_fields: string[];
  provenance: Provenance;
  provider_outcome: ProviderOutcomeStatus;
  retention_permitted: boolean;
  retention_until: string | null;
}

export interface FxSnapshot {
  base_currency: string;
  quote_currency: string;
  rate: string;
  captured_at: string;
  evidence_id: string | null;
}

export interface Expense {
  id: string;
  category: "flight" | "hotel" | "transport" | "food" | "activity" | "tax" | "contingency";
  money: Money;
  unit: "item" | "person" | "night" | "room" | "leg" | "trip";
  quantity: string;
  taxes: Money[];
  taxes_included: boolean;
  exclusions: string[];
  included: boolean;
  mandatory: boolean;
  fx_snapshot: FxSnapshot | null;
}

export interface Budget {
  id: string;
  target: Money;
  expense_ids: string[];
  expenses: Expense[];
  evidence: Evidence[];
}

export interface BudgetBreakdown {
  currency: string;
  verified_subtotal: string;
  estimated_subtotal: string;
  user_provided_subtotal: string;
  taxes_total: string;
  contingency_total: string;
  known_total: string;
  unknown_expense_ids: string[];
  mandatory_unknown_expense_ids: string[];
  feasibility: "WITHIN_BUDGET" | "OVER_BUDGET" | "UNKNOWN";
  shortfall: string | null;
}

export interface BudgetView {
  breakdown: BudgetBreakdown;
  expenses: Expense[];
  evidence: Evidence[];
}

export interface Fact {
  value: string | number | boolean | null;
  status: FactStatus;
  evidence_ids: string[];
  valid_at: string | null;
}

export interface TripBrief {
  origin: string | null;
  destination_text: string;
  start_date: string | null;
  end_date: string | null;
  travelers: number;
}

export interface TravelerPreferences {
  interests: string[];
  pace: "slow" | "balanced" | "fast";
  dietary_requirements: string[];
  mobility_requirements: string[];
  lodging_preferences: string[];
  transport_preferences: string[];
}

export interface Destination {
  id: string;
  name: string;
  provider_place_id: string | null;
  latitude: string | null;
  longitude: string | null;
  timezone: string | null;
  evidence_ids: string[];
}

export interface OpeningWindow {
  opens_at: string;
  closes_at: string;
}

export interface ScheduledItem {
  id: string;
  kind: "activity" | "restaurant" | "flight" | "hotel" | "transport";
  entity_id: string;
  destination_id: string | null;
  start_at: string | null;
  end_at: string | null;
  opening_windows: OpeningWindow[];
  required_buffer_minutes: number;
  critical: boolean;
}

export interface TripDay {
  id: string;
  local_date: string;
  timezone: string;
  scheduled_item_ids: string[];
  scheduled_items: ScheduledItem[];
}

export interface TransportLeg {
  id: string;
  origin_destination_id: string;
  destination_destination_id: string;
  mode: "flight" | "train" | "bus" | "metro" | "cab" | "walk";
  route_status: "REACHABLE" | "UNREACHABLE" | "UNKNOWN";
  duration_minutes: Fact;
  distance_km: string | null;
  depart_at: string | null;
  arrive_at: string | null;
  source_provider: string | null;
  retrieved_at: string | null;
  expires_at: string | null;
  evidence_ids: string[];
  expense_ids: string[];
}

export interface Trip {
  id: string;
  owner_id: string;
  title: string;
  brief: TripBrief;
  preferences: TravelerPreferences;
  budget: Budget;
  destination_ids: string[];
  day_ids: string[];
  destinations: Destination[];
  days: TripDay[];
  transport_legs: TransportLeg[];
  radius_km: string;
  readiness: TripReadiness;
}

export interface TripVersion {
  trip_id: string;
  version: number;
  created_at: string;
  trip: Trip;
}

export interface Operation {
  kind: "READ" | "ADD" | "REMOVE" | "REPLACE" | "MOVE" | "REORDER" | "REPLAN";
  target_id?: string | null;
  path?: "title" | "preferences.interests" | "preferences.pace" | null;
  value?: string | null;
  values?: string[] | null;
  index?: number | null;
}

export interface ProposalRequest {
  expected_version: number;
  idempotency_key: string;
  operations: Operation[];
}

export interface ProposalPreview {
  proposal_id: string;
  base_version: number;
  preview: Trip;
  changed_fields: string[];
  changes: Array<{ entity_id: string; fields: string[] }>;
}
