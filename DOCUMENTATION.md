# ContextGraph AI - Technical Documentation


## 1. Executive Summary

Enterprise support teams handle complex incidents (e.g., billing disputes, server outages) that require combing through fragmented knowledge bases and strict corporate policies. 

Standard AI solutions pass massive blocks of text between models, leading to latency spikes, token limit breaches, and a lack of auditability. 

**ContextGraph AI** solves this by implementing a **LangGraph Blackboard Pattern**. Instead of passing raw text, intelligent agents communicate via a shared memory state (`AgentState`) using **Evidence Pointers**. This ensures no context degradation and provides a 100% cryptographically verifiable trace of exactly why an AI made a specific decision.

---

## 2. System Architecture

The core of ContextGraph AI is a cyclic state graph driven by [LangGraph](https://python.langchain.com/v0.1/docs/langgraph/). 

### The `AgentState` Blackboard
All agents read from and write to a centralized TypedDict called `AgentState`. 

```python
class AgentState(TypedDict):
    ticket_query: str                  # The user's original support ticket
    collected_pointers: List[str]      # Vector DB document IDs
    decision_trace: List[Dict]         # Audit trail of every action
    current_status: str                # PASS/FAIL evaluation state
    confidence_score: float            # AI confidence metric
    final_resolution: str              # The text shown to the user
    loop_count: int                    # Circuit breaker to prevent infinite loops
```

### The Node Workflow
The system executes a cyclical workflow of specialized agent nodes:

1. 📚 **Retriever Node**: Connects to ChromaDB (Vector Database) and searches for enterprise knowledge relevant to the ticket. It appends the `doc_ids` (pointers) to the state.
2. 🧠 **Reasoner Node**: Fetches the raw text *only* for the pointers it needs. It uses the LLM (Gemini) to formulate a resolution claim.
3. ⚖️ **Policy Node**: Acts as a strict compliance officer. It evaluates the Reasoner's claim against enterprise rules. If it violates a policy, it rejects the claim.
4. 🔬 **Evaluator Node**: A cyclic router. It reviews the trace history. If the Policy node rejected the claim, it sets the status to `FAIL` and routes the system back to the Reasoner for a retry. If it passes, it routes to Audit.
5. 💾 **Audit Node**: The terminal node. It securely writes the final resolution and the immutable JSON decision trace to a SQLite database.

---

## 3. Project Directory Structure

```text
ContextGraph AI/
├── backend/
│   ├── graph.py          # Core LangGraph logic, Agent nodes, and FastAPI endpoints
│   └── setup_db.py       # Initialization script for SQLite and ChromaDB ingestion
├── frontend/
│   └── app.py            # Streamlit dashboard UI
├── data/
│   ├── dummy_data/       # Markdown files containing enterprise policies and logs
│   ├── audit.db          # (Generated) SQLite database storing the audit logs
│   └── chroma_db/        # (Generated) Persistent vector store for knowledge retrieval
├── test_graph.py         # Pytest suite for automated boundary and behavior testing
├── start.sh              # Bash script to boot the backend and frontend simultaneously
├── Dockerfile            # Production-ready containerization configuration
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables (e.g., GOOGLE_API_KEY)
```

---

## 4. Local Setup & Deployment Guide

Follow these steps to run ContextGraph AI locally on your machine.

### Prerequisites
- Python 3.10+ installed.
- A free Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/app/apikey).

### Step-by-step Installation

**1. Clone and Configure Environment**
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**2. Setup Environment Variables**
Create a `.env` file in the root directory:
```env
GOOGLE_API_KEY=your_actual_gemini_api_key_here
```

**3. Initialize Databases**
This script parses the markdown files in `data/dummy_data/`, chunks them, and stores them in ChromaDB. It also creates the SQLite tables.
```bash
python backend/setup_db.py
```

**4. Start the Application**
You can start the system using the provided bash script, or run them manually in separate terminal windows.

*Using the start script (Mac/Linux/Git Bash):*
```bash
./start.sh
```

*Manual Startup:*
```bash
# Terminal 1: Start the Backend REST API
uvicorn backend.graph:app --port 8000 --reload

# Terminal 2: Start the Frontend UI
streamlit run frontend/app.py
```

Navigate to `http://localhost:8501` in your browser to interact with the dashboard.

---

## 5. API Reference

The backend exposes a single REST endpoint for processing incidents.

### `POST /resolve_incident`

**Request Body (JSON):**
```json
{
  "query": "The authentication service went down yesterday. We need a refund."
}
```

**Response Payload (JSON `AgentState`):**
Returns the fully resolved `AgentState` dictionary, including the final text and the complete JSON decision trace for compliance auditing.

---

## 6. Testing Guide

The project includes an exhaustive, asynchronous `pytest` suite that verifies structural bounds, infinite loop prevention (circuit breaking), and concurrent load handling.

To run the tests:
```bash
# Ensure testing libraries are installed
pip install pytest pytest-asyncio

# Execute the suite
pytest test_graph.py -v
```

### Key Test Scenarios:
- **`test_state_append_modifier`**: Ensures lists append data rather than overwrite it during handoffs.
- **`test_infinite_loop_circuit_breaker`**: Forces an endless loop to ensure the router correctly intercepts and forces an exit at 3 loops.
- **`test_concurrent_stream_event_loop`**: Fires 10 concurrent requests to ensure the event loop doesn't block during heavy LLM inference.
