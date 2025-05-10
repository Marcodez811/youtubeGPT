from fastapi import HTTPException
from app.db.life_span import shared_resources
from app.services.vector_store import VectorStore

def get_vector_store() -> VectorStore:
    """FastAPI dependency to get the initialized VectorStore instance."""
    vector_store = shared_resources.get("vector_store")
    if not isinstance(vector_store, VectorStore):
         # Log error appropriately
         print("CRITICAL: Vector Store not found or not initialized in shared resources.")
         raise HTTPException(
             status_code=500,
             detail="Internal server error: Vector Store unavailable."
         )
    return vector_store