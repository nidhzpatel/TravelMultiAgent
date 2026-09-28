from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


class TravelPlanRequest(BaseModel):
    destination: str = Field(..., min_length=2, description="Destination city or country")
    origin: str = Field(..., min_length=2, description="Origin city or airport")
    start_date: date = Field(..., description="Trip start date")
    end_date: date = Field(..., description="Trip end date")
    travelers: int = Field(1, ge=1, description="Number of travelers")
    total_budget_usd: float = Field(..., gt=0, description="Total trip budget in USD (internal agent math)")
    currency: str = Field("USD", description="Original currency code for display: USD, INR, EUR, GBP, etc.")
    total_budget: float = Field(0, description="Original currency budget amount for display")
    exchange_rate: float = Field(1.0, description="Original currency units per 1 USD")
    interests: List[str] = Field(default_factory=list, description="Travel interest tags")
    radius_km: int = Field(300, ge=10, le=2000, description="All visited places must lie within this radius of the destination (km)")
    food_preference: Optional[str] = Field(None, description="Food the traveler eats: vegetarian, non-vegetarian, vegan, jain, halal, kosher, gluten-free, or cuisine style")
    travel_style: str = Field("balanced", description="budget | balanced | luxury")
    cover_nearby: Optional[bool] = Field(True, description="Whether to include nearby places/day trips when days allow")
    dietary_notes: Optional[str] = Field(None, description="Dietary restrictions or preferences")
    mobility_notes: Optional[str] = Field(None, description="Mobility constraints")
    transport_preference: Optional[str] = Field(None, description="Explicit user choice: flight | train | bus (None = let the transit mode selector decide)")
    free_text: Optional[str] = Field(None, description="Additional natural-language context")


class ParsedTravelRequest(BaseModel):
    destination: str
    origin: Optional[str]
    start_date: date
    end_date: date
    travelers: int
    total_budget_usd: float
    interests: List[str]
    travel_style: str
    flights_needed: bool
    number_of_days: int
    extra_notes: Optional[str]


class TransitLeg(BaseModel):
    day_number: Optional[int] = Field(None, description="Day this leg belongs to")
    from_location: str
    to_location: str
    mode: str = Field(..., description="flight | train | bus | metro | cab | walk")
    provider: str
    estimated_cost: float
    estimated_cost_usd: float
    duration_minutes: int
    notes: str


class DraftItineraryDay(BaseModel):
    day_number: int
    date: str
    region: str = Field(..., description="Region or area for the day, e.g., 'North Goa', 'Old Manali'")
    base_location: str = Field(..., description="Where the hotel is for this night")
    transit_from: Optional[str] = Field(None, description="Where the day starts, if different from base")
    transit_to: Optional[str] = Field(None, description="Where the day ends, if different from base")
    theme: str = Field(..., description="High-level theme for the day, e.g., 'beach day', 'heritage day'")
    activity_focus: List[str] = Field(default_factory=list, description="Interest tags for this day")


class DraftItinerary(BaseModel):
    days: List[DraftItineraryDay]
    transit_legs: List[TransitLeg] = Field(default_factory=list)
    hotel_regions: List[str] = Field(default_factory=list, description="Distinct base locations where hotels are needed")


class StayOption(BaseModel):
    night_number: int
    hotel_name: str
    location: str
    room_type: str
    estimated_cost: float
    estimated_cost_usd: float
    why_this_choice: str
    booking_notes: str


class ActivityItem(BaseModel):
    time_slot: str = Field(..., description="e.g., 09:00 AM - 11:30 AM")
    activity_name: str
    location: str
    category: str = Field(..., description="sightseeing | food | shopping | rest | transit")
    # Activity prices (sightseeing, attractions, meals) are intentionally hidden
    # from the traveler; only the plan is shown. None means "not priced".
    estimated_cost: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    notes: str


class CabServiceCharge(BaseModel):
    vehicle_type: str = Field(..., description="e.g., 'Private AC Sedan'")
    coverage: str = Field(..., description="What the cab package covers")
    total_days: int
    estimated_cost: float
    estimated_cost_usd: float
    notes: str


class DayItinerary(BaseModel):
    day_number: int
    date: str
    theme: str
    region: Optional[str] = Field(None, description="Region or area for the day")
    meals_included: List[str] = Field(default_factory=list, description="Meals included or planned for the day, e.g., ['breakfast', 'dinner']")
    activities: List[ActivityItem]
    transit_legs: List[TransitLeg]
    stay: Optional[StayOption]
    daily_transit_cost: float
    daily_transit_cost_usd: float
    daily_activity_cost: float
    daily_activity_cost_usd: float
    daily_stay_cost: float
    daily_stay_cost_usd: float
    total_daily_cost: float
    total_daily_cost_usd: float


class MasterTravelItinerary(BaseModel):
    destination: str
    origin: Optional[str]
    total_budget: float
    total_budget_usd: float
    actual_calculated_cost: float
    actual_calculated_cost_usd: float
    currency: str = "USD"
    exchange_rate: float = 1.0
    travelers: int
    radius_km: Optional[int] = Field(None, description="Travel radius from the destination used for planning (km)")
    food_preference: Optional[str] = Field(None, description="Food preference the stays and meals were planned around")
    days: List[DayItinerary]
    transit_summary: str
    stay_summary: str
    sightseeing_summary: str
    trip_scope: Optional[str] = Field(None, description="e.g., 'Goa + nearby day trips'")
    cab_service: Optional[CabServiceCharge] = Field(None, description="Overall cab package charge for the whole trip")
    inclusions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    notes: List[str]


class TravelPlanResponse(BaseModel):
    session_id: Optional[str] = None
    status: str
    itinerary: Optional[MasterTravelItinerary] = None
    error: Optional[str] = None


class PromptParseRequest(BaseModel):
    prompt: str = Field(..., min_length=3, description="Free-text travel request")


class PromptParseResponse(BaseModel):
    extracted: dict = Field(default_factory=dict, description="Fields successfully extracted from the prompt")
    missing: List[str] = Field(default_factory=list, description="Required fields still missing")
    parsed: dict = Field(default_factory=dict, description="Full parsed object returned by the parser agent")


class ChatMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str
    type: str = Field("text", description="text | itinerary_update | alternatives")
    payload: dict = Field(default_factory=dict)
    created_at: str = Field("", description="ISO timestamp")


class ChatSession(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessage]
    current_itinerary: Optional[MasterTravelItinerary] = None


class ChatCreateRequest(BaseModel):
    message: str = Field(..., min_length=1, description="First user message")


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User follow-up message")


class ChatMessageResponse(BaseModel):
    session_id: str
    message: ChatMessage
    session: ChatSession
