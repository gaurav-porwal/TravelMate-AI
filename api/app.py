"""
TravelMate AI API
Phase 2 CrewAI Integration
"""

import sys
import os

# Add project root to Python path
project_root = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../.."
    )
)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from typing import Optional

from api.datamodels import (
    ApprovalRequest,
    TravelPlan,
)

from db import db_utils

# Phase 2
from phases.phase2_crewai.trip_orchestrator import (
    CrewAITripOrchestrator
)

app = FastAPI(
    title="TravelMate AI API",
    version="1.0.0"
)

# ------------------------------------------------------------------
# ORCHESTRATORS
# ------------------------------------------------------------------

from phases.phase3_autogen.trip_orchestrator import (
    AutoGenTripOrchestrator
)
from phases.phase4_langgraph.trip_orchestrator import (
    LangGraphTravelOrchestrator,
)
ORCHESTRATOR_MAP = {
    "phase2_crewai": CrewAITripOrchestrator,
    "phase3_autogen": AutoGenTripOrchestrator,
    "phase4_langgraph": LangGraphTravelOrchestrator,
}

# ------------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------------

@app.get("/")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TravelMate AI API"
    }

# ------------------------------------------------------------------
# PLAN TRIP
# ------------------------------------------------------------------

@app.post("/api/v1/plan_trip")
def plan_trip(
    user_input: str,
    user_id: int,
    phase: str = "phase2_crewai"
):
    """
    Main trip planning endpoint
    """

    try:

        orchestrator_class = ORCHESTRATOR_MAP.get(phase)

        if orchestrator_class is None:
            return {
                "success": False,
                "error": f"Unsupported phase: {phase}"
            }

        orchestrator = orchestrator_class()

        result = orchestrator.plan_trip(
            user_input=user_input,
            user_id=user_id,
        )

        return result

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

# ------------------------------------------------------------------
# APPROVE TRIP
# ------------------------------------------------------------------

@app.post("/api/v1/approve")
def approve_trip(request: ApprovalRequest):

    try:

        orchestrator = CrewAITripOrchestrator()

        if request.approval:

            result = orchestrator.continue_trip_approval(
                trip_id=request.trip_id,
                approval_decision="approved",
                user_feedback=request.feedback or "",
            )

        else:

            result = orchestrator.continue_trip_approval(
                trip_id=request.trip_id,
                approval_decision="rejected",
                user_feedback=request.feedback or "",
            )

        result["user_id"] = request.user_id

        return result

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }

# ------------------------------------------------------------------
# GET PLAN
# ------------------------------------------------------------------

@app.get("/api/v1/trip/{trip_id}/plan")
def get_trip_plan(
    trip_id: int,
    version: Optional[int] = None,
):

    try:

        trip_plan = db_utils.get_trip_plan_by_trip_id(
            trip_id,
            version
        )

        if trip_plan:

            return {
                "success": True,
                "plan": trip_plan.to_travel_plan().model_dump(),
                "metadata": {
                    "trip_id": trip_plan.trip_id,
                    "version": trip_plan.version,
                    "status": trip_plan.status,
                    "generated_at": trip_plan.generated_at,
                }
            }

        return {
            "success": False,
            "error": "Trip plan not found",
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }

# ------------------------------------------------------------------
# SAVE PLAN
# ------------------------------------------------------------------

@app.post("/api/v1/trip/{trip_id}/plan")
def save_trip_plan(
    trip_id: int,
    travel_plan: TravelPlan,
    version: int = 1,
):

    try:

        plan_id = db_utils.save_travel_plan_to_db(
            travel_plan,
            trip_id,
            version,
        )

        return {
            "success": True,
            "plan_id": plan_id,
            "message": f"Trip plan saved for trip {trip_id}",
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }

# ------------------------------------------------------------------
# UPDATE PLAN STATUS
# ------------------------------------------------------------------

@app.put("/api/v1/trip-plan/{plan_id}/status")
def update_plan_status(
    plan_id: int,
    status: str,
):

    try:

        updated = db_utils.update_trip_plan_status(
            plan_id,
            status,
        )

        if updated:

            return {
                "success": True,
                "message":
                    f"Plan status updated to {status}"
            }

        return {
            "success": False,
            "error":
                "Plan not found or update failed"
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    print("TravelMate AI API Started")