from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Dict, Any, Optional

# --- SQLModel Definition ---
class VidChat(SQLModel, table=True):
    __tablename__ = "vid_chat"
    # id is the YouTube Video ID
    id: str = Field(primary_key=True)
    title: str
    url: str # Store original URL
    description: str = Field(default="") # Default to empty string
    transcript: str # Plain text transcript
    # Store list of timestamped segments as JSONB
    transcript_wts: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSONB))

    class Config:
        # Allow ORM mode for returning SQLModel objects directly
        orm_mode = True
