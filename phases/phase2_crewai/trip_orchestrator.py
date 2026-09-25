# Disable telemetry FIRST - before any other imports
import os

os.environ["CREWAI_TELEMETRY"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"

import warnings
warnings.filterwarnings("ignore")

import json
from datetime import datetime, date
from typing import Optional

# CrewAI may not be installed in some lab environments
try:
    from crewai import Crew, Task, Process
except Exception:
    Crew = None
    Task = None
    Process = None

# Local imports
import db.db_utils as db_utils

from api.datamodels import (
    TripRequirements,
    Trip,
    TravelPlan,
    OptimizationResult,
    ChatHistory,
)

from db.db_utils import save_chat_message_service

from phases.phase2_crewai.trip_agents import (
    collect_trip_requirements,
    create_travel_plan,
    optimize_travel_plan,
    summarize_optimization,
    summarize_plan,
    summarize_requirements,
)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


class CrewAITripOrchestrator:
    """
    Phase 2 Sequential Workflow

    InfoCollector
        ->
    Planner
        ->
    Optimizer
    """

    def __init__(self):
        self.phase = "phase2_crewai"

    def plan_trip(
        self,
        user_input,
        user_id,
        trip_title="My Trip",
        approval_callback=None,
        conversation_history=None,
    ):
        try:

            # --------------------------------------------------
            # Save user message
            # --------------------------------------------------

            save_chat_message_service(
                ChatHistory(
                    trip_id=None,
                    user_id=user_id,
                    role="user",
                    phase=self.phase,
                    content=user_input,
                )
            )

            # --------------------------------------------------
            # INFO COLLECTOR
            # --------------------------------------------------

            requirements, combined_text = collect_trip_requirements(
                user_input=user_input,
                conversation_history=conversation_history,
            )

            save_chat_message_service(
                ChatHistory(
                    trip_id=None,
                    user_id=user_id,
                    role="assistant",
                    phase=self.phase,
                    content=summarize_requirements(requirements),
                )
            )

            # Missing information flow
            if requirements.mode == "missing":

                return {
                    "success": False,
                    "message": requirements.agent_message,
                    "requirements": requirements.model_dump(),
                }

            # --------------------------------------------------
            # CREATE TRIP RECORD
            # --------------------------------------------------

            trip = Trip(
                user_id=user_id,
                phase=self.phase,
                title=trip_title,
                origin=requirements.origin,
                destination=requirements.destination,
                trip_startdate=requirements.trip_startdate,
                trip_enddate=requirements.trip_enddate,
                no_of_adults=requirements.no_of_adults,
                no_of_children=requirements.no_of_children,
                budget=requirements.budget or 0,
                currency=requirements.currency,
                purpose=requirements.purpose,
                accommodation_type=requirements.accommodation_type,
                travel_preferences=requirements.travel_preferences,
                travel_constraints=requirements.travel_constraints,
            )

            trip_id = db_utils.create_trip(trip)

            db_utils.update_trip_status(
                trip_id,
                "in_progress"
            )

            # --------------------------------------------------
            # PLANNER
            # --------------------------------------------------

            plan = create_travel_plan(requirements)

            save_chat_message_service(
                ChatHistory(
                    trip_id=trip_id,
                    user_id=user_id,
                    role="assistant",
                    phase=self.phase,
                    content=summarize_plan(plan),
                )
            )

            plan_id = db_utils.save_travel_plan_to_db(
                plan,
                trip_id,
                version=1,
            )

            # --------------------------------------------------
            # OPTIMIZER
            # --------------------------------------------------

            optimization = optimize_travel_plan(
                requirements,
                plan,
            )

            save_chat_message_service(
                ChatHistory(
                    trip_id=trip_id,
                    user_id=user_id,
                    role="assistant",
                    phase=self.phase,
                    content=summarize_optimization(
                        optimization
                    ),
                )
            )

            # --------------------------------------------------
            # RESPONSE
            # --------------------------------------------------

            return {
                "success": True,
                "trip_id": trip_id,
                "plan_id": plan_id,
                "message": "Trip planned successfully",
                "requirements": requirements.model_dump(
                    mode="json"
                ),
                "plan": plan.model_dump(),
                "optimization": optimization.model_dump(),
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }

    def continue_trip_approval(
        self,
        trip_id,
        approval_decision,
        user_feedback="",
    ):

        try:

            trip_plan = db_utils.get_trip_plan_by_trip_id(
                trip_id
            )

            if not trip_plan:
                return {
                    "success": False,
                    "message": "Trip plan not found",
                }

            if approval_decision.lower() == "approved":

                db_utils.update_trip_status(
                    trip_id,
                    "confirmed",
                )

                db_utils.update_trip_plan_status(
                    trip_plan.id,
                    "approved",
                )

                return {
                    "success": True,
                    "trip_id": trip_id,
                    "approval": True,
                    "updated_status": "approved",
                    "plan_id": trip_plan.id,
                    "message": "Travel plan approved successfully",
                }

            db_utils.update_trip_status(
                trip_id,
                "draft",
            )

            db_utils.update_trip_plan_status(
                trip_plan.id,
                "rejected",
            )

            return {
                "success": True,
                "trip_id": trip_id,
                "approval": False,
                "updated_status": "rejected",
                "plan_id": trip_plan.id,
                "feedback": user_feedback,
                "message": "Travel plan rejected",
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }


def test_orchestrator():

    orchestrator = CrewAITripOrchestrator()

    result = orchestrator.plan_trip(
        user_input=(
            "I want to travel from Bangalore "
            "to Goa for 2 adults with budget "
            "8000 INR"
        ),
        user_id=1,
    )

    print(
        json.dumps(
            result,
            indent=2,
            cls=DateTimeEncoder,
        )
    )


if __name__ == "__main__":
    test_orchestrator()