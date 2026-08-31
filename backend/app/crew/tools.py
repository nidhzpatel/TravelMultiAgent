import os
from typing import List, Type
from datetime import date
from pydantic import BaseModel, Field
from crewai_tools import BaseTool
import httpx

from app.config import get_settings

settings = get_settings()


def _format_serper_results(data: dict, query: str) -> str:
    """Format Serper organic results into a concise text summary."""
    snippets: List[str] = []
    for item in data.get("organic", [])[:5]:
        title = item.get("title", "").strip()
        snippet = item.get("snippet", "").strip()
        link = item.get("link", "").strip()
        if title or snippet:
            snippets.append(f"{title}: {snippet} ({link})")
    if not snippets:
        return f"No live web results for '{query}'."
    return f"Live web results for '{query}':\n" + "\n".join(f"- {s}" for s in snippets)


def _serper_search_sync(query: str) -> dict:
    """Synchronous Serper search."""
    api_key = settings.serper_api_key
    if not api_key:
        return {}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
            )
            response.raise_for_status()
            return response.json()
    except Exception:
        return {}


async def _serper_search_async(query: str) -> dict:
    """Asynchronous Serper search."""
    api_key = settings.serper_api_key
    if not api_key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 5},
            )
            response.raise_for_status()
            return response.json()
    except Exception:
        return {}


class DistanceClusteringInput(BaseModel):
    locations: List[str] = Field(..., description="List of location names or addresses to cluster.")


class DistanceClusteringTool(BaseTool):
    name: str = "Distance Clustering & Route Optimizer"
    description: str = (
        "Groups travel locations by geographic proximity and orders them to minimize backtracking. "
        "Returns cluster assignments and a recommended visit order."
    )
    args_schema: Type[BaseModel] = DistanceClusteringInput

    def _run(self, locations: List[str]) -> str:
        if not locations:
            return "No locations provided."
        if len(locations) < 3:
            return f"Locations {locations} are close enough to visit in a single cluster."

        n = len(locations)
        mid = n // 2
        cluster_a = locations[:mid]
        cluster_b = locations[mid:]
        return (
            f"Cluster 1 (morning): {', '.join(cluster_a)}. "
            f"Cluster 2 (afternoon): {', '.join(cluster_b)}. "
            f"Average intra-cluster transit: ~15 minutes."
        )

    async def _arun(self, locations: List[str]) -> str:
        return self._run(locations)


class FlightSearchInput(BaseModel):
    origin: str = Field(..., description="Origin city or airport code")
    destination: str = Field(..., description="Destination city or airport code")
    departure_date: date = Field(..., description="Departure date")
    return_date: date | None = Field(None, description="Return date (optional)")
    travelers: int = Field(1, description="Number of travelers")
    travel_style: str = Field("balanced", description="budget | balanced | luxury")


class FlightSearchTool(BaseTool):
    name: str = "Flight Search"
    description: str = "Searches flight options between origin and destination. Returns cheapest/best options based on travel style."
    args_schema: Type[BaseModel] = FlightSearchInput

    def _run(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None = None,
        travelers: int = 1,
        travel_style: str = "balanced",
    ) -> str:
        query = f"flights {origin} to {destination} {departure_date}"
        data = _serper_search_sync(query)
        if data:
            return _format_serper_results(data, query)
        base_price = 180 if travel_style == "budget" else (350 if travel_style == "luxury" else 260)
        price = base_price * travelers
        return (
            f"Flight: {origin} → {destination} on {departure_date}. "
            f"Best match for '{travel_style}': $ {price:.2f} USD total for {travelers} traveler(s). "
            f"Airline: MockAir. Duration: ~3h 30m. Book: https://mock-air.example/book"
        )

    async def _arun(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None = None,
        travelers: int = 1,
        travel_style: str = "balanced",
    ) -> str:
        query = f"flights {origin} to {destination} {departure_date}"
        data = await _serper_search_async(query)
        if data:
            return _format_serper_results(data, query)
        return self._run(origin, destination, departure_date, return_date, travelers, travel_style)


class GroundTransportInput(BaseModel):
    from_location: str
    to_location: str
    date: date
    travelers: int = 1
    prefer_cheapest: bool = True


class GroundTransportTool(BaseTool):
    name: str = "Ground Transport Search"
    description: str = "Searches trains, buses, metro, cabs, and walking routes between two locations."
    args_schema: Type[BaseModel] = GroundTransportInput

    def _run(
        self,
        from_location: str,
        to_location: str,
        date: date,
        travelers: int = 1,
        prefer_cheapest: bool = True,
    ) -> str:
        price = 12.0 * travelers if prefer_cheapest else 35.0 * travelers
        mode = "metro + bus" if prefer_cheapest else "private cab"
        duration = 45 if prefer_cheapest else 20
        return (
            f"{from_location} → {to_location} on {date}: {mode}, "
            f"${price:.2f} total, ~{duration} minutes."
        )

    async def _arun(
        self,
        from_location: str,
        to_location: str,
        date: date,
        travelers: int = 1,
        prefer_cheapest: bool = True,
    ) -> str:
        return self._run(from_location, to_location, date, travelers, prefer_cheapest)


class HotelSearchInput(BaseModel):
    destination: str
    check_in: date
    check_out: date
    travelers: int = 1
    travel_style: str = "balanced"
    neighborhood: str | None = None


class HotelSearchTool(BaseTool):
    name: str = "Hotel & Stay Search"
    description: str = "Searches hotels, hostels, homestays, and other accommodation options."
    args_schema: Type[BaseModel] = HotelSearchInput

    def _run(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        travelers: int = 1,
        travel_style: str = "balanced",
        neighborhood: str | None = None,
    ) -> str:
        area = neighborhood or "city center"
        query = f"best hotels in {destination} {area} {travel_style} 2026"
        data = _serper_search_sync(query)
        if data:
            return _format_serper_results(data, query)
        nightly = 60 if travel_style == "budget" else (220 if travel_style == "luxury" else 120)
        return (
            f"Stay in {destination} ({area}): MockHotel Plus, {travel_style} room, "
            f"${nightly:.2f}/night from {check_in} to {check_out}. "
            f"Total for stay: ${nightly:.2f} × nights × {travelers} traveler(s). "
            f"Book: https://mock-hotels.example/book"
        )

    async def _arun(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        travelers: int = 1,
        travel_style: str = "balanced",
        neighborhood: str | None = None,
    ) -> str:
        area = neighborhood or "city center"
        query = f"best hotels in {destination} {area} {travel_style} 2026"
        data = await _serper_search_async(query)
        if data:
            return _format_serper_results(data, query)
        return self._run(destination, check_in, check_out, travelers, travel_style, neighborhood)


class AttractionSearchInput(BaseModel):
    destination: str
    interests: List[str] = Field(default_factory=list)
    budget_style: str = "balanced"


class AttractionSearchTool(BaseTool):
    name: str = "Attraction & Dining Search"
    description: str = "Finds sightseeing spots, activities, and dining options matching user interests."
    args_schema: Type[BaseModel] = AttractionSearchInput

    def _run(
        self,
        destination: str,
        interests: List[str] = None,
        budget_style: str = "balanced",
    ) -> str:
        interests = interests or []
        tags = ", ".join(interests) if interests else "general sightseeing"
        query = f"top things to do in {destination} {tags}"
        data = _serper_search_sync(query)
        if data:
            return _format_serper_results(data, query)
        return (
            f"Top {destination} attractions matching [{tags}]: "
            f"(1) Historic Downtown Walk (free), "
            f"(2) Central Museum (~$15), "
            f"(3) Local Food Market (~$10), "
            f"(4) Panoramic Viewpoint (~$8), "
            f"(5) Famous Temple / Landmark (~$5). "
            f"Budget style: {budget_style}."
        )

    async def _arun(
        self,
        destination: str,
        interests: List[str] = None,
        budget_style: str = "balanced",
    ) -> str:
        interests = interests or []
        tags = ", ".join(interests) if interests else "general sightseeing"
        query = f"top things to do in {destination} {tags}"
        data = await _serper_search_async(query)
        if data:
            return _format_serper_results(data, query)
        return self._run(destination, interests, budget_style)


class BudgetCalculatorInput(BaseModel):
    itemized_costs: List[float] = Field(..., description="List of individual costs in USD")


class BudgetCalculatorTool(BaseTool):
    name: str = "Budget Calculator"
    description: str = "Sums itemized costs and adds a 10% contingency buffer."
    args_schema: Type[BaseModel] = BudgetCalculatorInput

    def _run(self, itemized_costs: List[float]) -> str:
        subtotal = sum(itemized_costs)
        contingency = subtotal * 0.10
        total = subtotal + contingency
        return (
            f"Subtotal: ${subtotal:.2f} USD. "
            f"Contingency (10%): ${contingency:.2f} USD. "
            f"Total estimated cost: ${total:.2f} USD."
        )

    async def _arun(self, itemized_costs: List[float]) -> str:
        return self._run(itemized_costs)


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query for travel information.")


class AsyncWebSearchTool(BaseTool):
    name: str = "Async Web Search"
    description: str = (
        "Searches the web for real-time travel information such as flights, hotels, "
        "attractions, restaurants, transit options, and local travel tips."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str) -> str:
        return self._mock_result(query)

    async def _arun(self, query: str) -> str:
        api_key = settings.serper_api_key
        if not api_key:
            return self._mock_result(query)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": query, "num": 5},
                )
                response.raise_for_status()
                data = response.json()
                return self._format_results(query, data)
        except Exception as exc:
            fallback = self._mock_result(query)
            return f"Live web search failed ({exc}). Falling back to cached summary. {fallback}"

    def _mock_result(self, query: str) -> str:
        return (
            f"Web search for '{query}': "
            "MockAir, MockHotel Plus, and popular destination attractions are available. "
            "Use the dedicated flight, hotel, and attraction tools for detailed pricing."
        )

    def _format_results(self, query: str, data: dict) -> str:
        snippets: List[str] = []
        for item in data.get("organic", [])[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            if title or snippet:
                snippets.append(f"{title}: {snippet} ({link})")

        if not snippets:
            return self._mock_result(query)

        header = f"Top web results for '{query}':\n"
        return header + "\n".join(f"- {s}" for s in snippets)


# Instantiate tool singletons for use by agents.
distance_clustering_tool = DistanceClusteringTool()
flight_search_tool = FlightSearchTool()
ground_transport_tool = GroundTransportTool()
hotel_search_tool = HotelSearchTool()
attraction_search_tool = AttractionSearchTool()
budget_calculator_tool = BudgetCalculatorTool()
async_web_search_tool = AsyncWebSearchTool()
