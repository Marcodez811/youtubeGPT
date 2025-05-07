# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Import the lifespan manager from your core directory
from app.db.life_span import lifespan_manager

# 2. Import the main router(s) from your routes directory
from app.api import chatroom

import requests
from bs4 import BeautifulSoup

# --- App Initialization with Lifespan ---
# The lifespan manager handles startup (DB init, VectorStore init) and shutdown
app = FastAPI(
    title="Youtube.AI API",
    description="API for interacting with YouTube video transcripts, generating summaries, answering questions, and more.",
    version="0.1.0",
    lifespan=lifespan_manager
)

# --- CORS Middleware ---
# Configure allowed origins based on your frontend deployment
origins = [
    "http://localhost:5173", # Vite default dev server
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Allow cookies if needed
    allow_methods=["*"],    # Allows all standard methods
    allow_headers=["*"],    # Allows all headers
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