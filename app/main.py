from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.life_span import lifespan_manager
from app.api import chatroom

import requests
from bs4 import BeautifulSoup

# --- App Initialization with Lifespan ---
app = FastAPI(
    title="Youtube.AI API",
    description="API for interacting with YouTube video transcripts, generating summaries, answering questions, and more.",
    version="0.1.0",
    lifespan=lifespan_manager
)

# --- CORS Middleware ---
# Configure allowed origins based on your frontend deployment
origins = [
    "http://localhost:5173",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include API Routers ---
app.include_router(chatroom.router)

@app.get("/", tags=["Root"])
def read_root():
    """
    Root endpoint providing a basic welcome message.
    """
    return {"message": "Welcome to the Youtube.AI API!"}

@app.get("/get-title")
def get_title(url: str):
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        return {"title": title_tag.text.split(' - YouTube')[0]}
    return {"title": None}