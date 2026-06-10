#!/bin/bash
# Initialize the SQLite databases and vector store
python backend/setup_db.py

# Start the FastAPI backend server in the background
# It will run on port 8000 locally inside this container
uvicorn backend.graph:app --host 0.0.0.0 --port 8000 &

# Start the Streamlit frontend server in the foreground
# It will run on the port provided by Render, and will be exposed to the internet
PORT=${PORT:-8501}
streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0
