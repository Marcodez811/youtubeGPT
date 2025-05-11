from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from app.db.life_span import shared_resources
from app.services.templates.qa import TEMPLATE_QA_SPECIFIC 
from app.services.templates.summarization import TEMPLATE_FULL_SUMMARY, TEMPLATE_RAG_SUMMARY
from app.services.templates.chat import CHAT_TEMPLATE
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

def generate_summary(query: str, transcript: str):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro-exp-03-25",
        temperature=0.5,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    prompt_template = ChatPromptTemplate.from_template(TEMPLATE_FULL_SUMMARY)
    prompt = prompt_template.invoke({
            "transcript": transcript,
            "user_query": query
        })
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        print(f"An error occurred: {e}")

async def generate_qa_response(query: str, vid_id: str):
    vector_store = shared_resources.get("vector_store")
    results = vector_store.similarity_search(query=query, vid_id=vid_id)
    retrieved_chunks = [str(r['text']) for r in results]

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=1.0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    prompt_template = ChatPromptTemplate.from_template(TEMPLATE_QA_SPECIFIC)
    prompt = prompt_template.invoke({
            "user_query": query,
            "retrieved_knowledge": str("\n-".join(retrieved_chunks)),
        })

    try:
        print("\n--- Invoking LLM Stream---")
        async for chunk in llm.astream(prompt):
            # chunk is typically an AIMessageChunk or similar object
            content = chunk.content
            if content: # Ensure content exists before yielding
                yield content
        print("\n--- LLM Response Completed---")
    except Exception as e:
        print(f"\n--- Error during LLM Invocation ---")
        print(f"An error occurred: {e}")
        yield f"\nAn error occurred while generating the response: {e}"

async def generate_chat_response(query: str, title: str, summary: str, history: List[str]):
    """For general_chat intent"""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=1,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    prompt_template = ChatPromptTemplate.from_template(CHAT_TEMPLATE)
    prompt = prompt_template.invoke({
            "video_title": title,
            "video_summary": summary,
            "history": "\n".join(history),
            "query": query
        })
    try:
        print("\n--- Invoking LLM Stream---")
        async for chunk in llm.astream(prompt):
            content = chunk.content
            if content: # Ensure content exists before yielding
                yield content
        print("\n--- LLM Response Completed---")
    except Exception as e:
        print(f"\n--- Error during LLM Invocation ---")
        print(f"An error occurred: {e}")
        yield f"\nAn error occurred while generating the response: {e}"

async def generate_summary_full(transcript: str, query: str):
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro-exp-03-25",
        temperature=0.5,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    prompt_template = ChatPromptTemplate.from_template(TEMPLATE_FULL_SUMMARY)
    prompt = prompt_template.invoke({
            "transcript": transcript,
            "user_query": query
        })

    try:
        print("\n--- Invoking LLM Stream---")
        async for chunk in llm.astream(prompt):
            content = chunk.content
            if content:
                yield content
        print("\n--- LLM Response Completed---")
    except Exception as e:
        print(f"\n--- Error during LLM Invocation ---")
        print(f"An error occurred: {e}")
        yield f"\nAn error occurred while generating the response: {e}"

async def generate_summary_specific(vid_id: str, query: str):
    vector_store = shared_resources.get("vector_store")
    results = vector_store.similarity_search(query=query, vid_id=vid_id)
    retrieved_chunks = [str(r['text']) for r in results]
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.5,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    prompt_template = ChatPromptTemplate.from_template(TEMPLATE_RAG_SUMMARY)
    prompt = prompt_template.invoke({
            "retrieved_knowledge": str("\n-".join(retrieved_chunks)),
            "user_query": query
        })

    try:
        print("\n--- Invoking LLM Stream---")
        async for chunk in llm.astream(prompt):
            content = chunk.content
            if content:
                yield content
        print("\n--- LLM Response Completed---")
    except Exception as e:
        print(f"\n--- Error during LLM Invocation ---")
        print(f"An error occurred: {e}")
        yield f"\nAn error occurred while generating the response: {e}"


# """Not yet implemented!!!"""

async def generate_flashcards_full(transcript: str):
    """Handles both flashcards_full and flashcards_topic intents"""
    pass

async def generate_flashcards_topic(query: str, vid_id: str):
    """Handles both flashcards_full and flashcards_topic intents"""
    pass

async def generate_quiz_full(transcript: str, scope: str, topic: str = None):
    """Handles both quiz_full and quiz_topic intents"""
    pass

async def generate_quiz_topic(query: str, vid_id: str):
    """Handles both quiz_full and quiz_topic intents"""
    pass