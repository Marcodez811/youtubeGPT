from sqlmodel import SQLModel, create_engine, Session 
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

# echo=False for production, else Verbose logging is enabled
engine = create_engine(DATABASE_URL, echo=False)

def get_session():
    with Session(engine) as session:
        yield session

async def init_db():
    from app.models.vid_chat import VidChat
    from app.models.message import Message
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    print("Database tables checked/created.")