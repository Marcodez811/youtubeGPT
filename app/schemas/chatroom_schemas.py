# schemas/chatroom_schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional

# --- Request Payloads ---
class ChatroomPayload(BaseModel):
    url: HttpUrl

class ChatroomQueryPayload(BaseModel):
    query: str

# --- Response Schemas ---
class VidChatResponse(BaseModel):
    id: str
    title: str
    url: str
    description: str
    # Optionally exclude large fields from default responses
    # transcript: Optional[str] = None
    # transcript_wts: Optional[List[Dict[str, Any]]] = None

    class Config:
        orm_mode = True # Allow creation from ORM objects

class QueryResponse(BaseModel):
    intent: Optional[str] = None # Make optional in case classification fails
    response: str
    vid_id: str