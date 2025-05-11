from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Dict, Any, Optional

# --- SQLModel Definition ---
class VidChat(SQLModel, table=True):
    __tablename__ = "vid_chat"
    id: str = Field(primary_key=True)
    title: str
    url: str
    description: str = Field(default="")
    summary: str = Field(default="", nullable=True)
    transcript: str # Plain text transcript
    # Store list of timestamped segments as JSONB
    transcript_wts: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSONB))

    class Config:
        from_attributes = True
