from chromadb import Documents, EmbeddingFunction, Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class LangchainGoogleEmbeddingFunction(EmbeddingFunction):
    """
    A custom wrapper that allows ChromaDB to use the reliable 
    langchain-google-genai embeddings package, bypassing Chroma's
    deprecated internal Google integration.
    """
    def __init__(self, api_key: str):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            google_api_key=api_key
        )
        
    def __call__(self, input: Documents) -> Embeddings:
        # ChromaDB provides a list of strings (Documents)
        # Langchain expects a list of strings and returns a list of float lists (Embeddings)
        return self.embeddings.embed_documents(list(input))
