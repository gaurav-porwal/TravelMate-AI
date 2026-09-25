"""
Phase 4 LangGraph Stateful Workflow
"""

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage

try:
    from langgraph.graph.message import add_messages
except Exception:
    def add_messages(existing, new):
        return (existing or []) + (new or [])

from api.datamodels import (
    ChatHistory,
)

from db.db_utils import (
    save_chat_message_service,
)

from phases.phase2_crewai.trip_agents import (
    collect_trip_requirements as phase2_collect_trip_requirements,
)

from phases.phase2_crewai.trip_agents import (
    create_travel_plan as phase2_create_travel_plan,
)

from phases.phase2_crewai.trip_agents import (
    optimize_travel_plan as phase2_optimize_travel_plan,
)

from toolkits.current_datetime import DateTimeTool
from toolkits.weather_tool import WeatherTool
from toolkits.web_search_service import WebSearchService


# ============================================================
# STATE
# ============================================================

class TravelState(TypedDict, total=False):

    messages: Annotated[
        List[BaseMessage],
        add_messages,
    ]

    phase: str
    thread_id: str

    user_id: int
    trip_id: Optional[int]

    user_input: str
    context_buffer: str

    conversation_history: List[
        Dict[str, Any]
    ]

    feedback: str

    requirements: Dict[str, Any]
    plan: Dict[str, Any]
    optimization: Dict[str, Any]

    weather_context: Dict[str, Any]
    tool_events: List[Dict[str, Any]]

    workflow_status: str
    next_node: str

    needs_clarification: bool
    missing_fields: List[str]

    clarification_question: str

    approval_mode: str
    approval_required: bool

    approval_status: str
    resume_available: bool

    wf_checkpoint_id: Optional[str]

    error: Optional[str]
    error_history: List[str]

    transition_log: List[
        Dict[str, Any]
    ]

    started_at: str
    updated_at: str


# ============================================================
# TRAVEL AGENTS
# ============================================================

class TravelAgents:

    def __init__(self):

        self.datetime_tool = (
            DateTimeTool()
        )

        self.weather_tool = (
            WeatherTool()
        )

        try:
            self.search_tool = (
                WebSearchService()
            )
        except Exception:
            self.search_tool = None

    # ----------------------------------------------------
    # INFO COLLECTOR
    # ----------------------------------------------------

    def info_collector_node(
        self,
        state: TravelState,
    ):

        try:

            requirements, _ = (
                phase2_collect_trip_requirements(
                    user_input=state[
                        "user_input"
                    ]
                )
            )

            if requirements.mode == "missing":

                return {
                    "requirements":
                        requirements.model_dump(
                            mode="json"
                        ),
                    "needs_clarification":
                        True,
                    "missing_fields":
                        requirements.missing_fields,
                    "clarification_question":
                        requirements.get_missing_info(),
                    "next_node":
                        "collect_travel_info",
                    "workflow_status":
                        "needs_clarification",
                    "updated_at":
                        datetime.now()
                        .isoformat(),
                }

            return {
                "requirements":
                    requirements.model_dump(
                        mode="json"
                    ),
                "needs_clarification":
                    False,
                "next_node":
                    "plan_travel_itinerary",
                "workflow_status":
                    "requirements_complete",
                "updated_at":
                    datetime.now()
                    .isoformat(),
            }

        except Exception as e:

            return {
                "error": str(e),
                "next_node":
                    "error_recovery",
            }

    # ----------------------------------------------------
    # PLANNER
    # ----------------------------------------------------

    def planner_node(
        self,
        state: TravelState,
    ):

        try:

            from api.datamodels import (
                TripRequirements
            )

            requirements = (
                TripRequirements(
                    **state[
                        "requirements"
                    ]
                )
            )

            plan = (
                phase2_create_travel_plan(
                    requirements
                )
            )

            weather = {}

            try:

                weather = (
                    self.weather_tool
                    .get_weather_range(
                        requirements.destination,
                        str(
                            requirements.trip_startdate
                        ),
                        str(
                            requirements.trip_enddate
                        ),
                    )
                )

            except Exception:

                weather = {
                    "fallback": True
                }

            return {
                "plan":
                    plan.model_dump(),
                "weather_context":
                    weather,
                "next_node":
                    "optimize_travel_plan",
                "workflow_status":
                    "planned",
                "updated_at":
                    datetime.now()
                    .isoformat(),
            }

        except Exception as e:

            return {
                "error": str(e),
                "next_node":
                    "error_recovery",
            }

    # ----------------------------------------------------
    # OPTIMIZER
    # ----------------------------------------------------

    def optimizer_node(
        self,
        state: TravelState,
    ):

        try:

            from api.datamodels import (
                TripRequirements,
                TravelPlan,
            )

            requirements = (
                TripRequirements(
                    **state[
                        "requirements"
                    ]
                )
            )

            plan = TravelPlan(
                **state["plan"]
            )

            optimization = (
                phase2_optimize_travel_plan(
                    requirements,
                    plan,
                )
            )

            return {
                "optimization":
                    optimization.model_dump(),
                "approval_required":
                    True,
                "next_node":
                    "approval",
                "workflow_status":
                    "awaiting_approval",
                "updated_at":
                    datetime.now()
                    .isoformat(),
            }

        except Exception as e:

            return {
                "error": str(e),
                "next_node":
                    "error_recovery",
            }

    # ----------------------------------------------------
    # APPROVAL
    # ----------------------------------------------------

    def approval_node(
        self,
        state: TravelState,
    ):

        checkpoint_id = (
            f"cp_"
            f"{datetime.now().timestamp()}"
        )

        return {
            "approval_status":
                "pending",
            "resume_available":
                True,
            "wf_checkpoint_id":
                checkpoint_id,
            "workflow_status":
                "awaiting_approval",
            "updated_at":
                datetime.now()
                .isoformat(),
        }

    # ----------------------------------------------------
    # COMPLETION
    # ----------------------------------------------------

    def completion_node(
        self,
        state: TravelState,
    ):

        return {
            "workflow_status":
                "completed",
            "approval_status":
                "approved",
            "updated_at":
                datetime.now()
                .isoformat(),
        }

    # ----------------------------------------------------
    # ERROR RECOVERY
    # ----------------------------------------------------

    def error_recovery_node(
        self,
        state: TravelState,
    ):

        error_history = (
            state.get(
                "error_history",
                []
            )
        )

        if state.get("error"):
            error_history.append(
                state["error"]
            )

        return {
            "workflow_status":
                "error",
            "error_history":
                error_history,
            "updated_at":
                datetime.now()
                .isoformat(),
        }


# ============================================================
# REQUIRED MODULE FUNCTIONS
# ============================================================

_TRAVEL_AGENTS = TravelAgents()


def collect_travel_info(
    state: TravelState,
):

    return (
        _TRAVEL_AGENTS
        .info_collector_node(
            state
        )
    )


def plan_travel_itinerary(
    state: TravelState,
):

    return (
        _TRAVEL_AGENTS
        .planner_node(
            state
        )
    )


def optimize_travel_plan(
    state: TravelState,
):

    return (
        _TRAVEL_AGENTS
        .optimizer_node(
            state
        )
    )


def approval_workflow_node(
    state: TravelState,
):

    return (
        _TRAVEL_AGENTS
        .approval_node(
            state
        )
    )


def completion_workflow_node(
    state: TravelState,
):

    return (
        _TRAVEL_AGENTS
        .completion_node(
            state
        )
    )


def error_recovery_workflow_node(
    state: TravelState,
):

    return (
        _TRAVEL_AGENTS
        .error_recovery_node(
            state
        )
    )