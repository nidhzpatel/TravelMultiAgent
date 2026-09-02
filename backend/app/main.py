import asyncio
import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any

import httpx

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fpdf import FPDF

from app.config import get_settings
from app.schemas import (
    TravelPlanRequest,
    TravelPlanResponse,
    PromptParseRequest,
    PromptParseResponse,
    MasterTravelItinerary,
    DayItinerary,
    ActivityItem,
    TransitLeg,
    StayOption,
    DraftItinerary,
    DraftItineraryDay,
)
from app.crew.crew import (
    build_parse_crew,
    build_skeleton_crew,
    build_travel_crew,
    build_stay_crew,
    build_sightseeing_crew,
    build_assembly_crew,
)
from app.crew.tools import (
    flight_search_tool,
    hotel_search_tool,
    attraction_search_tool,
)

settings = get_settings()

# In-memory store for completed itineraries so the PDF endpoint can fetch them by session_id.
itinerary_store: dict[str, MasterTravelItinerary] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _format_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _extract_json(raw: str) -> Any:
    """Extract a JSON object or array from agent output, handling markdown wrappers and comments."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # Remove single-line JSON comments (// ...).
    cleaned = re.sub(r"\s*//[^\n]*", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON object or array found in output")
    return json.loads(match.group(0))


def _extract_hotel_name_from_context(base: str, search_context: dict[str, str]) -> str | None:
    """Try to pull a real hotel name from the Serper search context for a base location."""
    context = search_context.get(f"hotel_{base}") or ""
    if not context or "No live web results" in context or "MockHotel" in context:
        return None

    skip_phrases = [
        "best", "top", "hotels in", "things to do", "what to do", "vs ",
        "guide", "compare", "downtown hotels", "hotel destinations",
        "find hotels", "book a stay",
    ]

    # Serper snippets often contain numbered lists like "1. Hard Rock Hotel Goa · 2. ...".
    # Extract the first real-looking entry from those lists.
    candidates = re.findall(
        r"(?:\d+\.\s*|\d+\)\s*|•\s*|\-\s*)([A-Z][A-Za-z0-9&\s'’\-]{2,60}?)(?=\s*[·,;|\n]|$)",
        context,
    )
    for candidate in candidates:
        candidate = candidate.strip()
        if len(candidate.split()) < 2:
            continue
        lower = candidate.lower()
        if any(phrase in lower for phrase in skip_phrases):
            continue
        return candidate

    # Fallback: use the first non-listicle result title.
    for line in context.splitlines():
        line = line.strip()
        if line.startswith("- "):
            title = line[2:].split(":")[0].strip()
            if not title:
                continue
            lower = title.lower()
            if any(phrase in lower for phrase in skip_phrases):
                continue
            return title
    return None


# Maps currency symbols/words to ISO currency codes.
_CURRENCY_SYMBOL_TO_CODE: dict[str, str] = {
    "inr": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "₹": "INR",
    "rs": "INR",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "€": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "£": "GBP",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "$": "USD",
}

# Fallback rates (USD base) used when the live API is unreachable.
_CURRENCY_RATES: dict[str, float] = {
    "inr": 86.0,
    "rupee": 86.0,
    "rupees": 86.0,
    "₹": 86.0,
    "rs": 86.0,
    "eur": 0.92,
    "euro": 0.92,
    "euros": 0.92,
    "€": 0.92,
    "gbp": 0.79,
    "pound": 0.79,
    "pounds": 0.79,
    "£": 0.79,
    "usd": 1.0,
    "dollar": 1.0,
    "dollars": 1.0,
    "$": 1.0,
}

# Maps common countries/destinations to currency codes when user omits currency.
_COUNTRY_CURRENCY_MAP: dict[str, str] = {
    "india": "INR",
    "usa": "USD",
    "united states": "USD",
    "america": "USD",
    "uk": "GBP",
    "united kingdom": "GBP",
    "britain": "GBP",
    "england": "GBP",
    "germany": "EUR",
    "france": "EUR",
    "italy": "EUR",
    "spain": "EUR",
    "netherlands": "EUR",
    "portugal": "EUR",
    "belgium": "EUR",
    "austria": "EUR",
    "greece": "EUR",
    "ireland": "EUR",
    "uae": "AED",
    "dubai": "AED",
    "abu dhabi": "AED",
    "japan": "JPY",
    "tokyo": "JPY",
    "australia": "AUD",
    "canada": "CAD",
    "thailand": "THB",
    "bangkok": "THB",
    "singapore": "SGD",
    "malaysia": "MYR",
    "kuala lumpur": "MYR",
    "indonesia": "IDR",
    "bali": "IDR",
    "vietnam": "VND",
    "nepal": "NPR",
    "sri lanka": "LKR",
    "turkey": "TRY",
    "switzerland": "CHF",
}

# Live exchange-rate cache.
_exchange_rate_cache: dict[str, Any] = {"rates": {}, "fetched_at": 0.0}
_EXCHANGE_RATE_TTL_SECONDS = 3600


def _fetch_exchange_rates() -> dict[str, float]:
    """Fetch USD-based exchange rates from a free API, with in-memory caching."""
    now = time.time()
    if now - _exchange_rate_cache["fetched_at"] < _EXCHANGE_RATE_TTL_SECONDS and _exchange_rate_cache["rates"]:
        return _exchange_rate_cache["rates"]

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get("https://open.er-api.com/v6/latest/USD")
            response.raise_for_status()
            data = response.json()
            rates = data.get("rates", {})
            if rates:
                _exchange_rate_cache["rates"] = rates
                _exchange_rate_cache["fetched_at"] = now
                return rates
    except Exception:
        pass

    # Fallback to hardcoded rates if API fails.
    return {
        "INR": 86.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "USD": 1.0,
        "AED": 3.67,
        "JPY": 145.0,
        "AUD": 1.5,
        "CAD": 1.36,
        "THB": 34.0,
        "SGD": 1.34,
        "MYR": 4.4,
        "IDR": 15500.0,
        "VND": 24500.0,
        "NPR": 138.0,
        "LKR": 300.0,
        "TRY": 34.0,
        "CHF": 0.88,
    }


_BUDGET_RE = re.compile(
    r"(?:budget\s*(?:of|is|around|about|approx|approximately)?\s*)"
    r"(?:[₹€£$]|inr|rs|rupees?|euros?|pounds?|gbp)?\s*"
    r"([\d,]+(?:\.\d+)?)\s*(k|thousand|million|mn|m)?\s*"
    r"(?:inr|rs|rupees?|euros?|pounds?|gbp|[₹€£$])?|"
    r"(?:[₹€£$]|inr|rs|rupees?|euros?|pounds?|gbp)\s*"
    r"([\d,]+(?:\.\d+)?)\s*(k|thousand|million|mn|m)?|"
    r"([\d,]+(?:\.\d+)?)\s*(k|thousand|million|mn|m)?\s*"
    r"(?:inr|rs|rupees?|euros?|pounds?|gbp|[₹€£$])",
    re.IGNORECASE,
)

_NUMBER_WORDS = {
    "k": 1_000,
    "thousand": 1_000,
    "million": 1_000_000,
    "mn": 1_000_000,
    "m": 1_000_000,
}

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
]

_WEEK_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "1st": 1,
    "2nd": 2,
    "3rd": 3,
    "4th": 4,
    "5th": 5,
}

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _build_iso_date(day_str: str, month_str: str, year: int) -> str | None:
    """Build an ISO date string from parsed day/month/year components."""
    try:
        day = int(day_str)
        month = _MONTHS.get(month_str.lower())
        if not month:
            return None
        return date(year, month, day).isoformat()
    except (ValueError, TypeError):
        return None

_RELATIVE_RANGE_RE = re.compile(
    r"(?:(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+week\s+of\s+)?"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?",
    re.IGNORECASE,
)

_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?\s*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s*(\d{4})?\s*(?:to|until|till|-|and)\s*"
    r"(\d{1,2})(?:st|nd|rd|th)?\s*(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s*(\d{4})?",
    re.IGNORECASE,
)


def _normalize_date(value: Any) -> str | None:
    """Parse a date string in various formats and return ISO YYYY-MM-DD."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _next_weekday(weekday: int) -> date:
    """Return the next occurrence of the given weekday (0=Monday)."""
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


_TRIP_DURATION_RE = re.compile(
    r"(\d+)\s*(?:day|days)\s*(?:trip|travel|tour|vacation|itinerary)",
    re.IGNORECASE,
)

_RELATIVE_DATE_RE = re.compile(
    r"\b(today|tomorrow|yesterday|next\s+week|this\s+week|coming\s+week)\b",
    re.IGNORECASE,
)


def _parse_relative_date_range(text: str) -> tuple[str, str] | None:
    """Parse natural-language date phrases into ISO start/end dates."""
    if not text:
        return None

    text_lower = text.lower()
    today = date.today()

    # Handle explicit day counts like "5 day trip", "3 days from tomorrow".
    duration_match = _TRIP_DURATION_RE.search(text)
    duration_days = int(duration_match.group(1)) if duration_match else None

    # Determine the anchor date.
    anchor: date | None = None

    if "tomorrow" in text_lower:
        anchor = today + timedelta(days=1)
    elif "today" in text_lower or "from now" in text_lower:
        anchor = today
    elif "yesterday" in text_lower:
        anchor = today - timedelta(days=1)
    elif "next week" in text_lower or "coming week" in text_lower:
        anchor = _next_weekday(0)  # Next Monday.
    elif "this week" in text_lower:
        anchor = today

    if anchor and duration_days is not None:
        start_date = anchor
        end_date = anchor + timedelta(days=duration_days - 1)
        return start_date.isoformat(), end_date.isoformat()

    if anchor:
        # Anchor without explicit duration: default to a 5-day trip.
        return anchor.isoformat(), (anchor + timedelta(days=4)).isoformat()

    # Handle "first week of September 2026" etc.
    match = _RELATIVE_RANGE_RE.search(text)
    if match:
        week_key = match.group(1)
        month_name = match.group(2)
        year_str = match.group(3)

        month = _MONTHS.get(month_name.lower())
        if not month:
            return None

        year = int(year_str) if year_str else today.year
        if not year_str and (today.month > month or (today.month == month and today.day > 28)):
            year += 1

        week_number = _WEEK_ORDINALS.get(week_key.lower()) if week_key else 1
        first_day_of_month = date(year, month, 1)
        start_date = first_day_of_month + timedelta(weeks=week_number - 1)
        end_date = start_date + timedelta(days=6)
        return start_date.isoformat(), end_date.isoformat()

    return None


def _detect_currency_from_prompt(prompt: str) -> str | None:
    """Return a currency code if an explicit currency symbol/code is found in the prompt."""
    prompt_lower = prompt.lower()
    for symbol in sorted(_CURRENCY_SYMBOL_TO_CODE.keys(), key=len, reverse=True):
        if symbol in prompt_lower:
            return _CURRENCY_SYMBOL_TO_CODE[symbol]
    return None


def _infer_currency_from_locations(origin: str, destination: str) -> str | None:
    """Infer currency from origin/destination when user does not mention one."""
    combined = f"{origin} {destination}".lower()
    for place, code in _COUNTRY_CURRENCY_MAP.items():
        if place in combined:
            return code
    return None


def _normalize_budget(value: Any, prompt: str, origin: str, destination: str) -> tuple[float, str, float] | None:
    """Convert a budget value to USD while preserving the original currency.

    Returns (usd_amount, currency_code, exchange_rate) or None on failure.
    Handles formats like 4000, $4,000, 4k, 4 thousand, ₹2,00,000, 200000 INR.
    """
    prompt_lower = prompt.lower()

    # 1. Try explicit currency from prompt.
    currency_code = _detect_currency_from_prompt(prompt)

    # 2. Infer from origin/destination if not explicit.
    if currency_code is None:
        currency_code = _infer_currency_from_locations(origin, destination)

    # 3. Default to USD.
    if currency_code is None:
        currency_code = "USD"

    rates = _fetch_exchange_rates()
    exchange_rate = rates.get(currency_code.upper())
    if exchange_rate is None:
        exchange_rate = _CURRENCY_RATES.get(currency_code.lower(), 1.0)

    # Parse the raw amount from the prompt if possible.
    match = _BUDGET_RE.search(prompt)
    if match:
        raw_amount_str = (
            match.group(1) or match.group(3) or match.group(5) or ""
        ).replace(",", "")
        multiplier_word = (
            match.group(2) or match.group(4) or match.group(6) or ""
        ).lower()
        try:
            raw_amount = float(raw_amount_str)
            multiplier = _NUMBER_WORDS.get(multiplier_word, 1)
            original_amount = raw_amount * multiplier
            usd_amount = original_amount / exchange_rate
            return round(usd_amount, 2), currency_code.upper(), exchange_rate
        except (TypeError, ValueError):
            pass

    # Fallback: trust the numeric value and treat it as the original currency.
    try:
        original_amount = float(value)
        usd_amount = original_amount / exchange_rate
        return round(usd_amount, 2), currency_code.upper(), exchange_rate
    except (TypeError, ValueError):
        return None


_INTEREST_SYNONYMS = {
    "nightlife": ["night life", "night-life", "nightlift", "night club", "night clubs", "clubbing", "partying", "party", "bars", "pubs"],
    "history": ["historic places", "historical places", "historical sites", "monuments", "heritage", "forts", "palaces", "historic", "historical"],
    "shopping": ["shopping malls", "markets", "shopping districts", "buying", "retail", "mall"],
    "food": ["street food", "local food", "cuisine", "restaurants", "eating", "dining", "foodie", "gastronomy"],
    "nature": ["parks", "gardens", "wildlife", "scenic", "outdoors", "forest", "lakes"],
    "beaches": ["beach", "sea", "ocean", "coast", "sand", "sunbathing"],
    "museums": ["museum", "art galleries", "gallery", "exhibitions", "art"],
    "temples": ["temple", "shrines", "religious sites", "spiritual", "mosques", "churches"],
    "tech": ["technology", "gadgets", "electronics", "innovation", "science"],
    "mountains": ["mountain", "hills", "hill station", "hiking", "trekking", "trek", "camping"],
}

_DIETARY_SYNONYMS = {
    "vegetarian": ["veg", "veggie", "no meat", "meat-free", "plant-based", "veg only", "pure veg", "no non-veg"],
    "vegan": ["no dairy", "no animal products", "no eggs", "no honey"],
    "halal": ["halal food", "halal meat"],
    "kosher": ["kosher food"],
    "gluten-free": ["gluten free", "no gluten", "celiac"],
    "jain": ["jain food", "no onion", "no garlic"],
}


def _clean_place_candidate(text: str) -> str | None:
    """Clean a raw string into a concise place name, or return None if it is generic."""
    text = re.sub(r"^(?:\d+\.\s*|\d+\)\s*|•\s*|\-\s*)", "", text)
    text = re.sub(
        r"\s+(day trips?|tours?|excursion|safari|cruise|full-day|half-day|private city|from|nearby|guide)$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    # Strip trailing noise like ellipsis, colons, dashes, or dangling "and".
    text = re.sub(r"\s*[: ]\s*(?:\.{3}|…)\s*$", "", text).strip()
    text = re.sub(r"\s*(?:\.{3}|…|:|–|-)\s*$", "", text).strip()
    text = re.sub(r"\s+and\s*$", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return None

    words = text.split()
    if len(words) < 1 or len(words) > 6:
        return None

    lower = text.lower()
    blocklist = {
        "things to do", "top things", "where to go", "places to avoid",
        "dinner", "water sports", "combo", "updated", "recommended", "best",
        "full day", "half day", "full-day", "sightseeing", "private tour", "city tour",
        "day trips", "day trip", "foot", "feet", "high", "meter", "metre",
        "private", "stay locations", "our most recommended", "stay around",
        "a full", "the full", "safari", "guided", "one-day",
        "getyourguide", "viator", "klook", "tripadvisor", "makemytrip", "jessieonajourney",
    }
    if any(phrase in lower for phrase in blocklist):
        return None

    if not any(w[0].isupper() for w in words if w):
        return None

    return text


async def _fetch_nearby_places_async(destination: str) -> list[str]:
    """Fetch nearby day-trip places from Serper for any destination."""
    if not destination or not settings.serper_api_key:
        return []

    query = f"best day trips from {destination}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    places: list[str] = []

    for item in data.get("organic", [])[:5]:
        text = f"{item.get('title', '')} · {item.get('snippet', '')}"

        # Pass 1: numbered / bulleted list items (e.g., "1. Dudhsagar Falls").
        for match in re.finditer(
            r"(?:\d+\.\s*|\d+\)\s*|•\s*|\-\s*)([A-Z][A-Za-z0-9&\s'’\-]{2,80}?)(?=\s*[·,;|\n]|$)",
            text,
        ):
            candidate = _clean_place_candidate(match.group(1))
            if candidate and candidate not in places:
                places.append(candidate)

        # Pass 2: split the whole text on common separators and clean each chunk.
        for chunk in re.split(r"[·,;|()\n]\s*|\band\b", text):
            candidate = _clean_place_candidate(chunk)
            if candidate and candidate not in places:
                places.append(candidate)

        # Pass 3: explicit place-like noun phrases ending in known location nouns.
        for match in re.finditer(
            r"([A-Z][A-Za-z0-9\s'’\-]{1,40}(?:Falls|Plantation|Beach|Fort|Temple|Island|City|Park|Gardens|Valley|Hills|Dam|Lake|Palace|Monastery|Church|Mosque))",
            text,
        ):
            candidate = _clean_place_candidate(match.group(1))
            if candidate and candidate not in places:
                places.append(candidate)

    # Drop shorter candidates that are substrings of a longer one (e.g. "Dudhsagar"
    # when "Dudhsagar Falls" is already present).
    deduped: list[str] = []
    for place in places:
        place_lower = place.lower()
        if any(place_lower in existing.lower() or existing.lower() in place_lower for existing in deduped):
            continue
        deduped.append(place)

    return deduped[:5]


def _should_cover_nearby(prompt: str, parsed_cover: Any) -> bool:
    """Default to covering nearby places unless the user explicitly opts out."""
    if isinstance(parsed_cover, bool):
        return parsed_cover
    prompt_lower = prompt.lower()
    opt_out_phrases = [
        "only ",
        "just ",
        "single destination",
        "one destination",
        "no nearby",
        "not interested in nearby",
        "stay in ",
    ]
    for phrase in opt_out_phrases:
        if phrase in prompt_lower:
            return False
    return True


def _normalize_interests(interests: list[str]) -> list[str]:
    """Normalize interest tags by merging synonyms and lowercasing."""
    normalized: list[str] = []
    for item in interests:
        item_lower = item.lower().strip()
        matched = False
        for canonical, synonyms in _INTEREST_SYNONYMS.items():
            if item_lower == canonical or item_lower in synonyms:
                if canonical not in normalized:
                    normalized.append(canonical)
                matched = True
                break
        if not matched and item_lower and item_lower not in normalized:
            normalized.append(item_lower)
    return normalized


def _normalize_dietary(note: str) -> str:
    """Normalize dietary note text using common synonyms."""
    if not note:
        return note
    note_lower = note.lower().strip()
    for canonical, synonyms in _DIETARY_SYNONYMS.items():
        checks = [canonical, *synonyms]
        if any(check in note_lower for check in checks):
            return canonical
    return note_lower


_ORIGIN_DEST_STOPWORDS = {
    "a", "an", "the", "my", "me", "i", "we", "us", "home", "here", "there",
    "today", "tomorrow", "yesterday", "next", "this", "coming", "week", "month",
    "budget", "plan", "trip", "travel", "for", "with", "and", "or", "of", "in",
    "on", "at", "from", "to", "between", "starting", "ending", "returning",
}


def _extract_origin_destination(prompt: str) -> tuple[str | None, str | None]:
    """Rule-based fallback for origin/destination when the LLM parser misses them."""
    p = prompt.lower()
    origin: str | None = None
    destination: str | None = None

    # from <origin> to <destination>
    m = re.search(
        r"from\s+([a-z][a-z\s,]{1,40}?)\s+to\s+([a-z][a-z\s,]{1,40}?)"
        r"(?=\s+(?:for|between|budget|with|and|on|in|starting|ending|from|to|returning|today|tomorrow|next|this)\b|$)",
        p,
    )
    if m:
        origin = m.group(1).strip().title()
        destination = m.group(2).strip().title()
        return origin, destination

    # to <destination> from <origin>
    m = re.search(
        r"to\s+([a-z][a-z\s,]{1,40}?)\s+from\s+([a-z][a-z\s,]{1,40}?)"
        r"(?=\s+(?:for|between|budget|with|and|on|in|starting|ending|returning|today|tomorrow|next|this)\b|$)",
        p,
    )
    if m:
        destination = m.group(1).strip().title()
        origin = m.group(2).strip().title()
        return origin, destination

    # travel/going/want to go to <destination>
    m = re.search(
        r"(?:travel|traveling|travelling|going|go|wants?\s+to\s+(?:go|travel|travelling))\s+(?:to\s+)?([a-z][a-z\s,]{1,40}?)"
        r"(?=\s+(?:from|for|between|budget|with|and|on|in|starting|ending|returning|today|tomorrow|next|this)\b|$)",
        p,
    )
    if m:
        destination = m.group(1).strip().title()

    # standalone from <origin>
    m = re.search(
        r"from\s+([a-z][a-z\s,]{1,40}?)"
        r"(?=\s+(?:to|for|between|budget|with|and|on|in|starting|ending|returning|today|tomorrow|next|this)\b|$)",
        p,
    )
    if m:
        origin = m.group(1).strip().title()

    # standalone to <destination> if destination still missing
    if not destination:
        m = re.search(
            r"\bto\s+([a-z][a-z\s,]{1,40}?)"
            r"(?=\s+(?:from|for|between|budget|with|and|on|in|starting|ending|returning|today|tomorrow|next|this)\b|$)",
            p,
        )
        if m:
            destination = m.group(1).strip().title()

    # Drop obvious stopwords / single-letter garbage.
    if origin and origin.lower() in _ORIGIN_DEST_STOPWORDS:
        origin = None
    if destination and destination.lower() in _ORIGIN_DEST_STOPWORDS:
        destination = None

    return origin, destination


def _extract_interests_from_prompt(prompt: str) -> list[str]:
    """Rule-based fallback for interests when the LLM parser misses them."""
    found: list[str] = []
    p = prompt.lower()
    for canonical, synonyms in _INTEREST_SYNONYMS.items():
        checks = [canonical, *synonyms]
        if any(check in p for check in checks):
            found.append(canonical)
    return found


def _build_inputs(request: TravelPlanRequest, *, nearby_places: list[str] | None = None) -> dict[str, Any]:
    """Convert a TravelPlanRequest into the string/interpolation inputs used by crews."""
    delta = (request.end_date - request.start_date).days
    number_of_days = max(1, delta + 1)

    # Budget distribution for the package model:
    # - transit: 30% (40% if flights are likely needed)
    # - stay: 45% (35% if flights needed)
    # - food/meals: 20%
    # - contingency: 10%
    flights_needed = bool(request.origin.strip()) and request.origin.strip().lower() != request.destination.strip().lower()
    transit_share = 0.40 if flights_needed else 0.30
    stay_share = 0.35 if flights_needed else 0.45
    food_share = 0.20

    return {
        "destination": request.destination,
        "origin": request.origin,
        "start_date": _format_date(request.start_date),
        "end_date": _format_date(request.end_date),
        "travelers": request.travelers,
        "currency": request.currency,
        "total_budget_usd": request.total_budget_usd,
        "budget_transit_usd": round(request.total_budget_usd * transit_share, 2),
        "budget_stay_usd": round(request.total_budget_usd * stay_share, 2),
        "budget_food_usd": round(request.total_budget_usd * food_share, 2),
        "interests": ", ".join(request.interests) if request.interests else "general sightseeing",
        "travel_style": request.travel_style,
        "cover_nearby": "yes" if request.cover_nearby else "no",
        "nearby_places": ", ".join(nearby_places) if nearby_places else "none",
        "number_of_days": number_of_days,
        "dietary_notes": request.dietary_notes or "none",
        "mobility_notes": request.mobility_notes or "none",
        "free_text": request.free_text or "",
    }


def _build_parsed_raw(request: TravelPlanRequest) -> str:
    """Synthesize a parser-agent-style JSON object from a structured request."""
    delta = (request.end_date - request.start_date).days
    number_of_days = max(1, delta + 1)
    origin = request.origin or ""
    flights_needed = bool(origin.strip()) and origin.strip().lower() != request.destination.strip().lower()
    parsed = {
        "destination": request.destination,
        "origin": origin,
        "start_date": _format_date(request.start_date),
        "end_date": _format_date(request.end_date),
        "travelers": request.travelers,
        "total_budget_usd": request.total_budget_usd,
        "currency": getattr(request, "currency", "USD"),
        "interests": request.interests,
        "travel_style": request.travel_style,
        "cover_nearby": request.cover_nearby,
        "number_of_days": number_of_days,
        "flights_needed": flights_needed,
        "extra_notes": request.free_text or "",
    }
    return json.dumps(parsed)


def _default_activities(day_number: int, destination: str, exchange_rate: float = 1.0) -> list[ActivityItem]:
    """Return a varied set of default activities for any day number."""
    activity_pool = [
        ActivityItem(
            time_slot="09:00 AM - 11:30 AM",
            activity_name="Historic Downtown Walk",
            location=f"{destination} Old Town",
            category="sightseeing",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Explore the historic heart of the city on foot.",
        ),
        ActivityItem(
            time_slot="12:00 PM - 1:30 PM",
            activity_name="Local Food Market",
            location=f"{destination} Main Market",
            category="food",
            estimated_cost_usd=12.0,
            estimated_cost=_to_original(12.0, exchange_rate),
            notes="Try local street food and regional specialties.",
        ),
        ActivityItem(
            time_slot="02:00 PM - 4:30 PM",
            activity_name="Central Museum",
            location=f"{destination} Museum District",
            category="sightseeing",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Entrance fees are not included in the package.",
        ),
        ActivityItem(
            time_slot="05:00 PM - 6:30 PM",
            activity_name="Panoramic Viewpoint",
            location=f"{destination} Skyline Deck",
            category="sightseeing",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Entrance fees are not included in the package.",
        ),
        ActivityItem(
            time_slot="07:00 PM - 8:30 PM",
            activity_name="Famous Landmark Visit",
            location=f"{destination} City Center",
            category="sightseeing",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Entrance fees are not included in the package.",
        ),
        ActivityItem(
            time_slot="09:00 PM - 10:30 PM",
            activity_name="Evening Food & Nightlife",
            location=f"{destination} Entertainment District",
            category="food",
            estimated_cost_usd=20.0,
            estimated_cost=_to_original(20.0, exchange_rate),
            notes="Dinner and a relaxed evening walk through the lively district.",
        ),
        ActivityItem(
            time_slot="10:00 AM - 12:30 PM",
            activity_name="Local Neighborhood Explore",
            location=f"{destination} Arts Quarter",
            category="sightseeing",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Entrance fees are not included in the package.",
        ),
        ActivityItem(
            time_slot="02:00 PM - 4:00 PM",
            activity_name="Scenic Park or Garden",
            location=f"{destination} Central Park",
            category="sightseeing",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Entrance fees are not included in the package.",
        ),
        ActivityItem(
            time_slot="06:00 PM - 7:30 PM",
            activity_name="Shopping & Souvenirs",
            location=f"{destination} Shopping District",
            category="shopping",
            estimated_cost_usd=0.0,
            estimated_cost=_to_original(0.0, exchange_rate),
            notes="Shopping purchases are not included in the package.",
        ),
    ]

    # Pick 2-3 activities per day in a rotating pattern so every day differs.
    n = len(activity_pool)
    start = ((day_number - 1) * 2) % n
    selected = []
    for i in range(3):
        idx = (start + i) % n
        item = activity_pool[idx]
        selected.append(
            ActivityItem(
                time_slot=item.time_slot,
                activity_name=item.activity_name,
                location=item.location,
                category=item.category,
                estimated_cost_usd=item.estimated_cost_usd,
                estimated_cost=item.estimated_cost,
                notes=item.notes,
            )
        )
    return selected


def _to_original(usd_amount: float, exchange_rate: float) -> float:
    """Convert an internal USD amount to the user's original currency."""
    return round(usd_amount * exchange_rate, 2)


def _build_itinerary(
    request: TravelPlanRequest,
    draft: DraftItinerary,
    parsed_raw: str,
    transit_raw: str,
    stay_raw: str,
    sightseeing_raw: str,
    search_context: dict[str, str],
) -> MasterTravelItinerary:
    """Assemble the final itinerary from the skeleton, search context, and agent outputs."""
    exchange_rate = getattr(request, "exchange_rate", 1.0) or 1.0
    currency = getattr(request, "currency", "USD") or "USD"
    total_budget = getattr(request, "total_budget", request.total_budget_usd) or request.total_budget_usd

    try:
        parsed = _extract_json(parsed_raw)
    except Exception:
        parsed = {}

    try:
        transit_legs = [TransitLeg(**leg) for leg in _extract_json(transit_raw)]
    except Exception:
        transit_legs = []

    try:
        stays = [StayOption(**stay) for stay in _extract_json(stay_raw)]
    except Exception:
        stays = []

    # Consolidate consecutive nights at the same base to a single hotel.
    if stays:
        consolidated: list[StayOption] = []
        current: StayOption | None = None
        for stay in sorted(stays, key=lambda s: s.night_number):
            if current is None or stay.location.split('—')[0].strip().lower() != current.location.split('—')[0].strip().lower():
                current = stay
                consolidated.append(current)
            else:
                consolidated.append(
                    StayOption(
                        night_number=stay.night_number,
                        hotel_name=current.hotel_name,
                        location=current.location,
                        room_type=current.room_type,
                        estimated_cost_usd=current.estimated_cost_usd,
                        estimated_cost=_to_original(current.estimated_cost_usd, exchange_rate),
                        why_this_choice=current.why_this_choice,
                        booking_notes=current.booking_notes,
                    )
                )
        stays = consolidated

    try:
        activity_days = _extract_json(sightseeing_raw)
    except Exception:
        activity_days = []

    start = request.start_date
    end = request.end_date
    delta = (end - start).days
    number_of_days = max(1, delta + 1)

    # Build a lookup for each skeleton day.
    draft_days = {d.day_number: d for d in draft.days}

    # Default transit if the agent produced nothing; prefer real search context if available.
    if not transit_legs:
        if request.origin.strip().lower() not in {request.destination.strip().lower(), draft.days[0].base_location.strip().lower()}:
            transit_legs = [
                TransitLeg(
                    day_number=1,
                    from_location=request.origin,
                    to_location=draft.days[0].base_location,
                    mode="flight",
                    provider="Real flight search (see context)" if search_context.get("outbound_flight") else "MockAir",
                    estimated_cost_usd=260.0 * request.travelers,
                    estimated_cost=_to_original(260.0 * request.travelers, exchange_rate),
                    duration_minutes=210,
                    notes=search_context.get("outbound_flight", "Estimated outbound flight cost.")[:300],
                ),
                TransitLeg(
                    day_number=number_of_days,
                    from_location=draft.days[-1].base_location,
                    to_location=request.origin,
                    mode="flight",
                    provider="Real flight search (see context)" if search_context.get("return_flight") else "MockAir",
                    estimated_cost_usd=260.0 * request.travelers,
                    estimated_cost=_to_original(260.0 * request.travelers, exchange_rate),
                    duration_minutes=210,
                    notes=search_context.get("return_flight", "Estimated return flight cost.")[:300],
                ),
            ]
        transit_legs.append(
            TransitLeg(
                day_number=None,
                from_location="Accommodation",
                to_location="Activity area",
                mode="metro",
                provider="Local Transit",
                estimated_cost_usd=5.0 * request.travelers,
                estimated_cost=_to_original(5.0 * request.travelers, exchange_rate),
                duration_minutes=30,
                notes="Daily local transit estimate.",
            )
        )

    # Default stay if the agent produced nothing; vary by base location from the skeleton.
    if not stays:
        nightly = 120.0 if request.travel_style == "balanced" else (60.0 if request.travel_style == "budget" else 220.0)
        for night in range(1, number_of_days + 1):
            skeleton_day = draft_days.get(night)
            base = skeleton_day.base_location if skeleton_day else request.destination
            region = skeleton_day.region if skeleton_day else base
            stay_cost_usd = nightly * request.travelers
            real_hotel = _extract_hotel_name_from_context(base, search_context)
            hotel_name = real_hotel or f"Hotel in {region}"
            stays.append(
                StayOption(
                    night_number=night,
                    hotel_name=hotel_name,
                    location=f"{base} — {region}",
                    room_type=f"{request.travel_style} room",
                    estimated_cost_usd=stay_cost_usd,
                    estimated_cost=_to_original(stay_cost_usd, exchange_rate),
                    why_this_choice="Base location chosen by the route planner to minimize backtracking.",
                    booking_notes="Use the live hotel search results in the plan context for real names and booking links.",
                )
            )

    days: list[DayItinerary] = []
    total_activity_cost = 0.0
    total_transit_cost = sum(leg.estimated_cost_usd for leg in transit_legs)
    total_stay_cost = sum(stay.estimated_cost_usd for stay in stays)

    for day_index in range(number_of_days):
        day_number = day_index + 1
        current_date = start + timedelta(days=day_index)
        skeleton_day = draft_days.get(day_number)

        # Find matching activities.
        activities: list[ActivityItem] = []
        for d in activity_days:
            if isinstance(d, dict) and d.get("day_number") == day_number and isinstance(d.get("activities"), list):
                for a in d["activities"]:
                    if isinstance(a, dict):
                        category = a.get("category", "sightseeing")
                        # Package model: we only charge for food and local transport.
                        # Entrance fees, attraction tickets, and shopping are excluded.
                        raw_cost = float(a.get("estimated_cost_usd", 0) or 0)
                        cost_usd = raw_cost if category in ("food", "transit") else 0.0
                        activities.append(
                            ActivityItem(
                                time_slot=a.get("time_slot", "TBD"),
                                activity_name=a.get("activity_name", "Activity"),
                                location=a.get("location", skeleton_day.region if skeleton_day else request.destination),
                                category=category,
                                estimated_cost_usd=cost_usd,
                                estimated_cost=_to_original(cost_usd, exchange_rate),
                                notes=a.get("notes", ""),
                            )
                        )
                break

        if not activities:
            activities = _default_activities(day_number, skeleton_day.region if skeleton_day else request.destination, exchange_rate)

        day_transit = [leg for leg in transit_legs if leg.day_number == day_number]
        day_transit_cost = sum(leg.estimated_cost_usd for leg in day_transit)

        stay = next((s for s in stays if s.night_number == day_number), stays[-1] if stays else None)
        day_stay_cost = stay.estimated_cost_usd if stay else 0.0

        day_activity_cost = sum(a.estimated_cost_usd for a in activities)
        total_activity_cost += day_activity_cost

        # Meals: breakfast + dinner for multi-day trips; lunch optional on heavy activity days.
        meals = ["breakfast", "dinner"]
        if any(a.category in ("sightseeing", "nature", "adventure") for a in activities):
            meals.append("lunch")

        days.append(
            DayItinerary(
                day_number=day_number,
                date=current_date.isoformat(),
                theme=skeleton_day.theme if skeleton_day else f"Day {day_number} in {request.destination}",
                region=skeleton_day.region if skeleton_day else request.destination,
                meals_included=meals,
                activities=activities,
                transit_legs=day_transit,
                stay=stay,
                daily_transit_cost_usd=day_transit_cost,
                daily_transit_cost=_to_original(day_transit_cost, exchange_rate),
                daily_activity_cost_usd=day_activity_cost,
                daily_activity_cost=_to_original(day_activity_cost, exchange_rate),
                daily_stay_cost_usd=day_stay_cost,
                daily_stay_cost=_to_original(day_stay_cost, exchange_rate),
                total_daily_cost_usd=day_transit_cost + day_activity_cost + day_stay_cost,
                total_daily_cost=_to_original(day_transit_cost + day_activity_cost + day_stay_cost, exchange_rate),
            )
        )

    subtotal = total_transit_cost + total_activity_cost + total_stay_cost
    contingency = subtotal * 0.10
    actual_cost = subtotal + contingency

    origin = parsed.get("origin") or request.origin
    travelers = parsed.get("travelers") or request.travelers

    # Build inclusions / exclusions from the plan components.
    inclusions = [
        f"{number_of_days}-day itinerary covering {request.destination}",
        f"Accommodation in {len({s.location for s in stays})} base location(s)",
        "Daily breakfast and dinner",
        "Sightseeing and local transit estimates",
    ]
    if any(leg.mode == "flight" for leg in transit_legs):
        inclusions.append("Outbound and return flight estimates")

    exclusions = [
        "Personal expenses, tips, and travel insurance",
        "Activity entrance fees, attraction tickets, and optional experiences",
        "Visa costs and international roaming",
    ]
    if request.dietary_notes:
        inclusions.append(f"Dietary preference noted: {request.dietary_notes}")
    if request.mobility_notes:
        inclusions.append(f"Mobility consideration noted: {request.mobility_notes}")

    trip_scope = f"{request.destination}"
    if request.cover_nearby and draft.hotel_regions and len(draft.hotel_regions) > 1:
        trip_scope += f" + nearby day trips ({', '.join(draft.hotel_regions)})"
    elif request.cover_nearby:
        trip_scope += " + nearby attractions"

    notes = [
        "Prices include estimated taxes and fees where available.",
        "A 10% contingency buffer has been added to the total.",
        "Live provider names and links are sourced from Serper search results.",
    ]
    if currency != "USD":
        notes.append(f"Budget and costs are displayed in {currency} using an exchange rate of {exchange_rate:,.2f} per 1 USD.")

    itinerary = MasterTravelItinerary(
        destination=request.destination,
        origin=origin,
        total_budget=round(total_budget, 2),
        total_budget_usd=request.total_budget_usd,
        actual_calculated_cost=_to_original(actual_cost, exchange_rate),
        actual_calculated_cost_usd=round(actual_cost, 2),
        currency=currency,
        exchange_rate=exchange_rate,
        travelers=travelers,
        days=days,
        transit_summary=f"Planned {len(transit_legs)} transit legs across {len({leg.from_location for leg in transit_legs})} locations.",
        stay_summary=f"Selected {len(stays)} night(s) in {', '.join(dict.fromkeys(draft.hotel_regions))} matching {request.travel_style} style.",
        sightseeing_summary=f"Curated activities across {number_of_days} day(s) focusing on {', '.join(request.interests) or 'general sightseeing'}.",
        trip_scope=trip_scope,
        inclusions=inclusions,
        exclusions=exclusions,
        notes=notes,
    )

    scaled_data = _scale_itinerary_to_budget(itinerary.model_dump(), request.total_budget_usd, exchange_rate)
    return MasterTravelItinerary(**scaled_data)


def _fill_display_currency(data: dict, exchange_rate: float) -> dict:
    """Ensure every *_usd cost field has a matching display-currency field."""
    if not isinstance(data, dict):
        return data

    def ensure(pair_usd: str, pair: str, obj: dict) -> None:
        if pair_usd in obj and pair not in obj:
            obj[pair] = _to_original(float(obj[pair_usd] or 0), exchange_rate)

    ensure("total_budget_usd", "total_budget", data)
    ensure("actual_calculated_cost_usd", "actual_calculated_cost", data)

    for day in data.get("days", []):
        if not isinstance(day, dict):
            continue
        ensure("daily_transit_cost_usd", "daily_transit_cost", day)
        ensure("daily_activity_cost_usd", "daily_activity_cost", day)
        ensure("daily_stay_cost_usd", "daily_stay_cost", day)
        ensure("total_daily_cost_usd", "total_daily_cost", day)
        for leg in day.get("transit_legs", []):
            ensure("estimated_cost_usd", "estimated_cost", leg)
        stay = day.get("stay")
        if stay:
            ensure("estimated_cost_usd", "estimated_cost", stay)
        for activity in day.get("activities", []):
            ensure("estimated_cost_usd", "estimated_cost", activity)

    return data


def _recompute_display_costs(data: dict, exchange_rate: float) -> dict:
    """Recompute all display-currency cost fields from their USD counterparts.

    Preserves the user's original total_budget amount (it is an input, not a
    derived value) so currencies like INR do not drift by a few rupees due to
    USD rounding.
    """
    if not isinstance(data, dict):
        return data

    def recalc(pair_usd: str, pair: str, obj: dict, overwrite: bool = True) -> None:
        if pair_usd in obj and (overwrite or pair not in obj):
            obj[pair] = _to_original(float(obj[pair_usd] or 0), exchange_rate)

    # total_budget is the user's original input; only fill it if missing.
    recalc("total_budget_usd", "total_budget", data, overwrite=False)
    recalc("actual_calculated_cost_usd", "actual_calculated_cost", data)

    for day in data.get("days", []):
        if not isinstance(day, dict):
            continue
        recalc("daily_transit_cost_usd", "daily_transit_cost", day)
        recalc("daily_activity_cost_usd", "daily_activity_cost", day)
        recalc("daily_stay_cost_usd", "daily_stay_cost", day)
        recalc("total_daily_cost_usd", "total_daily_cost", day)
        for leg in day.get("transit_legs", []):
            recalc("estimated_cost_usd", "estimated_cost", leg)
        stay = day.get("stay")
        if stay:
            recalc("estimated_cost_usd", "estimated_cost", stay)
        for activity in day.get("activities", []):
            recalc("estimated_cost_usd", "estimated_cost", activity)

    return data


def _scale_itinerary_to_budget(data: dict, total_budget_usd: float, exchange_rate: float) -> dict:
    """Proportionally scale all itemized costs down when the plan exceeds the budget.

    This is a deterministic safety net: agents receive budget caps, but LLMs can
    still overshoot. Scaling keeps the itinerary structure identical while making
    the final total fit the user's original currency budget.
    """
    if not isinstance(data, dict) or total_budget_usd <= 0:
        return data

    actual_usd = float(data.get("actual_calculated_cost_usd") or 0)
    if actual_usd <= total_budget_usd:
        return data

    factor = total_budget_usd / actual_usd
    currency = data.get("currency", "USD")

    for day in data.get("days", []):
        if not isinstance(day, dict):
            continue
        for leg in day.get("transit_legs", []):
            leg["estimated_cost_usd"] = round(float(leg.get("estimated_cost_usd", 0) or 0) * factor, 2)
        stay = day.get("stay")
        if stay:
            stay["estimated_cost_usd"] = round(float(stay.get("estimated_cost_usd", 0) or 0) * factor, 2)
        for activity in day.get("activities", []):
            activity["estimated_cost_usd"] = round(float(activity.get("estimated_cost_usd", 0) or 0) * factor, 2)

        day["daily_transit_cost_usd"] = round(sum(
            float(leg.get("estimated_cost_usd", 0) or 0) for leg in day.get("transit_legs", [])
        ), 2)
        day["daily_activity_cost_usd"] = round(sum(
            float(activity.get("estimated_cost_usd", 0) or 0) for activity in day.get("activities", [])
        ), 2)
        day["daily_stay_cost_usd"] = round(float(day.get("stay", {}).get("estimated_cost_usd", 0) or 0), 2)
        day["total_daily_cost_usd"] = round(
            day["daily_transit_cost_usd"] + day["daily_activity_cost_usd"] + day["daily_stay_cost_usd"], 2
        )

    total_transit = sum(
        sum(float(leg.get("estimated_cost_usd", 0) or 0) for leg in day.get("transit_legs", []))
        for day in data.get("days", [])
    )
    total_activity = sum(
        sum(float(activity.get("estimated_cost_usd", 0) or 0) for activity in day.get("activities", []))
        for day in data.get("days", [])
    )
    total_stay = sum(
        float(day.get("stay", {}).get("estimated_cost_usd", 0) or 0)
        for day in data.get("days", [])
    )
    subtotal = total_transit + total_activity + total_stay
    contingency = subtotal * 0.10
    data["actual_calculated_cost_usd"] = round(subtotal + contingency, 2)

    notes = data.get("notes") or []
    if not isinstance(notes, list):
        notes = [notes]
    over_by_original = _to_original(actual_usd - total_budget_usd, exchange_rate)
    notes.append(
        f"Costs were scaled by {factor:.0%} to fit your {currency} budget "
        f"(original estimate was {over_by_original:,.2f} over budget)."
    )
    data["notes"] = notes

    return _recompute_display_costs(data, exchange_rate)


def _is_valid_assembler_output(data: dict, request: TravelPlanRequest) -> bool:
    """Sanity-check the assembler's JSON before accepting it."""
    if not isinstance(data, dict):
        return False
    expected_days = (request.end_date - request.start_date).days + 1
    days = data.get("days")
    if not isinstance(days, list) or len(days) != expected_days:
        return False
    actual_usd = data.get("actual_calculated_cost_usd")
    if actual_usd in (None, 0, 0.0):
        return False
    return True


async def _assemble_itinerary_with_crew(
    request: TravelPlanRequest,
    draft: DraftItinerary,
    parsed_raw: str,
    transit_raw: str,
    stay_raw: str,
    sightseeing_raw: str,
    search_context: dict[str, str],
) -> MasterTravelItinerary:
    """Run the Itinerary Assembler crew to refine a deterministic baseline itinerary."""
    # Start from a deterministic, schema-correct baseline.
    baseline = _build_itinerary(
        request,
        draft=draft,
        parsed_raw=parsed_raw,
        transit_raw=transit_raw,
        stay_raw=stay_raw,
        sightseeing_raw=sightseeing_raw,
        search_context=search_context,
    )

    inputs = _build_inputs(request)
    enriched_inputs = {
        **inputs,
        "skeleton": draft.model_dump_json(),
        "search_context": json.dumps(search_context, indent=2),
        "transit_raw": transit_raw,
        "stay_raw": stay_raw,
        "sightseeing_raw": sightseeing_raw,
        "baseline_itinerary": baseline.model_dump_json(),
    }

    try:
        crew = build_assembly_crew()
        result = await crew.kickoff_async(inputs=enriched_inputs)
        raw_output = str(result.tasks_output[0]) if result and hasattr(result, "tasks_output") and result.tasks_output else "{}"
        data = _extract_json(raw_output)
        if _is_valid_assembler_output(data, request):
            exchange_rate = getattr(request, "exchange_rate", 1.0) or 1.0
            data.setdefault("currency", request.currency)
            data.setdefault("exchange_rate", exchange_rate)
            data = _fill_display_currency(data, exchange_rate)
            data = _scale_itinerary_to_budget(data, request.total_budget_usd, exchange_rate)
            return MasterTravelItinerary(**data)
    except Exception:
        pass

    return baseline


_CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "Rs ",
    "EUR": "EUR ",
    "GBP": "GBP ",
    "AED": "AED ",
    "JPY": "JPY ",
    "AUD": "A$",
    "CAD": "C$",
}


def _currency_symbol(currency_code: str) -> str:
    return _CURRENCY_SYMBOLS.get(currency_code, f"{currency_code} ")


def _pdf_text(text: str | None) -> str:
    """Sanitize text so fpdf's built-in Helvetica font can render it."""
    if text is None:
        return ""
    return (
        text.replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("•", "-")
        .replace("…", "...")
        .replace("€", "EUR")
        .replace("£", "GBP")
        .replace("₹", "INR")
        .replace("¥", "JPY")
    )


def _generate_itinerary_pdf(itinerary: MasterTravelItinerary) -> bytes:
    """Generate a PDF from a MasterTravelItinerary and return the bytes."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    symbol = _currency_symbol(itinerary.currency)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, _pdf_text(f"{itinerary.destination} Itinerary"), ln=True)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, _pdf_text(f"From {itinerary.origin or 'N/A'}  |  {itinerary.travelers} traveler(s)"), ln=True)
    pdf.cell(0, 8, _pdf_text(f"{len(itinerary.days)} day(s)  |  Budget: {symbol}{itinerary.total_budget:,.2f} {itinerary.currency}"), ln=True)
    pdf.cell(0, 8, _pdf_text(f"Estimated cost: {symbol}{itinerary.actual_calculated_cost:,.2f} {itinerary.currency}"), ln=True)
    if itinerary.trip_scope:
        pdf.cell(0, 8, _pdf_text(f"Scope: {itinerary.trip_scope}"), ln=True)
    pdf.ln(5)

    if itinerary.inclusions:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Inclusions", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for item in itinerary.inclusions:
            pdf.cell(0, 6, _pdf_text(f"- {item}"), ln=True)
        pdf.ln(3)

    if itinerary.exclusions:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Exclusions", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for item in itinerary.exclusions:
            pdf.cell(0, 6, _pdf_text(f"- {item}"), ln=True)
        pdf.ln(5)

    for day in itinerary.days:
        pdf.set_font("Helvetica", "B", 13)
        title = f"Day {day.day_number} - {day.theme}"
        if day.region:
            title += f" ({day.region})"
        pdf.cell(0, 10, _pdf_text(title), ln=True)

        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, _pdf_text(f"Date: {day.date}  |  Meals: {', '.join(day.meals_included) or 'N/A'}"), ln=True)

        if day.stay:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Stay:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, _pdf_text(f"  {day.stay.hotel_name} - {day.stay.location}"), ln=True)
            pdf.cell(0, 6, _pdf_text(f"  Room: {day.stay.room_type}  |  {symbol}{day.stay.estimated_cost:,.2f}"), ln=True)

        if day.transit_legs:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Transit:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for leg in day.transit_legs:
                pdf.cell(0, 6, _pdf_text(f"  {leg.from_location} -> {leg.to_location} ({leg.mode})  |  {symbol}{leg.estimated_cost:,.2f}"), ln=True)

        if day.activities:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Activities:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for activity in day.activities:
                pdf.cell(0, 6, _pdf_text(f"  {activity.time_slot}: {activity.activity_name} ({activity.location}) - {symbol}{activity.estimated_cost:,.2f}"), ln=True)

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _pdf_text(f"Daily total: {symbol}{day.total_daily_cost:,.2f}"), ln=True)
        pdf.ln(5)

    if itinerary.notes:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Notes", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for note in itinerary.notes:
            pdf.cell(0, 6, _pdf_text(f"- {note}"), ln=True)

    output = BytesIO()
    pdf.output(output)
    return output.getvalue()


@app.get("/plan/{session_id}/pdf")
async def download_itinerary_pdf(session_id: str) -> Response:
    """Download the itinerary for a given session as a PDF."""
    itinerary = itinerary_store.get(session_id)
    if not itinerary:
        return Response(status_code=404, content="Itinerary not found", media_type="text/plain")

    pdf_bytes = _generate_itinerary_pdf(itinerary)
    filename = f"{itinerary.destination.lower().replace(' ', '_')}-itinerary.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.post("/parse-prompt", response_model=PromptParseResponse)
async def parse_prompt(payload: PromptParseRequest) -> PromptParseResponse:
    """Extract structured travel fields from a free-text prompt.

    Returns the extracted values plus a list of required fields that are still
    missing so the frontend can ask only those questions.
    """
    required_fields = [
        "destination",
        "origin",
        "start_date",
        "end_date",
        "travelers",
        "total_budget_usd",
        "interests",
    ]
    optional_fields = ["travel_style", "cover_nearby", "dietary_notes", "mobility_notes", "free_text", "currency", "total_budget", "exchange_rate"]

    inputs = {
        "destination": "",
        "origin": "",
        "start_date": "",
        "end_date": "",
        "travelers": 1,
        "total_budget_usd": 0,
        "interests": "",
        "travel_style": "",
        "cover_nearby": "",
        "dietary_notes": "none",
        "mobility_notes": "none",
        "free_text": payload.prompt,
    }

    try:
        crew = build_parse_crew()
        result = await crew.kickoff_async(inputs=inputs)
        raw_output = str(result.tasks_output[0]) if result and hasattr(result, "tasks_output") and result.tasks_output else "{}"
        parsed = _extract_json(raw_output)
    except Exception:
        parsed = {}

    extracted: dict[str, Any] = {}
    for field in required_fields + optional_fields:
        value = parsed.get(field)
        if value not in (None, "", [], 0):
            extracted[field] = value

    missing = [field for field in required_fields if field not in extracted]

    # Normalize interests to a list when possible.
    if "interests" in extracted and isinstance(extracted["interests"], str):
        extracted["interests"] = [i.strip() for i in extracted["interests"].split(",") if i.strip()]
        if not extracted["interests"]:
            missing.append("interests")
            del extracted["interests"]

    if "interests" in extracted and isinstance(extracted["interests"], list):
        extracted["interests"] = _normalize_interests(extracted["interests"])

    if "dietary_notes" in extracted and isinstance(extracted["dietary_notes"], str):
        extracted["dietary_notes"] = _normalize_dietary(extracted["dietary_notes"])

    # Normalize dates to YYYY-MM-DD.
    start_text = extracted.get("start_date")
    end_text = extracted.get("end_date")

    # Try parsing explicit ranges like "10th oct to 20th oct 2026".
    range_match = None
    if isinstance(start_text, str):
        range_match = _DATE_RANGE_RE.search(start_text)
    if not range_match and isinstance(end_text, str):
        range_match = _DATE_RANGE_RE.search(end_text)

    if range_match:
        start_day, start_month, start_year, end_day, end_month, end_year = range_match.groups()
        year = int(start_year or end_year or date.today().year)
        start_iso = _build_iso_date(start_day, start_month, year)
        end_iso = _build_iso_date(end_day, end_month, year)
        if start_iso and end_iso:
            extracted["start_date"] = start_iso
            extracted["end_date"] = end_iso
        else:
            for date_field in ("start_date", "end_date"):
                if date_field in extracted and date_field not in missing:
                    missing.append(date_field)
                    del extracted[date_field]
    else:
        # Try parsing a shared relative date range (e.g., "first week of September 2026").
        shared_range = _parse_relative_date_range(str(start_text)) if start_text else None
        if not shared_range and end_text:
            shared_range = _parse_relative_date_range(str(end_text))

        if shared_range:
            extracted["start_date"] = shared_range[0]
            extracted["end_date"] = shared_range[1]
        else:
            for date_field in ("start_date", "end_date"):
                if date_field in extracted:
                    normalized = _normalize_date(extracted[date_field])
                    if normalized:
                        extracted[date_field] = normalized
                    else:
                        del extracted[date_field]
                        if date_field not in missing:
                            missing.append(date_field)

    # If the user gave a start date plus a duration like "5 day trip", fill in the end date.
    if "start_date" in extracted and "end_date" not in extracted:
        duration_match = _TRIP_DURATION_RE.search(payload.prompt)
        if duration_match:
            try:
                start_dt = date.fromisoformat(extracted["start_date"])
                days = int(duration_match.group(1))
                if days > 0:
                    extracted["end_date"] = (start_dt + timedelta(days=days - 1)).isoformat()
                    if "end_date" in missing:
                        missing.remove("end_date")
            except (ValueError, TypeError):
                pass

    # Fallback: parse the raw prompt for relative date phrases when no dates were extracted.
    if "start_date" not in extracted and "end_date" not in extracted:
        fallback_range = _parse_relative_date_range(payload.prompt)
        if fallback_range:
            extracted["start_date"] = fallback_range[0]
            extracted["end_date"] = fallback_range[1]
            if "start_date" in missing:
                missing.remove("start_date")
            if "end_date" in missing:
                missing.remove("end_date")

    # Default travel style to balanced so users don't get asked when they only mention a budget.
    if "travel_style" not in extracted:
        extracted["travel_style"] = "balanced"
    if "travel_style" in missing:
        missing.remove("travel_style")

    # If origin was misread as a relative date word, is a placeholder, or equals the destination, clear it.
    origin_value = extracted.get("origin", "").lower().strip()
    destination_value = extracted.get("destination", "").lower().strip()
    placeholder_origins = {
        "today", "tomorrow", "yesterday", "next week", "this week", "coming week",
        "unknown", "not sure", "unsure", "n/a", "none",
        "current location", "my location", "here",
    }
    if origin_value in placeholder_origins or origin_value == destination_value:
        extracted.pop("origin", None)
        origin_value = ""

    # Fallback: use rule-based extraction for origin/destination when the LLM missed them.
    if not extracted.get("origin") or not extracted.get("destination"):
        fallback_origin, fallback_destination = _extract_origin_destination(payload.prompt)
        if fallback_origin and not extracted.get("origin"):
            extracted["origin"] = fallback_origin
            origin_value = fallback_origin.lower().strip()
        if fallback_destination and not extracted.get("destination"):
            extracted["destination"] = fallback_destination
            destination_value = fallback_destination.lower().strip()

    # Fallback: extract interests from the raw prompt if the LLM missed them.
    if "interests" not in extracted or not extracted["interests"]:
        fallback_interests = _extract_interests_from_prompt(payload.prompt)
        if fallback_interests:
            extracted["interests"] = fallback_interests

    # Convert budget to USD while preserving the original currency.
    if "total_budget_usd" in extracted:
        raw_budget_value = extracted["total_budget_usd"]
        normalized = _normalize_budget(
            raw_budget_value,
            payload.prompt,
            origin_value,
            destination_value,
        )
        if normalized is not None:
            usd_amount, currency_code, exchange_rate = normalized
            extracted["total_budget"] = round(float(raw_budget_value), 2) if isinstance(raw_budget_value, (int, float)) else round(usd_amount * exchange_rate, 2)
            extracted["total_budget_usd"] = usd_amount
            extracted["currency"] = currency_code
            extracted["exchange_rate"] = exchange_rate
        else:
            del extracted["total_budget_usd"]
            if "total_budget_usd" not in missing:
                missing.append("total_budget_usd")

    # Decide whether to cover nearby places, and build the list if relevant.
    raw_cover = extracted.get("cover_nearby")
    cover_nearby = _should_cover_nearby(payload.prompt, raw_cover)
    extracted["cover_nearby"] = cover_nearby

    number_of_days = 0
    if "start_date" in extracted and "end_date" in extracted:
        try:
            start_dt = date.fromisoformat(extracted["start_date"])
            end_dt = date.fromisoformat(extracted["end_date"])
            number_of_days = (end_dt - start_dt).days + 1
        except (ValueError, TypeError):
            pass

    nearby_places: list[str] = []
    if cover_nearby and number_of_days >= 4:
        nearby_places = await _fetch_nearby_places_async(destination_value)
    extracted["nearby_places"] = nearby_places

    # Recompute missing from the final extracted set so any field we filled in post-processing is no longer missing.
    missing = [field for field in required_fields if field not in extracted]

    return PromptParseResponse(extracted=extracted, missing=missing, parsed=parsed)


async def _build_draft_itinerary(request: TravelPlanRequest, inputs: dict[str, Any]) -> DraftItinerary:
    """Run the itinerary architect crew and return a validated DraftItinerary."""
    crew = build_skeleton_crew()
    result = await crew.kickoff_async(inputs=inputs)
    raw_output = str(result.tasks_output[0]) if result and hasattr(result, "tasks_output") and result.tasks_output else "{}"
    try:
        data = _extract_json(raw_output)
    except Exception:
        data = {}

    raw_days = [item for item in data.get("days", []) if isinstance(item, dict)]

    # Correct architect mistakes: the first night's base (and its region) should
    # not be the origin; the origin should not appear as a hotel region.
    origin_lower = request.origin.strip().lower()
    destination_lower = request.destination.strip().lower()
    for item in raw_days:
        base = (item.get("base_location") or "").strip().lower()
        region = (item.get("region") or "").strip().lower()
        if base == origin_lower and base != destination_lower:
            item["base_location"] = request.destination
        if region == origin_lower and region != destination_lower:
            item["region"] = request.destination

    days: list[DraftItineraryDay] = []
    for item in raw_days:
        try:
            days.append(DraftItineraryDay(**item))
        except Exception:
            continue

    transit_legs: list[TransitLeg] = []
    for leg in data.get("transit_legs", []):
        if isinstance(leg, dict):
            # The architect prompt asks for estimated_cost_usd only; fill the
            # matching display field so Pydantic validation passes.
            if "estimated_cost_usd" in leg and "estimated_cost" not in leg:
                leg["estimated_cost"] = float(leg.get("estimated_cost_usd") or 0)
            try:
                transit_legs.append(TransitLeg(**leg))
            except Exception:
                continue

    hotel_regions = list(
        dict.fromkeys(
            d.base_location for d in days
            if d.base_location.strip().lower() != origin_lower
        )
    )

    # Fallback: if the architect produced nothing, build a single-base skeleton.
    if not days:
        delta = (request.end_date - request.start_date).days
        for i in range(delta + 1):
            current_date = request.start_date + timedelta(days=i)
            days.append(
                DraftItineraryDay(
                    day_number=i + 1,
                    date=current_date.isoformat(),
                    region=request.destination,
                    base_location=request.destination,
                    theme=f"Day {i + 1} in {request.destination}",
                    activity_focus=request.interests,
                )
            )
        hotel_regions = [request.destination]

    return DraftItinerary(days=days, transit_legs=transit_legs, hotel_regions=hotel_regions)


async def _run_search_tools(request: TravelPlanRequest, draft: DraftItinerary) -> dict[str, str]:
    """Call Serper-powered tools for each skeleton segment and return context strings."""
    start = request.start_date
    end = request.end_date
    first_base = draft.days[0].base_location if draft.days else request.destination
    last_base = draft.days[-1].base_location if draft.days else request.destination

    # Group consecutive nights by base location.
    hotel_groups: list[tuple[str, date, date]] = []
    current_base: str | None = None
    current_check_in: date | None = None
    current_check_out: date | None = None
    for day in draft.days:
        base = day.base_location
        day_date = date.fromisoformat(day.date)
        if base != current_base:
            if current_base is not None and current_check_in is not None and current_check_out is not None:
                hotel_groups.append((current_base, current_check_in, current_check_out + timedelta(days=1)))
            current_base = base
            current_check_in = day_date
            current_check_out = day_date
        else:
            current_check_out = day_date
    if current_base is not None and current_check_in is not None and current_check_out is not None:
        hotel_groups.append((current_base, current_check_in, current_check_out + timedelta(days=1)))

    search_tasks = []
    labels: list[str] = []

    # Outbound and return flights only if origin differs from destination area.
    if request.origin.strip().lower() not in {request.destination.strip().lower(), first_base.strip().lower()}:
        search_tasks.append(flight_search_tool._arun(request.origin, first_base, start, None, request.travelers, request.travel_style))
        labels.append("outbound_flight")
        search_tasks.append(flight_search_tool._arun(last_base, request.origin, end, None, request.travelers, request.travel_style))
        labels.append("return_flight")

    # Hotels per base region.
    for base, check_in, check_out in hotel_groups:
        search_tasks.append(hotel_search_tool._arun(base, check_in, check_out, request.travelers, request.travel_style))
        labels.append(f"hotel_{base}")

    # Attractions per distinct region/day theme.
    seen_regions: set[str] = set()
    for day in draft.days:
        key = f"{day.region}_{day.theme}"
        if key in seen_regions:
            continue
        seen_regions.add(key)
        focus = day.activity_focus or request.interests
        search_tasks.append(attraction_search_tool._arun(day.region, focus, request.travel_style))
        labels.append(f"attractions_{day.region}_{day.theme}")

    results = await asyncio.gather(*search_tasks, return_exceptions=True)
    context: dict[str, str] = {}
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            context[label] = f"Search failed for {label}: {result}"
        else:
            context[label] = str(result)
    return context


@app.post("/plan", response_model=TravelPlanResponse)
async def create_plan(plan_request: TravelPlanRequest) -> TravelPlanResponse:
    session_id = str(uuid.uuid4())

    nearby_places = await _fetch_nearby_places_async(plan_request.destination) if plan_request.cover_nearby else []
    inputs = _build_inputs(plan_request, nearby_places=nearby_places)
    parsed_raw = _build_parsed_raw(plan_request)

    try:
        # Phase 1: Itinerary Architect builds the route skeleton.
        draft = await _build_draft_itinerary(plan_request, inputs)

        # Phase 2: Parallel Serper searches per skeleton segment.
        search_context = await _run_search_tools(plan_request, draft)

        # Phase 3: Enrich inputs with skeleton + search context for specialists.
        enriched_inputs = {
            **inputs,
            "skeleton": draft.model_dump_json(),
            "search_context": json.dumps(search_context, indent=2),
        }

        # Phase 4: Run specialist crews in parallel.
        travel_crew = build_travel_crew()
        stay_crew = build_stay_crew()
        sightseeing_crew = build_sightseeing_crew()

        transit_result, stay_result, sightseeing_result = await asyncio.gather(
            travel_crew.kickoff_async(inputs=enriched_inputs),
            stay_crew.kickoff_async(inputs=enriched_inputs),
            sightseeing_crew.kickoff_async(inputs=enriched_inputs),
        )

        outputs = [
            str(transit_result.tasks_output[0]) if transit_result and hasattr(transit_result, "tasks_output") and transit_result.tasks_output else "[]",
            str(stay_result.tasks_output[0]) if stay_result and hasattr(stay_result, "tasks_output") and stay_result.tasks_output else "[]",
            str(sightseeing_result.tasks_output[0]) if sightseeing_result and hasattr(sightseeing_result, "tasks_output") and sightseeing_result.tasks_output else "[]",
        ]

        # Phase 5: Itinerary Assembler refines the deterministic baseline into the final itinerary.
        itinerary = await _assemble_itinerary_with_crew(
            plan_request,
            draft=draft,
            parsed_raw=parsed_raw,
            transit_raw=outputs[0],
            stay_raw=outputs[1],
            sightseeing_raw=outputs[2],
            search_context=search_context,
        )

        itinerary_store[session_id] = itinerary

        return TravelPlanResponse(
            session_id=session_id,
            status="completed",
            itinerary=itinerary,
        )

    except Exception as exc:
        return TravelPlanResponse(
            session_id=session_id,
            status="failed",
            error=str(exc),
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
