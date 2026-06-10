import os
import sqlite3
import chromadb
from chromadb.utils import embedding_functions

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'audit.db')
CHROMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma_db')
DUMMY_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dummy_data')

def setup_sqlite():
    print("Setting up SQLite...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AuditLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            query TEXT,
            final_resolution TEXT,
            decision_trace_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("SQLite setup complete.")

def setup_chroma():
    print("Setting up ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # We will use a default embedding function for simplicity
    emb_fn = embedding_functions.DefaultEmbeddingFunction()
    
    collection = client.get_or_create_collection(
        name="enterprise_knowledge",
        embedding_function=emb_fn
    )

    # Read markdown files
    documents = []
    metadatas = []
    ids = []
    
    if not os.path.exists(DUMMY_DATA_PATH):
        print(f"Data path {DUMMY_DATA_PATH} not found.")
        return

    for filename in os.listdir(DUMMY_DATA_PATH):
        if filename.endswith('.md'):
            filepath = os.path.join(DUMMY_DATA_PATH, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Naive chunking for this example (by double newline)
            chunks = content.split('\n\n')
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                doc_id = f"{filename}_chunk_{i}"
                documents.append(chunk.strip())
                metadatas.append({"source": filename, "chunk_index": i})
                ids.append(doc_id)

    if documents:
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Ingested {len(documents)} chunks into ChromaDB.")
    else:
        print("No dummy data found to ingest.")
    
    print("ChromaDB setup complete.")

if __name__ == "__main__":
    setup_sqlite()
    setup_chroma()
