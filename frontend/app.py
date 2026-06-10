import streamlit as st
import requests
import os

# API URL (Uses environment variable for Docker compatibility, defaults to localhost)
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(layout="wide", page_title="ContextGraph AI", page_icon="🏢")

# Custom CSS for the dashboard feel
st.markdown("""
<style>
.stApp {
    background-color: #0e1117;
    color: #fafafa;
}
.success-box {
    background-color: #004d40;
    color: #e0f2f1;
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #00695c;
    margin-top: 20px;
}
.agent-header {
    font-weight: 600;
    font-size: 1.1em;
    color: #64ffda;
}
</style>
""", unsafe_allow_html=True)

st.title("ContextGraph AI 🏢")
st.subheader("Traceable Multi-Agent Incident Resolution")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📝 Workspace")
    ticket_query = st.text_area("Enter Support Ticket / Incident", height=150, placeholder="e.g., The authentication service went down yesterday for 4 hours. We need a refund.")
    
    if st.button("Resolve Incident", type="primary"):
        if not ticket_query.strip():
            st.warning("Please enter an incident query.")
        else:
            with st.spinner("Agents are resolving the incident..."):
                try:
                    # Point to the FastAPI backend
                    response = requests.post(f"{BACKEND_URL}/resolve_incident", json={"query": ticket_query})
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    st.markdown("### 🎯 Final Resolution")
                    resolution = data.get("final_resolution", "No resolution provided.")
                    st.markdown(f"<div class='success-box'>{resolution}</div>", unsafe_allow_html=True)
                    
                    # Store trace in session state to render in right column
                    st.session_state["decision_trace"] = data.get("decision_trace", [])
                    st.session_state["final_state"] = data
                    
                except Exception as e:
                    st.error(f"Failed to connect to backend: {e}")

with col_right:
    st.markdown("### 🔍 Audit & Traceability")
    
    trace = st.session_state.get("decision_trace", [])
    
    if not trace:
        st.info("Submit an incident to see the agent decision trace.")
    else:
        for i, step in enumerate(trace):
            agent_name = step.get("agent", "Unknown Agent")
            
            # Map agent names to emojis
            emoji = "🕵️"
            if agent_name == "Retriever": emoji = "📚"
            elif agent_name == "Reasoner": emoji = "🧠"
            elif agent_name == "Policy": emoji = "⚖️"
            elif agent_name == "Evaluator": emoji = "🔬"
            elif agent_name == "Audit": emoji = "💾"
            
            with st.expander(f"Step {i+1}: {emoji} {agent_name}", expanded=True):
                # Display Claim/Ruling/Action
                if "action" in step:
                    st.markdown(f"**Action:** {step['action']}")
                if "claim" in step:
                    st.markdown(f"**Claim:** {step['claim']}")
                if "ruling" in step:
                    st.markdown(f"**Ruling:** {step['ruling']}")
                    if "violation_details" in step:
                        st.markdown(f"**Details:** {step['violation_details']}")
                
                # Display Confidence
                if "confidence" in step:
                    conf = float(step["confidence"])
                    st.markdown("**Confidence Score:**")
                    st.progress(conf)
                    st.caption(f"{conf:.2f} / 1.0")
                
                # Display Evidence Pointers
                pointers = step.get("pointers", [])
                if not pointers and "source_pointer" in step:
                    if step["source_pointer"] != "None":
                        pointers = [step["source_pointer"]]
                        
                if pointers:
                    st.markdown("**Evidence Pointers:**")
                    for p in pointers:
                        st.code(p, language="text")
