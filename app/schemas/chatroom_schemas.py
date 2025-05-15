# schemas/chatroom_schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List
from app.models.vid_chat import VidChat
from app.models.message import Message

# --- Request Payloads ---
class ChatroomPayload(BaseModel):
    url: HttpUrl

class ChatroomQueryPayload(BaseModel):
    query: str

# --- Response ---
class VidChatWithMessages(BaseModel):
    vid_chat: VidChat
    messages: List[Message]
