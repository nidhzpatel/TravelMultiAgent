/** Checked mirror of backend/app/domain/contracts.py for the v2 API. */

export type FactStatus = "VERIFIED" | "UNVERIFIED" | "UNKNOWN" | "STALE";
export type PriceStatus = "VERIFIED" | "ESTIMATED" | "USER_PROVIDED" | "UNKNOWN";
export type Provenance = "LIVE" | "MOCK" | "USER" | "LEGACY";
export type TripReadiness = "DRAFT" | "ACTION_REQUIRED" | "READY_TO_BOOK";

export interface Money {
  amount: string;
  currency: string;
  status: PriceStatus;
  provenance: Provenance;
  evidence_ids: string[];
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

export interface Trip {
  id: string;
  owner_id: string;
  title: string;
  brief: TripBrief;
  preferences: TravelerPreferences;
  readiness: TripReadiness;
}

export interface TripVersion {
  trip_id: string;
  version: number;
  created_at: string;
  trip: Trip;
}
