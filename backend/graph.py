import os
import json
from dotenv import load_dotenv

load_dotenv()
import sqlite3
import operator
from typing import List, Dict, Any, Annotated
from typing_extensions import TypedDict
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import chromadb
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

app = FastAPI()

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'audit.db')
CHROMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')

# Global ChromaDB Client (Prevents SQLite file lock hanging)
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
chroma_collection = chroma_client.get_or_create_collection(name="enterprise_knowledge")

# Dynamic Proxy Injection Model Configuration
import os

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Fallback to prevent crash, alerting you in the container logs
    print("WARNING: GOOGLE_API_KEY environment variable is missing! Inject via Docker environment variables.")
    api_key = "your-proxy-token"

proxy_url = os.getenv("LITELLM_URL") # E.g., http://litellm:4000
client_opts = {}

if proxy_url:
    client_opts = {"client_options": {"api_endpoint": proxy_url}}

# LLM (Using ultra-fast, low-rate Flash-Lite model for tight loops)
primary_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite", 
    google_api_key=api_key,
    temperature=0,
    **client_opts
)

backup_llm_1 = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash", 
    google_api_key=api_key,
    temperature=0,
    **client_opts
)

backup_llm_2 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key=api_key,
    temperature=0,
    **client_opts
)

llm = primary_llm.with_fallbacks([backup_llm_1, backup_llm_2])

class AgentState(TypedDict):
    ticket_query: str
    collected_pointers: Annotated[List[str], operator.add] 
    decision_trace: Annotated[List[Dict[str, Any]], operator.add] 
    current_status: str
    confidence_score: float
    final_resolution: str
    needs_human_review: bool
    loop_count: int 

def extract_text(content):
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                texts.append(item["text"])
            elif isinstance(item, str):
                texts.append(item)
            else:
                texts.append(str(item))
        return " ".join(texts)
    return str(content)

# --- Nodes ---

def retriever_node(state: AgentState):
    query = state["ticket_query"]
    
    results = chroma_collection.query(query_texts=[query], n_results=3)
    
    retrieved_ids = []
    if results and "ids" in results and results["ids"]:
        retrieved_ids = results["ids"][0]
        
    trace_entry = {
        "agent": "Retriever", 
        "action": f"Found {len(retrieved_ids)} relevant chunks", 
        "pointers": retrieved_ids
    }
    
    return {
        "collected_pointers": retrieved_ids,
        "decision_trace": [trace_entry]
    }

def reasoner_node(state: AgentState):
    query = state["ticket_query"]
    pointers = state.get("collected_pointers", [])
    
    context_text = ""
    if pointers:
        results = chroma_collection.get(ids=pointers)
        if results and "documents" in results and results["documents"]:
            context_text = "\n\n".join(results["documents"])
            
    prompt = f"Ticket Query: {query}\n\nContext:\n{context_text}\n\nFormulate a resolution."
    
    try:
        response = llm.invoke([SystemMessage(content="You are a support resolution expert."), HumanMessage(content=prompt)])
        resolution_text = extract_text(response.content)
        confidence = 0.85 # Mock confidence calculation for now
    except Exception as e:
        resolution_text = f"Error generating resolution: {str(e)}"
        confidence = 0.0
        
    trace_entry = {
        "agent": "Reasoner", 
        "claim": resolution_text, 
        "confidence": confidence, 
        "source_pointer": pointers[0] if pointers else "None"
    }
    
    return {
        "final_resolution": resolution_text,
        "confidence_score": confidence,
        "decision_trace": [trace_entry]
    }

def policy_node(state: AgentState):
    resolution = state.get("final_resolution", "")
    
    prompt = f"Check if the following resolution violates any enterprise policies. Resolution: {resolution}\nReply strictly with 'Approved' or 'Rejected' followed by the reason."
    
    try:
        response = llm.invoke([SystemMessage(content="You are a strict compliance officer."), HumanMessage(content=prompt)])
        ruling_text = extract_text(response.content)
        is_approved = "Approved" in ruling_text
        ruling = "Approved" if is_approved else "Rejected"
    except Exception as e:
        ruling = "Rejected"
        ruling_text = str(e)
        
    trace_entry = {
        "agent": "Policy", 
        "ruling": ruling, 
        "violation_details": ruling_text
    }
    
    return {
        "decision_trace": [trace_entry]
    }

def evaluator_node(state: AgentState):
    trace = state.get("decision_trace", [])
    loop_count = state.get("loop_count", 0) + 1
    
    prompt = f"Review the decision trace: {json.dumps(trace)}\nDid the Policy node contradict the Reasoner? Is the confidence justified? Reply strictly with 'PASS' if everything is sound, or 'FAIL' if there is a contradiction."
    
    try:
        response = llm.invoke([SystemMessage(content="You are a critical workflow evaluator."), HumanMessage(content=prompt)])
        evaluator_text = extract_text(response.content)
        status = "PASS" if "PASS" in evaluator_text else "FAIL"
    except Exception:
        status = "FAIL"
        
    trace_entry = {
        "agent": "Evaluator",
        "action": f"Evaluated trace, result: {status}",
        "pointers": []
    }
        
    return {
        "current_status": status,
        "loop_count": loop_count,
        "decision_trace": [trace_entry]
    }

def audit_node(state: AgentState):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO AuditLog (ticket_id, query, final_resolution, decision_trace_json)
        VALUES (?, ?, ?, ?)
    """, (
        "TICKET-" + str(hash(state["ticket_query"]))[-5:], 
        state["ticket_query"], 
        state["final_resolution"], 
        json.dumps(state["decision_trace"])
    ))
    conn.commit()
    conn.close()
    
    trace_entry = {
        "agent": "Audit",
        "action": "Saved to AuditLog",
        "pointers": []
    }
    
    return {
        "decision_trace": [trace_entry]
    }

# --- Routing ---
def route_after_evaluation(state: AgentState):
    # Short-circuit if the loop count hits the circuit breaker threshold
    if state.get("loop_count", 0) >= 3:
        return "audit" # Force push to storage even if it failed verification
        
    if state.get("current_status") == "FAIL":
        return "reasoner" # Retry loop
        
    return "audit" # Success route

# --- Graph Setup ---
workflow = StateGraph(AgentState)

workflow.add_node("retriever", retriever_node)
workflow.add_node("reasoner", reasoner_node)
workflow.add_node("policy", policy_node)
workflow.add_node("evaluator", evaluator_node)
workflow.add_node("audit", audit_node)

workflow.set_entry_point("retriever")

workflow.add_edge("retriever", "reasoner")
workflow.add_edge("reasoner", "policy")
workflow.add_edge("policy", "evaluator")

workflow.add_conditional_edges(
    "evaluator",
    route_after_evaluation,
    {
        "reasoner": "reasoner",
        "audit": "audit"
    }
)

workflow.add_edge("audit", END)

graph = workflow.compile()

# --- API Endpoints ---
class TicketRequest(BaseModel):
    query: str

@app.post("/resolve_incident")
def resolve_incident(req: TicketRequest):
    initial_state = {
        "ticket_query": req.query,
        "collected_pointers": [],
        "decision_trace": [],
        "current_status": "PENDING",
        "confidence_score": 0.0,
        "final_resolution": "",
        "needs_human_review": False,
        "loop_count": 0
    }
    
    final_state = graph.invoke(initial_state)
    return final_state
