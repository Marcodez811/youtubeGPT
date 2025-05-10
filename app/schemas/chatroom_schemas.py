# schemas/chatroom_schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional

# --- Request Payloads ---
class ChatroomPayload(BaseModel):
    url: HttpUrl

class ChatroomQueryPayload(BaseModel):
    query: str