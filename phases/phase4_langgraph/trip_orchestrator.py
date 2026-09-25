"""
Phase 4 LangGraph Stateful Workflow Orchestrator
"""

import json
import uuid
from datetime import datetime

import db.db_utils as db_utils

from api.datamodels import (
    Trip,
    TravelPlan,
)

from phases.phase4_langgraph.trip_agents import (
    collect_travel_info,
    plan_travel_itinerary,
    optimize_travel_plan,
    approval_workflow_node,
    completion_workflow_node,
    TravelState,
)


class LangGraphTravelOrchestrator:

    def __init__(self):

        self.checkpoints = {}

    def plan_trip(
        self,
        user_input,
        user_id,
        trip_title="My Trip",
        phase="phase4_langgraph",
        approval_mode="manual",
        previous_state=None,
    ):

        try:

            thread_id = str(uuid.uuid4())

            if previous_state:
                state = previous_state

                state["user_input"] = (
                    state.get(
                        "user_input",
                        ""
                    )
                    + "\n"
                    + user_input
                )

            else:

                state: TravelState = {
                    "thread_id": thread_id,
                    "phase": phase,
                    "user_id": user_id,
                    "user_input": user_input,
                    "workflow_status":
                        "started",
                    "transition_log": [],
                    "started_at":
                        datetime.now()
                        .isoformat(),
                    "updated_at":
                        datetime.now()
                        .isoformat(),
                }

            # -----------------------------------------
            # INFO COLLECTOR
            # -----------------------------------------

            info_update = (
                collect_travel_info(
                    state
                )
            )

            state.update(
                info_update
            )

            if state.get(
                "needs_clarification"
            ):

                return {
                    "success": False,
                    "needs_clarification":
                        True,
                    "missing_fields":
                        state.get(
                            "missing_fields",
                            []
                        ),
                    "message":
                        state.get(
                            "clarification_question"
                        ),
                    "workflow_state":
                        state,
                }

            requirements = state[
                "requirements"
            ]

            trip = Trip(
                user_id=user_id,
                phase=phase,
                title=trip_title,
                origin=requirements[
                    "origin"
                ],
                destination=requirements[
                    "destination"
                ],
                trip_startdate=requirements[
                    "trip_startdate"
                ],
                trip_enddate=requirements[
                    "trip_enddate"
                ],
                no_of_adults=requirements[
                    "no_of_adults"
                ],
                no_of_children=requirements.get(
                    "no_of_children",
                    0
                ),
                budget=requirements[
                    "budget"
                ],
                currency=requirements.get(
                    "currency",
                    "INR"
                ),
                purpose=requirements.get(
                    "purpose",
                    "leisure"
                ),
                accommodation_type="hotel",
                travel_preferences="none",
                travel_constraints="none",
            )

            trip_id = (
                db_utils.create_trip(
                    trip
                )
            )

            state["trip_id"] = (
                trip_id
            )

            db_utils.update_trip_status(
                trip_id,
                "in_progress",
            )

            # -----------------------------------------
            # PLANNER
            # -----------------------------------------

            planner_update = (
                plan_travel_itinerary(
                    state
                )
            )

            state.update(
                planner_update
            )

            # -----------------------------------------
            # OPTIMIZER
            # -----------------------------------------

            optimizer_update = (
                optimize_travel_plan(
                    state
                )
            )

            state.update(
                optimizer_update
            )

            # -----------------------------------------
            # APPROVAL CHECKPOINT
            # -----------------------------------------

            approval_update = (
                approval_workflow_node(
                    state
                )
            )

            state.update(
                approval_update
            )

            checkpoint_id = state.get(
                "wf_checkpoint_id"
            )

            self.checkpoints[
                checkpoint_id
            ] = state

            plan = TravelPlan(
                **state["plan"]
            )

            plan_id = (
                db_utils
                .save_travel_plan_to_db(
                    plan,
                    trip_id,
                    version=1,
                )
            )

            return {
                "success": True,
                "trip_id": trip_id,
                "user_id": user_id,
                "phase":
                    "phase4_langgraph",
                "message":
                    "Trip planned with stateful workflow",
                "requirements":
                    state[
                        "requirements"
                    ],
                "plan":
                    state["plan"],
                "optimization":
                    state[
                        "optimization"
                    ],
                "plan_id":
                    plan_id,
                "approval_required":
                    True,
                "checkpoint_id":
                    checkpoint_id,
                "workflow_status":
                    "awaiting_approval",
                "workflow_state": {
                    "thread_id":
                        thread_id,
                    "next_node":
                        state.get(
                            "next_node"
                        ),
                    "transition_count":
                        len(
                            state.get(
                                "transition_log",
                                []
                            )
                        ),
                },
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }

    def continue_trip_clarification(
        self,
        previous_state,
        user_input,
        user_id,
        approval_mode="manual",
    ):

        return self.plan_trip(
            user_input=user_input,
            user_id=user_id,
            previous_state=previous_state,
            approval_mode=approval_mode,
        )

    def handle_human_approval(
        self,
        thread_id,
        decision,
    ):

        if (
            thread_id
            not in self.checkpoints
        ):

            return {
                "success": False,
                "message":
                    "Checkpoint not found",
            }

        state = self.checkpoints[
            thread_id
        ]

        return (
            self.continue_trip_approval(
                state["trip_id"],
                decision,
            )
        )

    def continue_trip_approval(
        self,
        trip_id,
        approval_decision,
        user_feedback="",
    ):

        try:

            trip_plan = (
                db_utils
                .get_trip_plan_by_trip_id(
                    trip_id
                )
            )

            if not trip_plan:

                return {
                    "success": False,
                    "message":
                        "Trip plan not found",
                }

            if (
                approval_decision.lower()
                == "approved"
            ):

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
                    "updated_status":
                        "approved",
                    "plan_id":
                        trip_plan.id,
                    "message":
                        "Travel plan approved with state persistence",
                    "workflow_status":
                        "completed",
                }

            db_utils.update_trip_plan_status(
                trip_plan.id,
                "rejected",
            )

            return {
                "success": True,
                "trip_id": trip_id,
                "approval": False,
                "updated_status":
                    "rejected",
                "plan_id":
                    trip_plan.id,
                "feedback":
                    user_feedback,
                "message":
                    "Travel plan rejected, workflow will resume from checkpoint",
                "next_node":
                    "optimizer",
                "resume_available":
                    True,
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }


class LangGraphTripOrchestrator(
    LangGraphTravelOrchestrator
):
    pass


def test_langgraph_orchestrator():

    orchestrator = (
        LangGraphTravelOrchestrator()
    )

    result = (
        orchestrator.plan_trip(
            user_input=(
                "I want to plan a trip "
                "from Bangalore to Goa "
                "from 2027-02-15 to "
                "2027-02-18 for 2 adults "
                "with a budget of 8000 INR"
            ),
            user_id=1,
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    test_langgraph_orchestrator()