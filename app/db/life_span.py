# core/lifespan.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel # Import SQLModel here
from app.db.session import engine # Import the engine
from app.services.vector_store import VectorStore # Import VectorStore class
from app.db.session import DATABASE_URL # Import DB URL for VectorStore init
from typing import Dict

# --- Global Dictionary to Hold Shared Resources (like VectorStore) ---
# This is one way to make the initialized instance available elsewhere.
# Alternatives include passing it via app.state or using a dependency injection system.
shared_resources: Dict[str, object] = {}

@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    """
    Async context manager for FastAPI lifespan events.
    Handles database initialization and VectorStore setup.
    """
    print("Lifespan: Application startup...")

    # --- Initialize Database ---
    print("Lifespan: Initializing database tables...")
    try:
        # Import models needed for create_all *inside* the function
        # or ensure they are imported globally before SQLModel is used.
        # This example assumes models are implicitly known via SQLModel base.
        from app.models.vid_chat import VidChat # Ensure models are defined
        from app.models.message import Message # Ensure models are defined
        from app.services.vector_store import TextChunk
        SQLModel.metadata.create_all(engine)
        print("Lifespan: Database tables checked/created.")
    except Exception as e:
        print(f"Lifespan: FATAL - Database initialization failed: {e}")
        # Depending on severity, you might re-raise or handle differently
        raise RuntimeError(f"Database initialization failed: {e}") from e

    # --- Initialize Vector Store Singleton ---
    print("Lifespan: Initializing Vector Store...")
    try:
        vector_store_instance = VectorStore(connection_string=DATABASE_URL)
        # Store the instance in the shared dictionary
        shared_resources["vector_store"] = vector_store_instance
        print("Lifespan: Vector Store initialized successfully.")
    except Exception as e:
        print(f"Lifespan: FATAL - Vector Store initialization failed: {e}")
        raise RuntimeError(f"Vector Store initialization failed: {e}") from e

    yield # Application runs here

    # --- Cleanup ---
    print("Lifespan: Application shutdown...")
    # Add cleanup logic if needed (e.g., closing explicit connections, releasing GPU memory)
    shared_resources.clear() # Clear the shared resources
    print("Lifespan: Cleanup complete.")