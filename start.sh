#!/bin/bash
# Initialize the SQLite databases and vector store
python backend/setup_db.py

# Start the FastAPI backend server in the background
# It will run on port 8000 locally inside this container
uvicorn backend.graph:app --host 0.0.0.0 --port 8000 &

# Start the Streamlit frontend server in the foreground
# It will run on port 8501 and will be exposed to the internet by Render
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
