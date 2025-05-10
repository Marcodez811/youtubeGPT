from sqlmodel import SQLModel, Field, Index, Column, Enum
import uuid
from datetime import datetime
from enum import Enum as PyEnum

class MessageSender(PyEnum):
    BOT = "bot"
    USER = "user"

# Define the composite index name
MESSAGE_VID_TIMESTAMP_INDEX = "ix_message_vid_id_created_at"

class Message(SQLModel, table=True):
    __tablename__ = "message"
    __table_args__ = (
        Index(MESSAGE_VID_TIMESTAMP_INDEX, "vid_id", "created_at"),
        {'extend_existing': True}
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vid_id: str = Field(index=True, nullable=False)
    content: str
    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False
    )
    sent_by: str = Field(
        sa_column=Column(
            "sent_by", 
            Enum(MessageSender), 
            nullable=False
        )
    )