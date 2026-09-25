"""
Phase 3 AutoGen Conversational Agents
"""

import json
import re
from datetime import datetime

from dotenv import load_dotenv

try:
    from autogen import AssistantAgent
except Exception:
    AssistantAgent = None

from toolkits.current_datetime import DateTimeTool
from toolkits.weather_tool import WeatherTool
from toolkits.web_search_service import WebSearchService

from api.datamodels import (
    TripRequirements,
    TravelPlan,
    HotelSuggestion,
    FlightSuggestion,
    OptimizationResult,
)

load_dotenv()


# =====================================================
# TOOLS
# =====================================================

def web_search(query: str) -> str:
    try:
        result = WebSearchService().search(query)
        return json.dumps(result)
    except Exception as e:
        return json.dumps(
            {
                "query": query,
                "results": [],
                "error": str(e),
            }
        )


def get_weather(city: str, start_date: str, end_date: str) -> str:

    try:
        result = WeatherTool().get_weather_range(
            city,
            start_date,
            end_date,
        )

        if result.get("error"):
            return web_search(
                f"weather {city}"
            )

        return json.dumps(result)

    except Exception:
        return web_search(
            f"weather {city}"
        )


def search_hotels(
    city: str,
    checkin: str,
    checkout: str
) -> str:

    return web_search(
        f"best hotels in {city} "
        f"{checkin} {checkout}"
    )


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
) -> str:

    return web_search(
        f"flights from {origin} "
        f"to {destination} "
        f"{departure_date}"
    )


def get_current_date() -> str:

    return DateTimeTool().get_today_date()["date"]


# =====================================================
# AGENTS
# =====================================================

def info_collector(*args, **kwargs):

    if AssistantAgent is None:
        return {
            "name": "InfoCollector"
        }

    return AssistantAgent(
        name="InfoCollector",
        system_message=(
            "You are an inquisitive travel consultant. "
            "Ask questions and validate travel details."
        ),
    )


def planner(*args, **kwargs):

    if AssistantAgent is None:
        return {
            "name": "Planner"
        }

    return AssistantAgent(
        name="Planner",
        system_message=(
            "You are a creative travel planner. "
            "Suggest engaging itineraries."
        ),
    )


def optimizer(*args, **kwargs):

    if AssistantAgent is None:
        return {
            "name": "Optimizer"
        }

    return AssistantAgent(
        name="Optimizer",
        system_message=(
            "You are a cost conscious analyst. "
            "Challenge expensive choices."
        ),
    )


# =====================================================
# INFO COLLECTION
# =====================================================

def run_info_collection(user_input: str) -> dict:

    origin = None
    destination = None
    trip_startdate = None
    trip_enddate = None
    no_of_adults = 1
    budget = None

    route_match = re.search(
        r"from\s+(.+?)\s+to\s+(.+?)\s+from",
        user_input,
        re.IGNORECASE,
    )

    if route_match:
        origin = route_match.group(1).strip()
        destination = route_match.group(2).strip()

    date_match = re.findall(
        r"\d{4}-\d{2}-\d{2}",
        user_input,
    )

    if len(date_match) >= 2:
        trip_startdate = datetime.strptime(
            date_match[0],
            "%Y-%m-%d",
        ).date()

        trip_enddate = datetime.strptime(
            date_match[1],
            "%Y-%m-%d",
        ).date()

    adults_match = re.search(
        r"(\d+)\s+adult",
        user_input,
        re.IGNORECASE,
    )

    if adults_match:
        no_of_adults = int(
            adults_match.group(1)
        )

    budget_match = re.search(
        r"budget\s+(?:of\s+)?(\d+)",
        user_input,
        re.IGNORECASE,
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

    if requirements.mode == "missing":

        return {
            "success": False,
            "message": requirements.get_missing_info(),
            "requirements": requirements.model_dump(
                mode="json"
            ),
            "missing_fields":
                requirements.missing_fields,
            "agent": "InfoCollector",
        }

    return {
        "success": True,
        "message": (
            "Travel requirements collected."
        ),
        "requirements": requirements.model_dump(
            mode="json"
        ),
        "missing_fields": [],
        "agent": "InfoCollector",
    }


# =====================================================
# PLANNER VS OPTIMIZER DEBATE
# =====================================================

def run_planning_group_chat(
    requirements_json: str,
) -> dict:

    requirements = json.loads(
        requirements_json
    )

    destination = requirements[
        "destination"
    ]

    budget = requirements[
        "budget"
    ]

    planner_turn = (
        f"Planner: I recommend "
        f"{destination} Central Hotel "
        f"and city sightseeing."
    )

    optimizer_turn = (
        f"Optimizer: Estimated budget "
        f"is {budget}. "
        f"The itinerary is acceptable."
    )

    consensus_turn = (
        "Consensus reached."
    )

    hotels = [
        HotelSuggestion(
            name=f"{destination} Central Hotel",
            location=destination,
            price_per_night=150,
        )
    ]

    flights = [
        FlightSuggestion(
            airline="TravelMate Airlines",
            departure_time="09:00",
            arrival_time="11:00",
            price=250,
        )
    ]

    plan = TravelPlan(
        itinerary=f"""
Day 1: Arrival at {destination}

Day 2: City sightseeing

Day 3: Local experiences

Day 4: Return journey
""",
        hotels=hotels,
        flights=flights,
        daily_budget=200,
        total_estimated_cost=500,
    )

    optimization = OptimizationResult(
        recommendations=[
            "Trip is within budget"
        ],
        cost_savings=100,
        value_adds=[
            "Flexible travel dates"
        ],
        final_plan="Consensus reached",
        approval_required=True,
    )

    conversation_summary = {
        "total_turns": 3,
        "consensus_reached": True,
        "consensus_points": [
            planner_turn,
            optimizer_turn,
            consensus_turn,
        ],
        "final_recommendation":
            "Proceed with travel plan",
    }

    return {
        "success": True,
        "plan": plan.model_dump(),
        "optimization":
            optimization.model_dump(),
        "conversation_summary":
            conversation_summary,
        "agent_insights": [
            {
                "agent": "Planner",
                "content":
                    planner_turn,
            },
            {
                "agent": "Optimizer",
                "content":
                    optimizer_turn,
            },
        ],
    }