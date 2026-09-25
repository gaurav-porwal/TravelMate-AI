"""
Phase 3 AutoGen Orchestrator
InfoCollector -> Planner/Optimizer Debate -> Consensus
"""

import json
import os
import sys

sys.path.insert(
    0,
    os.path.abspath(
        os.path.dirname(__file__) + "/../.."
    ),
)

import db.db_utils as db_utils

from api.datamodels import (
    Trip,
    ChatHistory,
)

from db.db_utils import (
    save_chat_message_service,
)

from phases.phase3_autogen.trip_agents import (
    run_info_collection,
    run_planning_group_chat,
)


class AutoGenTripOrchestrator:

    def __init__(self):

        self.phase = "phase3_autogen"

    def plan_trip(
        self,
        user_input,
        user_id,
        trip_title="My Trip",
        approval_mode="auto",
    ):

        try:

            save_chat_message_service(
                ChatHistory(
                    trip_id=None,
                    user_id=user_id,
                    role="user",
                    phase=self.phase,
                    content=user_input,
                )
            )

            # ----------------------------------
            # INFO COLLECTOR
            # ----------------------------------

            info_result = run_info_collection(
                user_input
            )

            if not info_result["success"]:

                return {
                    "success": False,
                    "message":
                        info_result["message"],
                    "requirements":
                        info_result["requirements"],
                    "missing_fields":
                        info_result["missing_fields"],
                }

            requirements = info_result[
                "requirements"
            ]

            trip = Trip(
                user_id=user_id,
                phase=self.phase,
                title=trip_title,
                origin=requirements["origin"],
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
                    0,
                ),
                budget=requirements["budget"],
                currency=requirements.get(
                    "currency",
                    "INR",
                ),
                purpose=requirements.get(
                    "purpose",
                    "leisure",
                ),
                accommodation_type="hotel",
                travel_preferences="none",
                travel_constraints="none",
            )

            trip_id = db_utils.create_trip(
                trip
            )

            db_utils.update_trip_status(
                trip_id,
                "in_progress",
            )

            # ----------------------------------
            # DEBATE
            # ----------------------------------

            debate_result = (
                run_planning_group_chat(
                    json.dumps(requirements)
                )
            )

            plan = debate_result["plan"]

            optimization = debate_result[
                "optimization"
            ]

            conversation_summary = (
                debate_result[
                    "conversation_summary"
                ]
            )

            agent_insights = debate_result[
                "agent_insights"
            ]

            for insight in agent_insights:

                save_chat_message_service(
                    ChatHistory(
                        trip_id=trip_id,
                        user_id=user_id,
                        role="assistant",
                        phase=self.phase,
                        content=(
                            f"{insight['agent']}: "
                            f"{insight['content']}"
                        ),
                    )
                )

            # save plan

            from api.datamodels import (
                TravelPlan
            )

            plan_obj = TravelPlan(
                **plan
            )

            plan_id = (
                db_utils
                .save_travel_plan_to_db(
                    plan_obj,
                    trip_id,
                    1,
                )
            )

            db_utils.update_trip_status(
                trip_id,
                "completed",
            )

            return {
                "success": True,
                "trip_id": trip_id,
                "plan_id": plan_id,
                "message":
                    "Trip planned through agent conversation",
                "requirements":
                    requirements,
                "conversation_summary":
                    conversation_summary,
                "consensus_plan":
                    plan,
                "plan":
                    plan,
                "optimization":
                    optimization,
                "agent_insights":
                    agent_insights,
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
                        "Travel plan approved through agent conversation",
                    "conversation_summary":
                        "Agent consensus reached on approval",
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
                    "Travel plan rejected, agents will reconvene",
                "next_conversation":
                    "Agents will debate based on feedback",
            }

        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }


def test_autogen_orchestrator():

    orchestrator = (
        AutoGenTripOrchestrator()
    )

    result = (
        orchestrator.plan_trip(
            user_input=(
                "I want to plan a trip "
                "from Bangalore to Goa "
                "from 2027-02-15 to "
                "2027-02-18 for 2 adults "
                "with budget 8000 INR"
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
    test_autogen_orchestrator()