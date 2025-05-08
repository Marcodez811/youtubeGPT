import uuid
from typing import List, Dict, Any, Optional
from app.services.embeddings import SentenceTransformerEmbedding
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Column, Session, text, create_engine
from pgvector.sqlalchemy import Vector
from dotenv import load_dotenv

load_dotenv()

# --- Configuration of the VectorStore---
EMBEDDING_DIMENSION = 768
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
DEFAULT_INDEX_NAME = "embeddings_index_basic" 

# --- SQLModel Definition ---
class TextChunk(SQLModel, table=True):
    __tablename__ = "chunk"
    # Add table_args for the new index
    __table_args__ = {
        'extend_existing': True,

    }
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    text: str
    vid_id: str = Field(index=True, nullable=False)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(EMBEDDING_DIMENSION)))
    meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

# --- Vector Store Implementation ---
class VectorStore:
    def __init__(self, connection_string: str, embedding_model_name: str = DEFAULT_EMBEDDING_MODEL):
        """
        Initializes a basic vector store.

        Args:
            connection_string: PostgreSQL connection string (e.g., "postgresql://user:password@host:port/dbname").
            embedding_model_name: Name of the Sentence Transformer model to use.
        """
        self.engine = create_engine(connection_string)
        self.embedding_model = SentenceTransformerEmbedding(model_name=embedding_model_name)
        # Verify model dimension matches hardcoded dimension
        actual_dim = self.embedding_model.get_embedding_dimension()
        if actual_dim != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Model '{embedding_model_name}' has dimension {actual_dim}, "
                f"but TextChunk is defined with dimension {EMBEDDING_DIMENSION}. "
                f"Please update EMBEDDING_DIMENSION constant."
            )
        self.embedding_dim = EMBEDDING_DIMENSION
        self._init_store()

    def _init_store(self):
        """Initialize DB extension, create table, and create vector index."""
        try:
            with Session(self.engine) as session:
                session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                session.commit()

                # Create table and regular indexes (like on vid_id) based on model definition
                SQLModel.metadata.create_all(self.engine)

                # --- Only check/create the VECTOR index here ---
                vector_index_check_stmt = text(f"SELECT 1 FROM pg_indexes WHERE indexname = '{DEFAULT_INDEX_NAME}'")
                vector_index_exists = session.exec(vector_index_check_stmt).scalar_one_or_none()

                if not vector_index_exists:
                    print(f"Attempting to create vector index '{DEFAULT_INDEX_NAME}'...")
                    create_vector_index_stmt = text(f"""
                        CREATE INDEX {DEFAULT_INDEX_NAME}
                        ON {TextChunk.__tablename__}
                        USING hnsw (embedding vector_l2_ops);
                    """)
                    session.exec(create_vector_index_stmt)
                    session.commit()
                    print(f"Vector index '{DEFAULT_INDEX_NAME}' created successfully.")
                else:
                    print(f"Vector index '{DEFAULT_INDEX_NAME}' already exists.")
                # --- End Vector Index Check ---

            print("Database initialized and table/indexes verified.")
        except Exception as e:
            print(f"Error initializing database: {e}")

    def insert_chunks(self, texts: List[str], vid_id: str, meta: Optional[List[Dict[str, Any]]] = None):
        """
        Generates embeddings and inserts text chunks sequentially.

        Args:
            texts (List[str]): List of text strings to insert.
            meta (Optional[List[Dict[str, Any]]]): Optional list of metadata dictionaries,
                                                    one per text string. Must be in the same order as texts.
        """
        if not texts:
            print("No texts provided for insertion.")
            return
        if not vid_id:
            print("vid_id must be provided.")

        if meta:
            if len(meta) != len(texts):
                # Keep the original length check
                print("Error: Number of metadata entries does not match number of texts.")
                return
            for i, m in enumerate(meta):
                if not isinstance(m, dict):
                    print(f"Error: Metadata at index {i} is missing.")
                    return
                
        print(f"Generating embeddings and preparing {len(texts)} chunks for insertion...")
        try:
            # Generate embeddings sequentially (can be slow for large lists)
            # Wrap the loop with tqdm for progress indication
            embeddings = self.embedding_model.create_embeddings(texts)
            chunks_to_insert = [
                TextChunk(
                    text=texts[i], 
                    vid_id=vid_id,
                    embedding=embeddings[i], 
                    meta=meta[i] if meta else None,
                ) for i in range(len(texts))
            ]
        except Exception as e:
            print(f"Error during embedding generation or chunk preparation: {e}")
            return
        # Insert all prepared chunks in one transaction
        if not chunks_to_insert:
             print("No valid chunks were prepared for insertion.")
             return
        print(f"Inserting {len(chunks_to_insert)} chunks into the database...")
        session = Session(self.engine)
        try:
            with Session(self.engine) as session:
                session.add_all(chunks_to_insert)
                session.commit()
                print(f"Inserted {len(chunks_to_insert)} chunks into the database...")
        except Exception as db_err:
            print(f"Database error during bulk insertion: {db_err}")

    def similarity_search(self, query: str, vid_id: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Perform a similarity search using a query string.

        Args:
            query: The query text.
            limit: Maximum number of results to return.

        Returns:
            List of dictionaries, each containing 'id', 'text', 'meta', and 'distance'.
            Sorted by distance (ascending - lower is more similar).
        """
        q_emb = self.embedding_model.create_embeddings(query)
        if q_emb.size == 0:
            print("Failed to generate embedding for the query.")
            return []
        # 2. Perform the search using parameter binding and L2 distance (<->)
        embedding_str = str(q_emb.tolist())

        stmt = text(f"""
            SELECT
                id,
                text,
                embedding <-> CAST(:embedding AS vector) AS distance
            FROM {TextChunk.__tablename__}
            WHERE vid_id = :vid_id
            ORDER BY distance ASC
            LIMIT :limit
        """)

        results = []
        try:
            with Session(self.engine) as session:
                results = session.exec(
                    statement=stmt,
                    params={"embedding": embedding_str, "limit": limit, "vid_id": vid_id}
                ).mappings().all()
            # .mappings().all() returns a list of dictionary-like RowMapping objects
        except Exception as e:
            print(f"Error during similarity search: {e}")

        return [dict(row) for row in results]
    
    def delete_chunks(self, vid_id: str):
        """
        Deletes chunks where the metadata contains a specific key-value pair.

        Args:
            vid_id: The value to match for the specified metadata key.
            meta_key: The key within the JSONB 'meta' column to filter on (default: 'vid_id').
        """
        if not vid_id:
            print("Error: No vid_id provided for deletion.")
            return

        table_name = TextChunk.__tablename__
        # Construct the DELETE statement with parameter binding
        stmt = text(f"""
            DELETE FROM {table_name}
            WHERE vid_id = :value_param
        """)
        deleted_count = 0
        session = Session(self.engine)
        try:
            # Execute the statement, passing only the value parameter
            result = session.exec(stmt, {"value_param": vid_id})
            session.commit()
            deleted_count = result.rowcount
            if deleted_count > 0:
                print(f"Successfully deleted {deleted_count} chunk(s) with vid_id = '{vid_id}'.")
            else:
                print(f"No chunks found with vid_id = '{vid_id}' to delete.")

        except Exception as e:
            session.rollback()
            print(f"Error deleting chunks with vid_id = '{vid_id}': {e}")
        finally:
            session.close()

        return deleted_count

    def clear_database(self):
        """
        Removes ALL data from the vector store table ('chunk').

        Warning: This operation is irreversible and deletes all inserted chunks!
        """
        table_name = TextChunk.__tablename__
        print(f"WARNING: Attempting to clear ALL data from table '{table_name}'...")

        # Optional: Add a confirmation step for safety
        # confirm = input("Are you sure you want to delete all data? (yes/no): ")
        # if confirm.lower() != 'yes':
        #     print("Operation cancelled.")
        #     return
        try:
            with Session(self.engine) as session:
                stmt = text(f"TRUNCATE TABLE {table_name};")
                session.exec(stmt)
                session.commit()
                print(f"Successfully cleared all data from table '{table_name}'.")
        except Exception as e:
            print(f"Error clearing table '{table_name}': {e}")