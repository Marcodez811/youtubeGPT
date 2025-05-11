from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select
from sqlalchemy import delete
from pydantic import BaseModel
from typing import List, Dict, Any, AsyncGenerator
from app.services.transcript import load_pipeline, get_video_content, Transcript
from app.services.intent_classifier import classify_intent 
from app.services.vector_store import VectorStore
from app.services.responder import generate_qa_response, generate_summary, generate_chat_response, generate_summary_full, generate_summary_specific
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
    except Exception as e:
        print(f"Error getting transcript for {vid_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process transcript for video {vid_id}.")

    # 4. Create VidChat Object
    new_vid_chat = VidChat(
        id=vid_id,
        title=title,
        url=url_str,
        description=description,
        summary=generate_summary("Give a high level summarizaiton of what this video is all about.", transcript_obj.content),
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

@router.delete("/{vid_id}", status_code=204)
async def delete_chatroom_by_id(
    vid_id: str,
    session: Session = Depends(get_session),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Deletes a chatroom and all associated messages by video ID.

    Args:
    - vid_id (str): The ID of the video, which is also used as the ID for the VidChat.
    - session (Session): The database session.
    - vector_store (VectorStore): The vector store client.

    Returns:
    - 204 No Content on success.
    - 404 if the chatroom (VidChat) with the given vid_id is not found.
    - 500 on other database errors or issues with the vector store.
    """
    try:
        # 1. Attempt to find the chatroom (VidChat) first.
        #    This allows us to fail fast with a 404 if it doesn't exist.
        chatroom_statement = select(VidChat).where(VidChat.id == vid_id)
        chatroom_to_delete = session.exec(chatroom_statement).first()

        if not chatroom_to_delete:
            raise HTTPException(
                status_code=404,
                detail=f"Chatroom with vid_id '{vid_id}' not found."
            )

        # 2. Delete associated messages
        session.exec(delete(Message).where(Message.vid_id == vid_id))

        # 3. Delete the chatroom (VidChat) itself
        print(f"Marking chatroom '{vid_id}' for deletion.")
        session.delete(chatroom_to_delete)

        # 4. Delete associated chunks from the vector store
        print(f"Requesting deletion of chunks for vid_id '{vid_id}' from vector store.")
        vector_store.delete_chunks(vid_id)
        print(f"Successfully requested deletion of chunks for vid_id '{vid_id}'.")

        # 5. Commit the database transaction
        session.commit()
        print(f"Successfully deleted chatroom and messages for vid_id '{vid_id}' and committed to DB.")

        return Response(status_code=204)

    except HTTPException:
        # Re-raise HTTPException directly to preserve its status code and details
        raise
    except Exception as e:
        # For any other type of exception (e.g., database error during commit,
        # vector store error if it raises something other than HTTPException)
        print(f"An error occurred: {str(e)}. Rolling back session.")
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete chatroom for vid_id '{vid_id}': {str(e)}"
        )

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
        # Summarization
        if intent == "summarize_full":
            content_stream_generator = generate_summary_full(vid_chat.transcript, user_query)
        elif intent == "summarize_specific":
            content_stream_generator = generate_summary_specific(vid_id, user_query)
        # Q&A
        elif intent == "qa_specific":
            content_stream_generator = generate_qa_response(user_query, vid_id)
        # Conversational
        elif intent == "general_chat":
            # current uses the vanilla sliding window method for allowing conversational flow.
            stmt = select(Message.content, Message.sent_by).where(Message.vid_id == vid_id).order_by(Message.created_at.desc()).limit(5)
            results = session.exec(stmt).mappings().all()
            history = list(reversed([f'{m.sent_by}: "{m.content}"' for m in results]))
            content_stream_generator = generate_chat_response(user_query, vid_chat.title, vid_chat.summary, history)
        # Learning Tools
        elif intent in ["flashcards_full", "quiz_full"]:
            response_content = f"{intent.split('_')[0].title()} generation for full video is not implemented yet."
            content_stream_generator = _string_to_async_generator(response_content, intent)
        elif intent in ["flashcards_topic", "quiz_topic"]:
            response_content = f"{intent.split('_')[0].title()} generation for specific topics is not implemented yet."
            content_stream_generator = _string_to_async_generator(response_content, intent)
        # Utility
        elif intent == "irrelevant":
            response_content = "This seems unrelated to the video content. How can I help you with the video?"
            content_stream_generator = _string_to_async_generator(response_content, intent)
        else:
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

        