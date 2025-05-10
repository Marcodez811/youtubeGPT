from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Dict, Any, AsyncGenerator
from app.services.transcript import load_pipeline, get_video_content, Transcript
from app.services.intent_classifier import classify_intent 
from app.services.vector_store import VectorStore
from app.services.responder import generate_summary_response, generate_qa_response
from app.models.vid_chat import VidChat
from app.models.message import Message, MessageSender
from app.schemas.chatroom_schemas import ChatroomPayload, ChatroomQueryPayload
from app.db.session import get_session
from app.db.dependencies import get_vector_store
from app.utils.yt_utils import get_description
from fastapi.responses import StreamingResponse

# --- Router Definition ---
router = APIRouter(
    prefix="/api/chatrooms",
    tags=["Chatrooms"]
)

async def _string_to_async_generator(text: str, intent: str) -> AsyncGenerator[str, None]:
    """
    Helper to wrap a simple string response into an async generator,
    optionally prefixing with intent if a structured stream (like SSE) was desired.
    For plain text stream, we just yield the text.
    """
    yield text

# --- API Endpoints ---

@router.post("/", response_model=VidChat)
def create_chatroom(payload: ChatroomPayload, session: Session = Depends(get_session), vector_store: VectorStore = Depends(get_vector_store)):
    """
    Creates a new chatroom entry by processing a YouTube URL.
    Fetches metadata, transcript, and stores it.
    Returns the created VidChat object.
    """
    url_str = str(payload.url) # Convert HttpUrl back to string if needed by helpers
    transcript_obj: Transcript = load_pipeline(url_str, False) # Assuming it takes vid_id now
    vid_id = transcript_obj.vid_id

    existing_chat = session.get(VidChat, vid_id)
    if existing_chat:
        print(f"Chatroom for {vid_id} already exists. Returning existing.")
        return existing_chat # Return existing data

    print(f"Creating new chatroom for video ID: {vid_id}")

    # 2. Fetch Metadata (consider doing this in parallel if using async)
    title = transcript_obj.vid_title
    description = get_description(url_str)
    # 3. Fetch Transcripts (handle potential errors from services)
    try:
        # Get timestamped transcript
        transcript_wts_list: List[Dict[str, Any]] = get_video_content(vid_id)
        if not isinstance(transcript_wts_list, list):
            print(f"Warning: get_video_content did not return a list for {vid_id}")
            transcript_wts_list = [] # Or raise error

    except Exception as e:
        print(f"Error getting transcript for {vid_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process transcript for video {vid_id}.")

    # 4. Create VidChat Object
    new_vid_chat = VidChat(
        id=vid_id,
        title=title,
        url=url_str,
        description=description,
        transcript=transcript_obj.content,
        transcript_wts=transcript_wts_list
    )
    # 5. Add to DB and Commit
    try:
        session.add(new_vid_chat)
        chunks = transcript_obj.chunks
        vector_store.insert_chunks(chunks, vid_id, [{}] * len(chunks))
        session.commit()
        session.refresh(new_vid_chat)
        print(f"Successfully created chatroom for {vid_id}")
        return new_vid_chat
    except Exception as e:
        session.rollback()
        print(f"Database error creating chatroom for {vid_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save chatroom data.")
    
class VidChatWithMessages(BaseModel):
    vid_chat: VidChat
    messages: List[Message]


@router.get("/{vid_id}", response_model=VidChatWithMessages)
def get_chatroom_by_id(vid_id: str, session: Session = Depends(get_session)):
    """
    Retrieves VidChat details for a given video ID.
    """
    print(f"Fetching chatroom for video ID: {vid_id}")
    vid_chat = session.get(VidChat, vid_id)
    if not vid_chat:
        print(f"Chatroom not found for video ID: {vid_id}")
        raise HTTPException(status_code=404, detail=f"Chatroom for video ID '{vid_id}' not found.")
    # fetch messages for this video chat
    messages_stm = select(Message).where(Message.vid_id == vid_id).order_by(Message.created_at)
    messages = session.exec(messages_stm).all()
    return {
        "vid_chat": vid_chat,
        "messages": messages
    }

@router.get("/", response_model=List[VidChat])
def get_chatrooms(session: Session = Depends(get_session)):
    """
    Retrieves all the current created chatrooms.
    """
    print("Fetching all the chatrooms for the user.")
    results = session.exec(
        select(
            VidChat.id,
            VidChat.title
        )
    ).mappings().all()
    return [dict(row) for row in results]


@router.post("/{vid_id}/query", response_model=Dict[str, Any])
async def query_chatroom(vid_id: str, payload: ChatroomQueryPayload, session: Session = Depends(get_session)):
    """
    Processes a user query against a specific chatroom (video).
    Classifies intent and routes to the appropriate backend service (QA, Summary, etc.).
    """
    user_query = payload.query
    print(f"Received query for vid_id '{vid_id}': '{user_query}'")

    # 1. Get the VidChat data (including transcript)
    vid_chat = session.get(VidChat, vid_id)
    if not vid_chat:
        raise HTTPException(status_code=404, detail=f"Chatroom for video ID '{vid_id}' not found.")

    if not vid_chat.transcript:
         raise HTTPException(status_code=400, detail=f"Transcript is not available for video ID '{vid_id}'. Cannot process query.")

    # 2. Classify Intent
    try:
        # Assuming classify_intent takes the user query string
        intent = classify_intent(user_query)
        print(f"Classified Intent: {intent}")
    except Exception as e:
        print(f"Error classifying intent for query '{user_query}': {e}")
        raise HTTPException(status_code=500, detail="Failed to classify query intent.")

    # 3. Route based on Intent and prepare the stream generator
    content_stream_generator: AsyncGenerator[str, None]

    try:
        if intent == "summarization":
            # Call your summarization function/service
            # Pass the necessary context (full transcript, specific user query)
            content_stream_generator = generate_summary_response(vid_chat.transcript, user_query)
        elif intent == "question-answering":
            # Call your RAG/QA function/service
            # Pass the query and potentially the vid_id to access vector store chunks
            content_stream_generator = generate_qa_response(user_query, vid_id) # Assuming RAG uses vid_id
        elif intent == "quiz-gen":
            # response_content = generate_quiz(vid_chat.transcript)
            response_content = "Quiz generation is not implemented yet." # Placeholder
            content_stream_generator = _string_to_async_generator(response_content, intent)
        elif intent == "flashcard-gen":
            # response_content = generate_flashcards(vid_chat.transcript)
            response_content = "Flashcard generation is not implemented yet." # Placeholder
            content_stream_generator = _string_to_async_generator(response_content, intent)
        elif intent == "irrelevant":
            response_content = "This seems unrelated to the video content. How can I help you with the video?"
            content_stream_generator = _string_to_async_generator(response_content, intent)
        # Add handling for 'general' intent if you implement it
            # response_content = generate_general_response(user_query, conversation_history) # Needs history
            # response_content = "Okay." # Simple placeholder
        # elif intent == "general":
        else:
            # Handle unknown or unhandled intents
            print(f"Warning: Unhandled intent '{intent}' received.")
            response_content = "Sorry, I'm not sure how to handle that request regarding the video."
            content_stream_generator = _string_to_async_generator(response_content, intent)

        # Create an async generator that preserves streaming and saves messages
        async def message_stream_generator():
            # Save user message
            user_message = Message(
                vid_id=vid_id,
                content=user_query,
                sent_by=MessageSender.USER
            )
            session.add(user_message)

            # Collect bot response while streaming
            bot_response = ""
            try:
                async for chunk in content_stream_generator:
                    bot_response += chunk
                    yield chunk
            except:
                bot_response = "We've encountered an ERROR while generating the content."
            # Save bot message after stream is complete
            bot_message = Message(
                vid_id=vid_id,
                content=bot_response,
                sent_by=MessageSender.BOT
            )
            session.add(bot_message)
            session.commit()

        return StreamingResponse(message_stream_generator(), media_type="text/plain")

    except Exception as e:
         print(f"Error processing intent '{intent}' for vid_id '{vid_id}': {e}")
         # Return a generic error to the user, log the details
         raise HTTPException(status_code=500, detail=f"An error occurred while processing your request.")