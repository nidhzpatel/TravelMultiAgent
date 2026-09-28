export interface TravelPlanRequest {
  destination: string
  origin: string
  start_date: string
  end_date: string
  travelers: number
  total_budget_usd: number
  currency: string
  total_budget?: number
  exchange_rate?: number
  interests: string[]
  radius_km?: number
  food_preference?: string
  travel_style: string
  cover_nearby?: boolean
  dietary_notes?: string
  mobility_notes?: string
  transport_preference?: string
  free_text?: string
}

export interface PromptParseRequest {
  prompt: string
}

export interface PromptParseResponse {
  extracted: Partial<TravelPlanRequest>
  missing: string[]
  parsed: Record<string, unknown>
}

export interface TransitLeg {
  day_number: number | null
  from_location: string
  to_location: string
  mode: string
  provider: string
  estimated_cost: number
  estimated_cost_usd: number
  duration_minutes: number
  notes: string
}

export interface StayOption {
  night_number: number
  hotel_name: string
  location: string
  room_type: string
  estimated_cost: number
  estimated_cost_usd: number
  why_this_choice: string
  booking_notes: string
}

export interface ActivityItem {
  time_slot: string
  activity_name: string
  location: string
  category: string
  estimated_cost: number | null
  estimated_cost_usd: number | null
  notes: string
}

export interface CabServiceCharge {
  vehicle_type: string
  coverage: string
  total_days: number
  estimated_cost: number
  estimated_cost_usd: number
  notes: string
}

export interface DayItinerary {
  day_number: number
  date: string
  theme: string
  region?: string
  meals_included: string[]
  activities: ActivityItem[]
  transit_legs: TransitLeg[]
  stay: StayOption | null
  daily_transit_cost: number
  daily_transit_cost_usd: number
  daily_activity_cost: number
  daily_activity_cost_usd: number
  daily_stay_cost: number
  daily_stay_cost_usd: number
  total_daily_cost: number
  total_daily_cost_usd: number
}

export interface MasterTravelItinerary {
  destination: string
  origin: string | null
  total_budget: number
  total_budget_usd: number
  actual_calculated_cost: number
  actual_calculated_cost_usd: number
  currency: string
  exchange_rate: number
  travelers: number
  radius_km?: number | null
  food_preference?: string | null
  days: DayItinerary[]
  transit_summary: string
  stay_summary: string
  sightseeing_summary: string
  trip_scope?: string
  cab_service?: CabServiceCharge | null
  inclusions: string[]
  exclusions: string[]
  notes: string[]
}

export interface TravelPlanResponse {
  session_id: string | null
  status: string
  itinerary: MasterTravelItinerary | null
  error: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  type: 'text' | 'itinerary_update' | 'alternatives'
  payload?: {
    itinerary?: MasterTravelItinerary
    alternatives?: unknown[]
    suggested_actions?: string[]
  }
  created_at?: string
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages: ChatMessage[]
  current_itinerary: MasterTravelItinerary | null
}

export interface ChatCreateRequest {
  message: string
}

export interface ChatMessageRequest {
  message: string
}

export interface ChatMessageResponse {
  session_id: string
  message: ChatMessage
  session: ChatSession
}
