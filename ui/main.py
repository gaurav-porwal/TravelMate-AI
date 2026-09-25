# ui/main.py - LEARNING PROJECT UI
# TODO: This shows placeholder responses to demonstrate UI structure
# Replace placeholder logic with actual AI agent integration when implementing

import streamlit as st
import requests
import json
import pandas as pd
from pathlib import Path
import sys

API_BASE_URL = "http://localhost:8000"

# Add project root to path for db_utils
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
try:
    from db import db_utils
except ImportError:
    from db import db_utils

# -----------------------------
# API helper functions (moved to top)
# -----------------------------
def plan_trip_api(user_input, user_id, phase):
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/plan_trip",
            params={"user_input": user_input, "user_id": user_id, "phase": phase},
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
    return None

def approve_api(trip_id, user_id, approval, feedback=None):
    payload = {"trip_id": trip_id, "user_id": user_id, "approval": approval}
    if feedback:
        payload["feedback"] = feedback
    try:
        response = requests.post(f"{API_BASE_URL}/api/v1/approve", json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
    return None

st.set_page_config(page_title="TravelMate AI", layout="wide")

# Sidebar Navigation
st.sidebar.title("TravelMate AI")
page = st.sidebar.radio("Navigate", ["Welcome Page", "Trip Planner", "Database Viewer"])

# -----------------------------
# Welcome Page
# -----------------------------
if page == "Welcome Page":
    st.title("Welcome to TravelMate AI - Learning Project")
    st.markdown("""
    ## [LEARNING PROJECT] AI Multi-Agent Travel Planning System
    
    This is a **hands-on learning project** where you'll implement AI agents across different frameworks.
    
    ### What's Already Provided:
    - [PROVIDED] **Database layer** (`db/`) - Complete schema, models, and utilities
    - [PROVIDED] **API toolkits** (`toolkits/`) - Tavily web search, weather, and datetime tools
    - [PROVIDED] **Configuration** (`config.py`) - API key management
    - [PARTIAL] **UI Interface** (this Streamlit app) - Template structure, you connect the agents
    - [PROVIDED] **Data models** (`api/datamodels.py`) - All Pydantic models
    
    ### Your Learning Tasks (Implement These):
    - **Phase 2:** Implement CrewAI agents in `phases/phase2_crewai/`
    - **Phase 3:** Implement AutoGen agents in `phases/phase3_autogen/`  
    - **Phase 4:** Implement LangGraph workflow in `phases/phase4_langgraph/`
    - **API Layer:** Complete FastAPI endpoints in `api/app.py`
    - **UI Connection:** Connect your agents to replace placeholder messages
    
    ### Learning Progression:
    1. **Phase 2 (CrewAI):** Sequential agent workflow - InfoCollector → Planner → Optimizer
    2. **Phase 3 (AutoGen):** Collaborative debate - Agents discuss and reach consensus  
    3. **Phase 4 (LangGraph):** Stateful workflows - Human-in-the-loop, persistence, recovery
    
    ### Test Users (Pre-loaded in Database):
    - **Alice:** Luxury traveler (art, fine dining)
    - **Bob:** Budget backpacker (adventure, local experiences) 
    - **Carla:** Family travel (safety, kid-friendly)
    - **David:** Business travel (efficiency, business amenities)
    - **Emma:** Student travel (budget, authentic experiences)
    
    **[NEXT STEP]** Go to Trip Planner → Select User → Choose "Start New Trip" → Try chatting!
    """)

# -----------------------------
# Trip Planner (Chat-style, API-driven)
# -----------------------------
elif page == "Trip Planner":
    st.title("TravelMate Trip Planner")
    
    # API Status Check
    try:
        test_response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if test_response.status_code == 200:
            st.success("✅ API Server is running - Connect your agents to enable full functionality!")
        else:
            st.warning("⚠️ API Server responded with error - Showing placeholder mode")
    except requests.RequestException:
        st.info("**Learning Mode:** API server is not running. UI shows placeholder responses to demonstrate functionality.")
    
    st.markdown("""
        Use the chat below to describe your trip in natural language.
        **Example Inputs:**

1. **Complete Query:**
    'I want to plan a leisure trip from Bangalore to Goa from December 15-18, 2025, for 2 adults with a budget of 8000 INR.'

2. **Multi-turn (2-turn) Query:**                  
    - Turn 1: 'I want to plan a solo business trip from Mumbai to Singapore.'
    - Turn 2: '"Next month for 4 days starting on the 15th with a budget of $1200 USD"'
""")
    from db import db_utils
    trip_id = None  # Initialize trip_id at the beginning
    with st.sidebar:
        st.header("Configuration")
        phase = st.selectbox("AI Phase", ["phase2_crewai", "phase3_autogen", "phase4_langgraph"])
        user_list = db_utils.get_all_users()
        if user_list:
            username = st.selectbox("User", user_list)
            user_id = db_utils.get_user_id_by_name(username)
            # Trip selection for user
            trips = db_utils.get_trips_by_user_name(username)
            trip_options = {f"{t['title']} (ID {t['id']})": t['id'] for t in trips} if trips else {}
            
            # Add "Start New Trip" option
            trip_options["Start New Trip"] = "new_trip"
            
            selected_trip_option = st.selectbox("Select Trip", list(trip_options.keys()))
            
            if selected_trip_option == "Start New Trip":
                trip_id = None
                st.info("[CHAT] Start chatting to create a new trip! Just describe your travel plans.")
            elif selected_trip_option:
                trip_id = trip_options[selected_trip_option]
                trip_details = db_utils.get_trip_with_plan(trip_id)
                if trip_details:
                    with st.expander("Trip Details", expanded=False):
                        st.write(f"**Trip:** {trip_details['title']}")
                        st.write(f"**Route:** {trip_details['origin']} to {trip_details['destination']}")
                        st.write(f"**Dates:** {trip_details['trip_startdate']} to {trip_details['trip_enddate']}")
                        st.write(f"**Status:** {trip_details['trip_status']}")
                        
                        # Show plan details if available
                        if trip_details.get('plan_status'):
                            st.write(f"**Plan Status:** {trip_details['plan_status']}")
                            st.write(f"**Plan Version:** {trip_details.get('plan_version', 'N/A')}")
                            if trip_details.get('total_estimated_cost'):
                                st.write(f"**Estimated Cost:** ${trip_details['total_estimated_cost']}")
                            
                            # Show detailed plan if available
                            try:
                                import json
                                if trip_details.get('hotels_json'):
                                    hotels = json.loads(trip_details['hotels_json'])
                                    st.write(f"**Hotels:** {len(hotels)} options")
                                if trip_details.get('flights_json'):
                                    flights = json.loads(trip_details['flights_json'])
                                    st.write(f"**Flights:** {len(flights)} options")
                            except:
                                pass
                        else:
                            st.write("**Plan Status:** No plan generated yet")
        else:
            st.error("[LEARNING PROJECT] No users found in database. Run the database setup first!")
            username = None
            user_id = None
            trip_id = None

    # Chat history state
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "trip_id" not in st.session_state:
        st.session_state["trip_id"] = None
    if "plan" not in st.session_state:
        st.session_state["plan"] = None
    if "awaiting_approval" not in st.session_state:
        st.session_state["awaiting_approval"] = False
    
    # Clear chat when user or trip selection changes
    if "current_selected_trip" not in st.session_state:
        st.session_state["current_selected_trip"] = None
    if "current_selected_user" not in st.session_state:
        st.session_state["current_selected_user"] = None
    
    # Check if user or trip selection has changed
    current_trip_selection = trip_id if trip_id != "new_trip" else None
    current_user_selection = user_id if 'user_id' in locals() and user_id else None
    
    if (st.session_state["current_selected_trip"] != current_trip_selection or 
        st.session_state["current_selected_user"] != current_user_selection):
        # Clear chat history and related state when switching users or trips
        st.session_state["messages"] = []
        st.session_state["plan"] = None
        st.session_state["awaiting_approval"] = False
        
        # Load historical chat for existing trips
        if current_trip_selection is not None and current_user_selection is not None:
            try:
                # Load chat history from database for this specific trip
                historical_messages = db_utils.load_chat_history(current_trip_selection)
                if historical_messages:
                    # Convert database records to chat message format
                    for msg in historical_messages:
                        role = msg.get('role', 'assistant')  # role is already in correct format
                        st.session_state["messages"].append({
                            "role": role,
                            "content": msg.get('content', '')
                        })
            except Exception as e:
                # If historical chat loading fails, start with empty chat
                st.info(f"Starting fresh chat (historical messages unavailable: {str(e)})")
                st.session_state["messages"] = []
        
        # Update tracking variables
        st.session_state["current_selected_trip"] = current_trip_selection
        st.session_state["current_selected_user"] = current_user_selection

    # Show chat history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input - now works for both existing trips and new trip creation
    prompt = st.chat_input("Ask your travel planner...")
    if prompt and user_id:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        # Determine if this is for a new trip or existing trip
        current_trip_id = trip_id if 'trip_id' in locals() else None
        
        # Call API
        plan = plan_trip_api(prompt, user_id, phase)
        
        # Show placeholder message when API is not available
        if plan is None:
            # Different messages for new vs existing trips
            if current_trip_id is None:
                placeholder_message = f"""
**[LEARNING PROJECT] NEW TRIP CREATION**

Your request: *"{prompt}"*

**To implement:** 
- Choose your AI framework (Phase 2/3/4)
- Implement agents in the respective phase folder
- Connect agents to replace this placeholder

**Hint:** Start with CrewAI Phase 2 for sequential agent workflow!
"""
            else:
                placeholder_message = f"""
**[LEARNING PROJECT] TRIP MODIFICATION**

Your request: *"{prompt}"*  
Trip ID: {current_trip_id}

**To implement:**
- Load existing trip data using db_utils
- Analyze modification request with your agents  
- Update trip plan and save changes

**Hint:** Use the same agents but with trip context!
"""
            
            st.session_state["messages"].append({"role": "assistant", "content": placeholder_message})
            with st.chat_message("assistant"):
                st.markdown(placeholder_message)
            
            # Don't set awaiting_approval for placeholder responses
            st.session_state["awaiting_approval"] = False
            st.session_state["plan"] = None
            
        else:

            template_plan = plan

            st.session_state["plan"] = template_plan

            if template_plan.get("success", False):
                st.session_state["awaiting_approval"] = True
                st.session_state["trip_id"] = template_plan.get(
                    "trip_id",
                    None
                )
            else:
                st.session_state["awaiting_approval"] = False

            summary_lines = []

            if template_plan.get("success"):

                req = template_plan.get(
                    "requirements",
                    {}
                )

                summary_lines.append(
                    f"**Trip:** {req.get('origin', '?')} to "
                    f"{req.get('destination', '?')}"
                )

                summary_lines.append(
                    f"**Budget:** "
                    f"{req.get('budget', '?')} "
                    f"{req.get('currency', 'USD')}"
                )

                plan_data = template_plan.get(
                    "plan",
                    {}
                )

                if plan_data.get("itinerary"):
                    summary_lines.append(
                        f"**Itinerary:**\n{plan_data['itinerary']}"
                    )

                hotels = plan_data.get(
                    "hotels",
                    []
                )

                if hotels:
                    hotel = hotels[0]

                    summary_lines.append(
                        f"**Hotel:** "
                        f"{hotel.get('name', 'N/A')}"
                    )

                flights = plan_data.get(
                    "flights",
                    []
                )

                if flights:
                    flight = flights[0]

                    summary_lines.append(
                        f"**Flight:** "
                        f"{flight.get('airline', 'N/A')}"
                    )

                optimization = template_plan.get(
                    "optimization",
                    {}
                )

                recommendations = optimization.get(
                    "recommendations",
                    []
                )

                if recommendations:

                    summary_lines.append(
                        "**Recommendations:**"
                    )

                    for rec in recommendations:

                        summary_lines.append(
                            f"- {rec}"
                        )

            else:

                summary_lines.append(
                    template_plan.get(
                        "message",
                        "Unable to generate trip."
                    )
                )

            assistant_content = "\n".join(
                summary_lines
            )

            st.session_state["messages"].append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                }
            )

            with st.chat_message("assistant"):
                st.markdown(
                    assistant_content
                )

    # Approval logic (only show when API is working and plan is available)
    if st.session_state["awaiting_approval"] and st.session_state["plan"] and user_id:
        st.write("#### Do you approve this plan?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve"):
                approve_result = approve_api(st.session_state["trip_id"], user_id, True)
                if approve_result:
                    st.success("Trip approved!")
                    st.session_state["awaiting_approval"] = False
                    st.session_state["messages"].append({"role": "assistant", "content": str(approve_result)})
                else:
                    st.error("[LEARNING PROJECT] Could not connect to API server. Implement your FastAPI approval endpoints first!")
        with col2:
            feedback = st.text_input("Feedback for revision", key="feedback")
            if st.button("Reject/Revise"):
                reject_result = approve_api(st.session_state["trip_id"], user_id, False, feedback)
                if reject_result:
                    st.warning("Plan sent for revision. Await updated plan.")
                    st.session_state["awaiting_approval"] = False
                    st.session_state["messages"].append({"role": "assistant", "content": str(reject_result)})
                else:
                    st.error("[LEARNING PROJECT] Could not connect to API server. Implement your FastAPI approval endpoints first!")

    # Raw API output
    if st.session_state["plan"]:
        with st.expander("Raw API Output", expanded=False):
            st.json(st.session_state["plan"])

# -----------------------------
# Database Viewer
# -----------------------------
elif page == "Database Viewer":
    st.title("Database Tables")

    tables = ["users", "trips", "trip_plans", "chat_history"]
    selected_table = st.selectbox("Select a table", tables)

    try:
        df = db_utils.load_table_as_dataframe(selected_table)
        if not df.empty:
            st.dataframe(df.astype(str), use_container_width=True)
            st.subheader("Table Statistics")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Rows", len(df))
            with col2:
                st.metric("Columns", len(df.columns))
            with col3:
                if selected_table == "trips":
                    active_trips = len(df[df['trip_status'].isin(['draft', 'confirmed', 'in_progress'])])
                    st.metric("Active Trips", active_trips)
                elif selected_table == "trip_plans":
                    if 'status' in df.columns:
                        approved_plans = len(df[df['status'] == 'approved'])
                        st.metric("Approved Plans", approved_plans)
                    else:
                        st.metric("Total Plans", len(df))
                elif selected_table == "chat_history":
                    recent_messages = len(df[df['created_at'] > pd.Timestamp.now() - pd.Timedelta(days=7)])
                    st.metric("Recent Messages (7d)", recent_messages)
                else:
                    st.metric("Recent Entries", len(df))
        else:
            st.warning(f"Table {selected_table} is empty or could not be loaded. Check database setup.")
    except Exception as e:
        st.error(f"[LEARNING PROJECT] Could not load table {selected_table}: {e}")
    if st.button("Refresh Data"):
        st.rerun()