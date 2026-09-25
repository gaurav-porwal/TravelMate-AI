from typing import Optional, Dict, Any, List

from .datamodels import HotelSuggestion, FlightSuggestion
from toolkits.weather_tool import WeatherTool
from toolkits.current_datetime import DateTimeTool
from toolkits.web_search_service import WebSearchService

weather_service = WeatherTool()
datetime_service = DateTimeTool()


def _safe_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Run a Tavily web search with a safe fallback.
    TAVILY_API_KEY must be set in your .env file (see config.py).
    """
    try:
        return WebSearchService().search(query=query, max_results=max_results)
    except Exception:
        return {
            "query": query,
            "results": [
                {
                    "title": f"Fallback result for: {query}",
                    "url": "",
                    "content": "Generated fallback result because web search is unavailable.",
                }
            ],
            "fallback": True,
        }


def hotel_search_tool(city: str = "Paris", checkin: str = "2025-12-01", checkout: str = "2025-12-05", adults: int = 1) -> List[HotelSuggestion]:
    """
    Search for hotels using the Tavily web search service.
    TODO: Parse and refine the search results into structured HotelSuggestion objects.
    """
    query = f"best hotels in {city} for {adults} adults from {checkin} to {checkout}"
    result = _safe_search(query, max_results=5)
    hotels: List[HotelSuggestion] = []
    for idx, item in enumerate(result.get("results", [])[:3]):
        title = item.get("title", f"Hotel Option {idx + 1}") if isinstance(item, dict) else str(item)
        hotels.append(
            HotelSuggestion(
                name=title,
                price_per_night=100.0 + (idx * 25.0),
                rating=4.0,
                location=city,
                amenities=["WiFi", "Breakfast"],
            )
        )
    return hotels


def flight_search_tool(origin: str = "London", destination: str = "Paris", departure_date: str = "2025-12-01", return_date: Optional[str] = None) -> List[FlightSuggestion]:
    """
    Search for flights using the Tavily web search service.
    TODO: Parse and refine the search results into structured FlightSuggestion objects.
    """
    query = f"flights from {origin} to {destination} on {departure_date}"
    if return_date:
        query += f" return {return_date}"

    result = _safe_search(query, max_results=5)
    flights: List[FlightSuggestion] = []
    for idx, item in enumerate(result.get("results", [])[:3]):
        title = item.get("title", f"Airline Option {idx + 1}") if isinstance(item, dict) else str(item)
        flights.append(
            FlightSuggestion(
                airline=title,
                departure_time=f"{departure_date}T09:00:00",
                arrival_time=f"{departure_date}T13:00:00",
                price=180.0 + (idx * 40.0),
                duration="4h",
                stops=0 if idx == 0 else 1,
            )
        )
    return flights


def weather_lookup_tool(city: str = "Paris", start_date: str = "2025-12-01", end_date: str = "2025-12-05") -> Dict[str, Any]:
    """
    Look up weather via the Open-Meteo based WeatherTool, falling back to
    web_search_service (Tavily) if the weather API is unavailable.
    """
    result = weather_service.get_weather_range(city, start_date, end_date)
    forecast = result.get("forecast", []) if isinstance(result, dict) else []

    if forecast:
        first_day = forecast[0]
        if isinstance(first_day, dict):
            return {
                "date": first_day.get("date", start_date),
                "forecast": first_day.get("description", ""),
                "high": first_day.get("temp_max", None),
                "low": first_day.get("temp_min", None),
            }
        return {"date": start_date, "forecast": str(first_day), "high": None, "low": None}

    # weather fallback via web search when the weather API fails or returns no data
    search = _safe_search(f"weather forecast in {city} from {start_date} to {end_date}", max_results=3)
    summary = search.get("results", [{}])[0]
    return {
        "date": start_date,
        "forecast": summary.get("title", "No weather data") if isinstance(summary, dict) else str(summary),
        "high": None,
        "low": None,
    }


def datetime_tool_func() -> Dict[str, Any]:
    result = datetime_service.get_today_date()
    return {"current_datetime": result.get("date", "") if isinstance(result, dict) else str(result)}


def local_experience_tool(city: str = "Paris") -> List[Dict[str, Any]]:
    """
    Find local experiences/activities using the Tavily web search service.
    """
    result = _safe_search(f"things to do in {city}", max_results=5)
    experiences: List[Dict[str, Any]] = []
    for r in result.get("results", []):
        if isinstance(r, dict):
            name = r.get("title", "Unknown Experience")
        else:
            name = str(r)
        experiences.append({"name": name, "category": "Activity", "price": 0})
    return experiences
