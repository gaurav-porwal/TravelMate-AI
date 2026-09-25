"""
Phase 2: CrewAI Agents - Starter Template

Files you implement: this file (agent + tool definitions) and
trip_orchestrator.py (CrewAITripOrchestrator, which imports the names
below). Keep the public function/class names and signatures as-is -
trip_orchestrator.py and api/app.py depend on them by name.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

try:
    from crewai import Agent, LLM
except Exception:
    Agent = None
    LLM = None

from api.datamodels import (
    FlightSuggestion,
    HotelSuggestion,
    OptimizationResult,
    TravelPlan,
    TripRequirements,
)
from toolkits.current_datetime import DateTimeTool
from toolkits.weather_tool import WeatherTool
from toolkits.web_search_service import WebSearchService

load_dotenv()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
# These wrap the provided toolkits/ services so CrewAI agents (and your own
# orchestration code) can call them. web_search_service (Tavily) is the
# universal fallback whenever weather/hotel/flight search comes back empty
# or errors out - see the lab manual's Fallback Strategy section.

class SearchWebTool:
    """
    General web search - also the fallback tool for validating destinations
    and for hotel/flight/activity lookups when other sources fail.
    Args:
        query (str): The search query string.
        max_results (int): Max number of results to return.
    Returns:
        Dict[str, Any]: {"query": ..., "results": [{"title", "url", "content"}, ...]}
    TODO: Call WebSearchService().search(...) and return its result, with a
    safe fallback payload if the call raises or errors.
    """
    def _run(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        try:
            return WebSearchService().search(query, max_results)
        except Exception as e:
            return {
                "query": query,
                "results": [],
                "error": str(e)
            }


class GetWeatherTool:
    """
    Weather forecast for a destination over a date range.
    Args:
        city (str): City name.
        start_date (str): Start date (YYYY-MM-DD).
        end_date (str): End date (YYYY-MM-DD).
    Returns:
        Dict[str, Any]: Weather forecast payload, or a web-search fallback
        result if the weather API is unavailable.
    TODO: Call WeatherTool().get_weather_range(...); fall back to
    SearchWebTool on failure per the lab manual's fallback strategy.
    """
    def _run(self, city: str, start_date: str, end_date: str) -> Dict[str, Any]:
        try:
            result = WeatherTool().get_weather_range(
                city,
                start_date,
                end_date
            )

            if result.get("error"):
                return SearchWebTool()._run(
                    f"weather forecast {city} {start_date} {end_date}"
                )

            return result

        except Exception:
            return SearchWebTool()._run(
                f"weather forecast {city} {start_date} {end_date}"
            )


class SearchHotelsTool:
    """
    Hotel search for a destination and date range.
    Args:
        city (str): City name.
        checkin (str): Check-in date (YYYY-MM-DD).
        checkout (str): Check-out date (YYYY-MM-DD).
        adults (int): Number of adults.
    Returns:
        Dict[str, Any]: Same shape as SearchWebTool's result.
    TODO: Implement via a web search query (no dedicated hotels API is
    provided - Tavily general search is the intended source).
    """
    def _run(
    self,
    city: str,
    checkin: str,
    checkout: str,
    adults: int = 1
) -> Dict[str, Any]:

        query = (
            f"best hotels in {city} "
            f"from {checkin} to {checkout} "
            f"for {adults} adults"
        )

        return SearchWebTool()._run(query)


class SearchFlightsTool:
    """
    Flight search between two cities.
    Args:
        origin (str): Origin city.
        destination (str): Destination city.
        departure_date (str): Departure date (YYYY-MM-DD).
        return_date (str, optional): Return date (YYYY-MM-DD).
    Returns:
        Dict[str, Any]: Same shape as SearchWebTool's result.
    TODO: Implement via a web search query (no dedicated flights API is
    provided - Tavily general search is the intended source).
    """
    def _run(
    self,
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None
) -> Dict[str, Any]:

        query = (
            f"flights from {origin} to {destination} "
            f"on {departure_date}"
        )

        if return_date:
            query += f" return {return_date}"

        return SearchWebTool()._run(query)


class GetCurrentDateTool:
    """
    Today's date, for validating that trip dates are in the future.
    Returns:
        str: Current date in YYYY-MM-DD format.
    TODO: Call DateTimeTool().get_today_date() and return the date string.
    """
    def _run(self) -> str:
        result = DateTimeTool().get_today_date()
        return result.get("date")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
# Each factory returns a CrewAI Agent with a role/goal/backstory and the
# tools listed for it in the lab manual. Keep an `llm=None` fallback path
# (e.g. returning a plain dict) for environments where crewai isn't
# installed, so importing this module never crashes.

def info_collector(llm=None):

    if Agent is None:
        return {
            "name": "InfoCollector"
        }

    return Agent(
        role="Travel Requirements Specialist",
        goal="Extract and validate travel requirements",
        backstory=(
            "Experienced travel consultant who gathers "
            "travel requirements and validates information"
        ),
        verbose=True,
    )


def planner(llm=None):

    if Agent is None:
        return {
            "name": "Planner"
        }

    return Agent(
        role="Travel Itinerary Specialist",
        goal="Create detailed itineraries",
        backstory=(
            "Travel planning expert specialized in hotels,"
            " flights and local activities."
        ),
        verbose=True,
    )


def optimizer(llm=None):

    if Agent is None:
        return {
            "name": "Optimizer"
        }

    return Agent(
        role="Travel Cost Optimizer",
        goal="Optimize plans and reduce costs",
        backstory=(
            "Travel finance expert identifying savings "
            "and practical improvements."
        ),
        verbose=True,
    )


# ---------------------------------------------------------------------------
# Core workflow functions
# ---------------------------------------------------------------------------
# trip_orchestrator.py calls these three functions directly to drive the
# sequential InfoCollector -> Planner -> Optimizer workflow and persist
# results. Keep these exact names/signatures - the orchestrator, and
# Phase 4 (which reuses Phase 2's plan/optimize logic), import them by name.

def collect_trip_requirements(
    user_input: str,
    conversation_history=None,
    prior_context=None,
):

    import re
    from datetime import datetime

    origin = None
    destination = None
    trip_startdate = None
    trip_enddate = None
    no_of_adults = 1
    budget = None

    # route

    route_match = re.search(
        r"from\s+(.+?)\s+to\s+(.+?)\s+from",
        user_input,
        re.IGNORECASE
    )

    if route_match:
        origin = route_match.group(1).strip()
        destination = route_match.group(2).strip()

    # dates

    date_match = re.findall(
        r"\d{4}-\d{2}-\d{2}",
        user_input
    )

    if len(date_match) >= 2:
        trip_startdate = datetime.strptime(
            date_match[0],
            "%Y-%m-%d"
        ).date()

        trip_enddate = datetime.strptime(
            date_match[1],
            "%Y-%m-%d"
        ).date()

    # adults

    adults_match = re.search(
        r"(\d+)\s+adult",
        user_input,
        re.IGNORECASE
    )

    if adults_match:
        no_of_adults = int(
            adults_match.group(1)
        )

    # budget

    budget_match = re.search(
        r"budget\s+(?:of\s+)?(\d+)",
        user_input,
        re.IGNORECASE
    )

    if budget_match:
        budget = float(
            budget_match.group(1)
        )

    requirements = TripRequirements(
        origin=origin,
        destination=destination,
        trip_startdate=trip_startdate,
        trip_enddate=trip_enddate,
        no_of_adults=no_of_adults,
        budget=budget,
        currency="INR",
        purpose="leisure",
    )

    return requirements, user_input


def create_travel_plan(
    requirements: TripRequirements,
    user_feedback: str = ""
) -> TravelPlan:

    hotels = [
        HotelSuggestion(
            name=f"{requirements.destination} Central Hotel",
            location=requirements.destination,
            price_per_night=150
        )
    ]

    flights = [
        FlightSuggestion(
            airline="TravelMate Airlines",
            departure_time="09:00",
            arrival_time="11:00",
            price=250
        )
    ]

    itinerary = f"""
Day 1:
Arrival at {requirements.destination}

Day 2:
City sightseeing

Day 3:
Local experiences and leisure

Day 4:
Return journey
"""

    return TravelPlan(
        itinerary=itinerary,
        hotels=hotels,
        flights=flights,
        daily_budget=(
            requirements.budget / 4
            if requirements.budget
            else 0
        ),
        total_estimated_cost=500
    )


def optimize_travel_plan(
    requirements: TripRequirements,
    plan: TravelPlan,
    user_feedback: str = ""
) -> OptimizationResult:

    recommendations = []

    if requirements.budget and plan.total_estimated_cost:

        if plan.total_estimated_cost > requirements.budget:
            recommendations.append(
                "Consider budget hotel alternatives"
            )
        else:
            recommendations.append(
                "Trip is within budget"
            )

    return OptimizationResult(
        recommendations=recommendations,
        cost_savings=100,
        value_adds=[
            "Early booking discounts",
            "Flexible schedules"
        ],
        final_plan="Optimized successfully",
        approval_required=True
    )


# ---------------------------------------------------------------------------
# Summaries (used for chat-history logging by the orchestrator)
# ---------------------------------------------------------------------------

def summarize_requirements(
    requirements: TripRequirements
) -> str:

    if requirements.mode == "missing":
        return requirements.get_missing_info()

    return (
        f"{requirements.origin} to "
        f"{requirements.destination}"
    )

def summarize_plan(plan: TravelPlan) -> str:

    return (
        f"{len(plan.hotels)} hotels, "
        f"{len(plan.flights)} flights"
    )

def summarize_optimization(
    opt: OptimizationResult
) -> str:

    return (
        f"{len(opt.recommendations)} recommendations"
    )

__all__ = [
    "SearchWebTool",
    "GetWeatherTool",
    "SearchHotelsTool",
    "SearchFlightsTool",
    "GetCurrentDateTool",
    "info_collector",
    "planner",
    "optimizer",
    "collect_trip_requirements",
    "create_travel_plan",
    "optimize_travel_plan",
    "summarize_requirements",
    "summarize_plan",
    "summarize_optimization",
]
